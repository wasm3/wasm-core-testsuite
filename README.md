# wasm-core-testsuite

WebAssembly core testsuite, converted using `wast2json`.

- `core/` — the WebAssembly 3.0 core testsuite
  ([`wg-3.0`](https://github.com/WebAssembly/spec/tree/wg-3.0/test/core) tag of the spec repo),
  laid out the way the spec repo lays it out: everything Wasm 3.0 absorbed keeps its own
  subdirectory — `core/bulk-memory/`, `core/exceptions/`, `core/gc/`, `core/memory64/`,
  `core/multi-memory/`, `core/relaxed-simd/` and `core/simd/`
- `proposals/` — testsuites of proposals that are not part of Wasm 3.0, taken from each
  proposal's own repo: `threads`, `custom-page-sizes`, `wide-arithmetic` and `stack-switching`

Only the tests that actually exercise a proposal end up in its directory: the ones it adds
under its own name, plus any of the shared tests that don't convert until its feature is
enabled.

## Regenerating

Run on Linux (or under WSL on Windows):

```sh
./process_all.py
```

The script downloads the spec testsuite, the proposal repos and a
[wabt](https://github.com/WebAssembly/wabt) release into `_wast/`, and regenerates `core/`
and `proposals/`. The spec tag and tool versions can be overridden via the `SPEC_TAG`,
`WABT_VERSION` and `WASM_TOOLS_VERSION` environment variables.

Whatever `wast2json` can't read — GC types, 64-bit index types, `module definition` — is
converted with [wasm-tools](https://github.com/bytecodealliance/wasm-tools) `json-from-wast`
instead; the run prints which files those were. Its JSON is modelled on `wast2json`, but is
printed compactly and tags each module with a `module_type` field.
