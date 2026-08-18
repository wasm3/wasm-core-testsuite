#!/usr/bin/env python3

import os, sys, glob
import json
import shlex
import subprocess
import argparse
import pathlib


def ensure_path(p):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)


def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def warning(msg):
    print(f"Warning: {msg}", flush=True)


def convert(wast_fn, json_fn, flags="", tool="wast2json"):
    """Converts a single .wast file. Returns None on success, the error output otherwise.

    wast2json reports some errors without failing, so any output counts as an error.
    wasm-tools understands every proposal, so it takes no feature flags."""
    wast_fn, json_fn = str(wast_fn), str(json_fn)
    if tool == "wasm-tools":
        cmd = ["wasm-tools", "json-from-wast", "--wasm-dir", os.path.dirname(json_fn) or ".",
               "-o", json_fn, wast_fn]
    else:
        cmd = ["wast2json", "--debug-names"] + shlex.split(flags) + ["-o", json_fn, wast_fn]
    try:
        out = run(cmd)
    except subprocess.CalledProcessError as e:
        out = e.output
    return out.decode(errors="replace").strip() or None


def discard(json_fn):
    """Throws away the result of a conversion; prune() sweeps up its module files."""
    try:
        os.remove(json_fn)
    except FileNotFoundError:
        pass


def prune(jsonDir):
    """Drops the module files no .json refers to.

    Those are the leftovers of conversions that failed or got redone with another tool,
    plus the ones wasm-tools writes but never names: it emits both a .wat and a .wasm
    for some text modules."""
    used = set()
    for json_fn in glob.glob(os.path.join(jsonDir, "*.json")):
        with open(json_fn) as f:
            used |= set(find_filenames(json.load(f)))
    for fn in glob.glob(os.path.join(jsonDir, "*.wasm")) + glob.glob(os.path.join(jsonDir, "*.wat")):
        if os.path.basename(fn) not in used:
            os.remove(fn)


def find_filenames(node):
    """Yields every "filename" a converted testsuite refers to."""
    if isinstance(node, dict):
        if isinstance(node.get("filename"), str):
            yield node["filename"]
        for value in node.values():
            yield from find_filenames(value)
    elif isinstance(node, list):
        for value in node:
            yield from find_filenames(value)


def process(wastDir, jsonDir, flags="", optimize=None, tool="wast2json"):
    wastDir, jsonDir = str(wastDir), str(jsonDir)
    ensure_path(jsonDir)

    print(f"Preprocessing spec files: {wastDir} -> {jsonDir}", flush=True)

    fallback = []
    inputFiles = glob.glob(os.path.join(wastDir, "*.wast"))
    inputFiles.sort()
    for fn in inputFiles:
        fn = os.path.basename(fn)

        wast_fn = os.path.join(wastDir, fn)
        json_fn = os.path.join(jsonDir, os.path.splitext(fn)[0]) + ".json"
        err = convert(wast_fn, json_fn, flags, tool)
        if err and tool == "wast2json":
            # wabt's text parser lags behind the spec (GC types, 64-bit index types,
            # `module definition`, ...), so retry with wasm-tools, which understands
            # everything the spec repo throws at it.
            discard(json_fn)
            err = convert(wast_fn, json_fn, tool="wasm-tools")
            if not err:
                fallback.append(fn)
        if err:
            discard(json_fn)
            warning(f"Could not process {wast_fn}:\n{err}")

    if fallback:
        print(f"Converted with wasm-tools: {' '.join(fallback)}", flush=True)

    prune(jsonDir)

    if optimize:
        wasmFiles = glob.glob(os.path.join(jsonDir, "*.wasm"))
        wasmFiles.sort()
        for fn in wasmFiles:
            try:
                run(["wasm-opt"] + shlex.split(optimize) + [fn, "-o", fn])
            except subprocess.CalledProcessError as e:
                warning(f"Could not optimize {fn}:\n{e.output.decode(errors='replace').strip()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--optimize")   # i.e. "-O3"
    parser.add_argument("--flags", default="")
    parser.add_argument("--tool", default="wast2json")   # or "wasm-tools"
    parser.add_argument("input")
    parser.add_argument("output")

    args = parser.parse_args()

    process(args.input, args.output, args.flags, args.optimize, args.tool)


if __name__ == "__main__":
    main()
