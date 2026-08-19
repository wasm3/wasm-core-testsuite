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

from process import convert, process, set_tool_paths

SPEC_TAG = os.environ.get("SPEC_TAG", "wg-3.0")
WABT_VERSION = os.environ.get("WABT_VERSION", "1.0.41")
WASM_TOOLS_VERSION = os.environ.get("WASM_TOOLS_VERSION", "1.256.0")

PLATFORMS = {
    # (system, machine): (wabt, wasm-tools)
    ("Linux",   "x86_64"):  ("linux-x64",   "x86_64-linux"),
    ("Linux",   "aarch64"): ("linux-arm64", "aarch64-linux"),
    ("Darwin",  "arm64"):   ("macos-arm64", "aarch64-macos"),
    ("Windows", "AMD64"):   ("windows-x64", "x86_64-windows"),
}

# Testsuites of proposals that are not part of Wasm 3.0, taken from the proposal's own
# repo (github.com/WebAssembly/<name>). Everything else these repos carry is just their
# copy of the spec testsuite, which core/ already covers.
PROPOSALS = ["threads", "custom-page-sizes", "wide-arithmetic", "stack-switching",
             "compact-import-section"]

# Every feature wabt knows about, used to tell a proposal's own tests apart from the
# rest of the suite: they are the ones that need its flag on top of all the others.
WABT_FEATURES = ["annotations", "code-metadata", "compact-imports", "custom-page-sizes",
                 "exceptions", "extended-const", "function-references", "gc", "memory64",
                 "multi-memory", "relaxed-simd", "tail-call", "threads", "wide-arithmetic"]

# wabt 1.0.41 writes compact import groups with the item count instead of the
# grouped entry count, producing binaries that conforming decoders reject.
BROKEN_WABT_FEATURES = {"compact-imports"}

DEPS = Path("_wast")


def wabt_flags(*excluded):
    """All stable wabt features needed for conversion, excluding known-bad emitters."""
    skipped = BROKEN_WABT_FEATURES | set(excluded)
    return " ".join(f"--enable-{f}" for f in WABT_FEATURES if f not in skipped)


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

    suffix = ".exe" if platform.system() == "Windows" else ""
    pinned = {
        "wast2json": wabt / "bin" / f"wast2json{suffix}",
        "wasm-tools": wasmTools / f"wasm-tools{suffix}",
    }
    set_tool_paths(pinned)

    for binDir in (wabt / "bin", wasmTools):
        os.environ["PATH"] = str(binDir.resolve()) + os.pathsep + os.environ["PATH"]
    subprocess.check_call([str(pinned["wast2json"]), "--version"])
    subprocess.check_call([str(pinned["wasm-tools"]), "--version"])


def belongs(name, fn, testDir, probe):
    """Does this test of the proposal's repo actually exercise the proposal?

    Two ways of telling. The tests a proposal adds live under its own name, either in a
    `test/core/<name>/` directory or as a single `test/core/<name>.wast`. On top of that,
    proposals usually extend a handful of the shared tests as well; those are found by
    conversion: they need the proposal's own feature flag, everything else wabt knows
    about isn't enough. (The second test only works for proposals wabt implements.)"""
    rel = fn.relative_to(testDir)
    if rel.parts[0] in (name, f"{name}.wast"):
        return True
    if name not in WABT_FEATURES:
        return False
    deps = wabt_flags(name)
    return bool(convert(fn, probe, deps)) and not convert(fn, probe, f"{deps} --enable-{name}")


def collect(name, repoDir):
    """Gathers the tests that actually exercise the proposal into a single directory."""
    wastDir = DEPS / "proposals" / name
    shutil.rmtree(wastDir, ignore_errors=True)
    wastDir.mkdir(parents=True)

    testDir = repoDir / "test/core"
    with tempfile.TemporaryDirectory() as probeDir:
        probe = Path(probeDir) / "probe.json"
        for fn in sorted(testDir.glob("**/*.wast")):
            if not belongs(name, fn, testDir, probe):
                continue
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

    # The spec testsuite is mirrored one directory at a time: everything Wasm 3.0 pulled
    # in (gc, memory64, multi-memory, exceptions, relaxed-simd, ...) keeps living in its
    # own subdirectory, the way the spec repo lays it out.
    testDir = spec / "test/core"
    shutil.rmtree("core", ignore_errors=True)
    flags = wabt_flags()
    process(testDir, "core", flags)
    for sub in sorted(p for p in testDir.iterdir() if p.is_dir()):
        process(sub, Path("core") / sub.name, flags)

    shutil.rmtree("proposals", ignore_errors=True)
    for name in PROPOSALS:
        repoDir = fetch(f"https://github.com/WebAssembly/{name}/archive/refs/heads/main.zip",
                        f"{name}-main.zip", f"{name}-main")
        wastDir = collect(name, repoDir)
        process(wastDir, Path("proposals") / name, flags)


if __name__ == "__main__":
    main()
