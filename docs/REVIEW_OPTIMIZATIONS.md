# Review fixes and equivalent caching — 2026-09-14

Base: `18adb705823b4e98e322cb4e153b2f313e4c2428`.
Copy all four `lua/tiger_sentence*.lua` files when upgrading. Schemas, plain-text
code tables, model bytes and learning database namespaces do not change.

## Intentional fixes

The unlocked incremental decoder previously assumed a four-key maximum when
invalidating whole-input edges. Five/eight-key custom codes could leak a direct
multi-character candidate and its single-character reward into a segmented path.
The invalidation boundary now uses the loaded maximum code length and trailing
selector span. Numeric-selector backspacing also rebuilds where an edge could
become a whole-input edge. These counterexamples deliberately change to match
fresh decoding; they are not included in an indiscriminate old/new equality claim.

`results_equal` now checks learning inhibition/rewards, full off-menu confidence
candidates, truncation, incomplete-tail flags and path boundaries/fields. Tests
mutate each semantic field independently. A separate process-level probe compares
old and new implementations, so a shared implementation mistake is not hidden
by comparing only the new incremental decoder with its own full decoder.

## Preserved semantics and bounded caches

- Learning keeps its independent full-replay `build` oracle. Path contexts cache
  the original validated text calculation, not an unchecked BOS/prev1 shortcut.
  A byte scanner replaces fragment character-array allocation while preserving
  malformed UTF-8 behavior. Context caches are tied to immutable path text.
- Prefix windows belong to an immutable sorted code vector (weak-key ownership,
  2,048 FIFO entries). The original lower-bound plus 64 *slots*, including an
  equal-code slot, is retained. Prefix-score results belong to one score-index
  epoch (4,096 FIFO entries); different modes, contexts, times and snapshots
  cannot share a stale result. Zero-valued misses are cached too.
- Prefix evidence retains its already-built boundary/text index. Visible path
  membership is indexed once per result generation. Original evidence iteration
  and floating-point accumulation order are unchanged; plain-array callers keep
  the linear fallback.
- The ngram reader is a separate module, instantiated once by the sentence
  module. The existing 8 MiB page LRU, 16,384-entry context caches, model failure
  generation and legacy reader remain. Successor binary search has one shared
  implementation. A per-model 8,192-entry FIFO caches bigram lambda, raw float
  probability and observed status separately. Observed zero is not a missing
  record. No quantization, beam pruning, rank/learning weight changes, altered
  confidence pool or arithmetic reassociation is introduced.

The bounded metadata/query caches add memory; the 8 MiB limit still describes
page bytes, not total Lua memory. All score caches follow their model/epoch
lifetime. The broader lexicon/decoder/frontend split and speculative whole-page
predecoding are deliberately deferred rather than bundled without measured
production-model benefit. No background writer or database migration is added.

## Validation completed locally

System Lua 5.4 shared library in an isolated Linux container; no real librime
or desktop/mobile frontend was available for this local run.

- Original four suites pass (including 23,034 learning checks).
- 33,736 review checks: long/custom codes, selectors, equality negative cases,
  indexed evidence, prefix windows/epochs/eviction, malformed/control/supplementary
  Unicode and compatibility paths.
- 80,986 reader checks against an independent float32-rounded oracle: missing
  contexts/targets, observed-zero records, cached/uncached values, bounded eviction,
  reload and corrupt-header rejection. Synthetic model: 17,480 bytes, SHA-256
  `b50a12fc5292fabbd4841fd61dd7f85cfa6ae9987d1f74aa752287aa6f86862f`.
- Ten functional negative controls are detected. LuaJIT explicitly skips binary
  model tests where string.unpack/utf8 are unavailable; this is not a model pass.
- Independent old/new runs match exactly for 15,128 no-model snapshots and
  15,128 synthetic-TCSKNM02 snapshots (30,256 total). The same probe runs in
  separate processes with frozen time, deterministic inputs, both duplicate
  modes, learning on/off, append, backspace, middle edit, paste, Tab-style locks,
  and same-generation evidence upgrades. Comparison includes full confidence
  pools, path fields and hex-serialized floating-point values.

No-model snapshot SHA-256:
`94b22547e19351f64e3470040226b90f96d4b781a77f632ee683ca7972aec961`.
Synthetic-model snapshot SHA-256:
`c6d63a212786187d5f30e1ba571b661e16aecbf6e231b1e02f69cc3b3f22bf4a`.

The uploaded production model could not be opened in the execution container.
Its real-model difference test, accuracy on labeled text, cold storage/page
behavior and real-device latency are **not** claimed as validated. `--require-model`
requires an explicit readable `--model`; `--mode mobile` now also fails closed
rather than silently benchmarking no-model fallback. CI adds independent
no-model/synthetic comparisons and real-librime preedit/options integration.
CI results should be read from the PR checks, not inferred from local tests.

## Reproduction

```sh
python3 tools/run_regressions.py --lua lua5.4 --negative-control
python3 tools/compare_revisions.py --baseline /path/to/old/tree --lua lua5.4 --report none.json
python3 tools/compare_revisions.py --baseline /path/to/old/tree --lua lua5.4 --fixture --legacy-ranking --report synthetic.json
python3 tools/compare_revisions.py --baseline /path/to/old/tree --lua lua5.4 --model /path/to/sentence-ngram-mobile.bin --require-model --legacy-ranking --report production.json
lua5.4 tools/bench_review_learning.lua /path/to/source/tree 7
```

Run the same benchmark probe alternately against old and new sources. It uses
1,000 in-memory learning records, no model and no LevelDb writes; report warm
prefix-query and decoder-with/without-learning costs separately. GC is forced
outside timing; live-heap end-minus-start is **not** allocation count, GC pause
or total process memory. Shared-container exploratory timings were noisy and
are not a general speedup claim. The production-model benchmark and actual
frontend latency remain required before advertising a user-visible multiplier.
`--legacy-ranking` disables the later compact ranking priors only for this
historical behavior-equivalence check; labeled accuracy tests use current defaults.
