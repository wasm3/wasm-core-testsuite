# wasm-core-testsuite

WebAssembly core testsuite, converted using `wast2json`.

- `core/` — the [WebAssembly 2.0](https://www.w3.org/TR/wasm-core-2/) core testsuite
  ([`wg-2.0`](https://github.com/WebAssembly/spec/tree/wg-2.0/test/core) tag of the spec repo),
  including `core/simd/`
- `proposals/` — testsuites of proposals that are not part of Wasm 2.0, taken from each
  proposal's own repo: `tail-call`, `extended-const`, `function-references`, `multi-memory`,
  `gc`, `exceptions` ([exception-handling](https://github.com/WebAssembly/exception-handling))
  and `threads`

Only the tests that actually exercise a proposal end up in its directory: those are the ones
that don't convert with the other features alone, but do once the proposal is enabled.

## Regenerating

Run on Linux (or under WSL on Windows):

```sh
./process_all.py
```

The script downloads the spec testsuite, the proposal repos and a
[wabt](https://github.com/WebAssembly/wabt) release into `_wast/`, and regenerates `core/`
and `proposals/`. The spec tag and tool versions can be overridden via the `SPEC_TAG`,
`WABT_VERSION` and `WASM_TOOLS_VERSION` environment variables.

The GC tests are converted with
[wasm-tools](https://github.com/bytecodealliance/wasm-tools) `json-from-wast`, since wabt's
text parser doesn't understand GC types yet. Its JSON is modelled on `wast2json`, but is
printed compactly and tags each module with a `module_type` field.
