#!/usr/bin/env python3

import os, sys, glob, time
import subprocess
import argparse
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument("--optimize")   # i.e. "-O3"
parser.add_argument("--flags", default="")
parser.add_argument("input")
parser.add_argument("output")

args = parser.parse_args()

#print(args)

wastDir = args.input
jsonDir = args.output

def ensure_path(p):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)

def warning(msg):
    print(f"Warning: {msg}")

ensure_path(jsonDir)

if True:
    print("Preprocessing spec files...")

    inputFiles = glob.glob(os.path.join(wastDir, "*.wast"))
    inputFiles.sort()
    for fn in inputFiles:
        fn = os.path.basename(fn)

        wast_fn = os.path.join(wastDir, fn)
        json_fn = os.path.join(jsonDir, os.path.splitext(fn)[0]) + ".json"
        try:
            run(f"wast2json --debug-names {args.flags} -o {json_fn} {wast_fn}")
        except Exception:
            warning(f"Could not process {wast_fn}")

    if args.optimize:
        wasmFiles = glob.glob(os.path.join(jsonDir, "*.wasm"))
        wasmFiles.sort()
        for fn in wasmFiles:
            try:
                run(f"wasm-opt {args.optimize} {fn} -o {fn}")
            except Exception:
                pass
