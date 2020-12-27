#!/usr/bin/env bash

export PATH=~/_Projects/Wasm/test/wabt/build:$PATH

./process.py ./_wast/core-opam-1.1.1 ./core

./process.py --flags=""                                 ./_wast/proposals/mutable-global ./proposals/mutable-global
./process.py --flags="--enable-bulk-memory"             ./_wast/proposals/bulk-memory-operations ./proposals/bulk-memory-operations/
./process.py --flags="--enable-reference-types"         ./_wast/proposals/reference-types ./proposals/reference-types
./process.py --flags="--enable-sign-extension"          ./_wast/proposals/sign-extension-ops ./proposals/sign-extension-ops
./process.py --flags="--enable-tail-call"               ./_wast/proposals/tail-call ./proposals/tail-call
./process.py --flags="--enable-threads"                 ./_wast/proposals/threads ./proposals/threads
./process.py --flags="--enable-saturating-float-to-int" ./_wast/proposals/nontrapping-float-to-int-conversions ./proposals/nontrapping-float-to-int-conversions

# TODO:
#./process.py --flags="--enable-simd"                   ./_wast/proposals/simd ./proposals/simd
#./process.py --flags="--enable-exceptions"             ./_wast/proposals/___ ./proposals/___
