#!/usr/bin/env python3

"""
Regenerates the testsuite from the WebAssembly spec repo, using wast2json (wabt)
and, for what wabt cannot parse yet, wasm-tools.

Meant to be run on Linux (or under WSL on Windows):
    ./process_all.py

Everything that gets downloaded lands in ./_wast (git-ignored).
"""

import os, sys
import platform
import shutil
import tarfile
import zipfile
import urllib.request
import subprocess
import tempfile
from pathlib import Path

from process import convert, process

SPEC_TAG = os.environ.get("SPEC_TAG", "wg-2.0")
WABT_VERSION = os.environ.get("WABT_VERSION", "1.0.41")
WASM_TOOLS_VERSION = os.environ.get("WASM_TOOLS_VERSION", "1.256.0")

PLATFORMS = {
    # (system, machine): (wabt, wasm-tools)
    ("Linux",   "x86_64"):  ("linux-x64",   "x86_64-linux"),
    ("Linux",   "aarch64"): ("linux-arm64", "aarch64-linux"),
    ("Darwin",  "arm64"):   ("macos-arm64", "aarch64-macos"),
    ("Windows", "AMD64"):   ("windows-x64", "x86_64-windows"),
}

# Testsuites of proposals that are not part of Wasm 2.0, taken from the proposal's
# own repo. Which tests belong to a proposal is figured out automatically: they are
# the ones that don't convert with just the "deps" features (everything the tests rely
# on besides the proposal itself), but do convert once the proposal is enabled too.
PROPOSALS = {
    "tail-call":           {"flags": "--enable-tail-call"},
    "extended-const":      {"flags": "--enable-extended-const"},
    "function-references": {"flags": "--enable-function-references", "deps": "--enable-tail-call"},
    "multi-memory":        {"flags": "--enable-multi-memory"},
    # wabt's text parser doesn't understand GC types at all, so these tests are converted
    # with wasm-tools, which needs no feature flags: what identifies them is that wabt
    # can't handle them even with every feature it knows about turned on.
    "gc":                  {"deps": "--enable-all", "tool": "wasm-tools"},
    "exceptions":          {"flags": "--enable-exceptions", "deps": "--enable-tail-call",
                            "repo": "exception-handling"},
    "threads":             {"flags": "--enable-threads"},
}

DEPS = Path("_wast")


def fetch(url, archive, dirname):
    """Download and unpack an archive into DEPS, unless it's already there."""
    archive, dirname = DEPS / archive, DEPS / dirname
    if dirname.is_dir():
        return dirname

    print(f"Downloading {url}", flush=True)
    urllib.request.urlretrieve(url, archive)

    # Unpack next to the final location and move it into place only once complete,
    # so that an interrupted run doesn't leave a half-extracted directory behind.
    staging = DEPS / (dirname.name + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(staging)
    else:
        with tarfile.open(archive) as tf:
            if sys.version_info >= (3, 12):
                tf.extractall(staging, filter="data")
            else:
                tf.extractall(staging)
    unpacked, = staging.iterdir()   # each archive holds a single top-level directory
    os.replace(unpacked, dirname)
    shutil.rmtree(staging, ignore_errors=True)
    return dirname


def install_tools():
    """Downloads the converters and puts them on PATH."""
    key = (platform.system(), platform.machine())
    if key not in PLATFORMS:
        sys.exit(f"No prebuilt wabt / wasm-tools for {key}")
    wabtPlat, wasmToolsPlat = PLATFORMS[key]

    wabt = fetch(f"https://github.com/WebAssembly/wabt/releases/download/{WABT_VERSION}"
                 f"/wabt-{WABT_VERSION}-{wabtPlat}.tar.gz",
                 f"wabt-{WABT_VERSION}.tar.gz", f"wabt-{WABT_VERSION}")
    wasmTools = fetch(f"https://github.com/bytecodealliance/wasm-tools/releases/download"
                      f"/v{WASM_TOOLS_VERSION}/wasm-tools-{WASM_TOOLS_VERSION}-{wasmToolsPlat}.tar.gz",
                      f"wasm-tools-{WASM_TOOLS_VERSION}.tar.gz",
                      f"wasm-tools-{WASM_TOOLS_VERSION}-{wasmToolsPlat}")

    for binDir in (wabt / "bin", wasmTools):
        os.environ["PATH"] = str(binDir.resolve()) + os.pathsep + os.environ["PATH"]
    subprocess.check_call(["wast2json", "--version"])
    subprocess.check_call(["wasm-tools", "--version"])


def collect(name, repoDir, flags, deps, tool):
    """Gathers the tests that actually exercise the proposal into a single directory."""
    wastDir = DEPS / "proposals" / name
    shutil.rmtree(wastDir, ignore_errors=True)
    wastDir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as probeDir:
        probe = Path(probeDir) / "probe.json"
        for fn in sorted((repoDir / "test/core").glob("**/*.wast")):
            if not convert(fn, probe, deps):
                continue        # converts fine without the proposal
            if convert(fn, probe, f"{deps} {flags}", tool):
                continue        # needs more than the proposal
            dst = wastDir / fn.name
            if dst.exists():
                dst = wastDir / f"{fn.parent.name}-{fn.name}"
            shutil.copy(fn, dst)

    print(f"Selected {len(list(wastDir.glob('*.wast')))} {name} tests", flush=True)
    return wastDir


def main():
    os.chdir(Path(__file__).parent)
    DEPS.mkdir(parents=True, exist_ok=True)

    install_tools()

    spec = fetch(f"https://github.com/WebAssembly/spec/archive/refs/tags/{SPEC_TAG}.zip",
                 f"spec-{SPEC_TAG}.zip", f"spec-{SPEC_TAG}")

    # All WebAssembly 2.0 features (multi-value, sign-extension, saturating float-to-int,
    # bulk memory, reference types, SIMD, mutable globals) are enabled by default in wabt.
    shutil.rmtree("core", ignore_errors=True)
    process(spec / "test/core",      "core")
    process(spec / "test/core/simd", "core/simd")

    for name, proposal in PROPOSALS.items():
        repo = proposal.get("repo", name)
        repoDir = fetch(f"https://github.com/WebAssembly/{repo}/archive/refs/heads/main.zip",
                        f"{repo}-main.zip", f"{repo}-main")
        flags = proposal.get("flags", "")
        deps = proposal.get("deps", "")
        tool = proposal.get("tool", "wast2json")
        wastDir = collect(name, repoDir, flags, deps, tool)
        shutil.rmtree(Path("proposals") / name, ignore_errors=True)
        process(wastDir, Path("proposals") / name, f"{deps} {flags}", tool=tool)


if __name__ == "__main__":
    main()
