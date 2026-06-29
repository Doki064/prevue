---
phase: 10-boundary-contracts
plan: "03"
subsystem: engines
tags: [perf-03, pricing, usage-capture, tokens, cost-compute, otel, stdout-json, tdd]
dependency_graph:
  requires: [10-01, 10-02]
  provides:
    - "prevue.pricing package (compute_cost + load_pricing_table + model_prices.json)"
    - "prevue.engines.usage.capture_usage per-strategy dispatcher"
    - "flow.py real-token seam with per-engine estimated flag"
  affects:
    - "engine_meta['tokens'] shape extended with input/output/cache/cost_usd/estimated"
    - "test_pricing.py GREEN (8 tests)"
    - "test_usage_capture.py GREEN (7 tests, includes Pitfall 3 regression)"
tech_stack:
  added: []
  patterns:
    - "prevue.pricing package (__init__.py + vendored model_prices.json) — data ships in wheel via uv_build"
    - "functools.lru_cache on zero-arg load_pricing_table() for bundled snapshot"
    - "importlib-free package-relative path: Path(__file__).parent / 'model_prices.json'"
    - "per-strategy capture dispatch on spec.usage_capture literal field"
    - "Pitfall 3 guard: _resolve_fence_source extracts result field for stdout-json engines"
    - "T-10-07 pattern: try/except wraps all JSON/OTEL parse — malformed input → None → fallback"
    - "optional spec= kwarg on review_with_retry preserves backward compat for existing callers"
key_files:
  created:
    - src/prevue/pricing/__init__.py
    - src/prevue/pricing/model_prices.json
    - src/prevue/engines/usage.py
  modified:
    - src/prevue/engines/flow.py
    - src/prevue/engines/tokens.py
    - src/prevue/engines/cli_adapter.py
    - tests/test_usage_capture.py
decisions:
  - "prevue.pricing is a PACKAGE (not pricing.py module file) — JSON data file must live alongside __init__.py in the same directory"
  - "load_pricing_table(path=None): optional path arg covers test injection; zero-arg (cached) for production; no zero-arg call in pytest tests (WARNING 2)"
  - "compute_cost prefers cost_usd from usage dict before recomputing from token counts (Claude total_cost_usd is authoritative)"
  - "capture_usage returns None for 'none' strategy — caller is responsible for bytes/4 estimate + estimated=True label (D-04)"
  - "Pitfall 3 fix: _resolve_fence_source guards against non-JSON stdout gracefully — any exception returns raw_stdout so normal degraded path fires"
  - "spec= kwarg on review_with_retry is optional (None default) — existing test_engine_flow.py callers unaffected, additive change"
  - "OTEL path read from COPILOT_OTEL_FILE_EXPORTER_PATH env inside flow.py post-invoke — WARNING 3 comment added noting Plan 05 wires this"
  - "Pitfall 3 regression test added to test_usage_capture.py — asserts Claude envelope with fenced result yields findings, not degraded"
metrics:
  duration: 13min
  completed: "2026-06-29"
  tasks: 2
  files: 7
requirements_completed: [PERF-03]
---

# Phase 10 Plan 03: Real Token Accounting + Cost Compute (PERF-03) Summary

JWT-style real token capture + dollar-cost computation: Claude stdout-json envelope parsed for exact input/output/cache/total_cost_usd tokens, Copilot OTEL JSONL summed, Cursor/Antigravity honest bytes/4 labeled estimate — all per-engine via a clean strategy dispatch, with a vendored LiteLLM pricing snapshot inside a `prevue.pricing` package and a cache-aware `compute_cost` formula.

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-29T10:35:00Z
- **Completed:** 2026-06-29T10:48:39Z
- **Tasks:** 2
- **Files modified:** 7 (2 new source files, 1 new data file, 3 modified source files, 1 modified test file)

## Accomplishments

### Task 1: prevue.pricing package + pure compute_cost

- Created `src/prevue/pricing/` as a Python package (not a `pricing.py` module) with `__init__.py` and `model_prices.json`
- Vendored the LiteLLM pricing snapshot (2918 models, 1.5 MB, downloaded 2026-06-29 from BerriAI/litellm)
- Implemented `load_pricing_table(path=None)` with optional path injection + `lru_cache` for the bundled zero-arg path
- Implemented `compute_cost(engine, model, usage, override=None, table=None)` with:
  - Cache-aware formula: input + output + cache_read + cache_creation × respective per-token cost fields
  - Prefers `cost_usd` from usage dict verbatim (Claude's `total_cost_usd`) over recomputation
  - D-06c: `engine.pricing` override map shadows table row for matching model
  - Unknown model returns None (no cost, labeled by caller)
  - `table=` parameter injectable so pytest tests use the 4-model sample fixture (WARNING 2 compliance)
- No network imports in `src/prevue/pricing/` (T-10-06 mitigated; grep gate clean)
- `model_prices.json` ships in wheel automatically via `uv_build` (verified with zipfile check)
- All 8 `test_pricing.py` tests GREEN

### Task 2: per-strategy usage capture + flow seam

- Created `src/prevue/engines/usage.py` with `capture_usage(spec, stdout, otel_path)`:
  - `stdout-json`: parses Claude envelope `usage` block → real input/output/cache_read/cache_creation tokens + `total_cost_usd` as `cost_usd`, `estimated=False`
  - `otel-jsonl`: reads + sums Copilot OTEL JSONL spans via `llm.usage.{prompt_tokens,completion_tokens,cache_read_tokens}` attributes, `estimated=False`; gracefully returns None when `otel_path` unset/empty/missing (WARNING 3 — Plan 05 wires the env)
  - `none`: always returns None → caller bytes/4 estimate with `estimated=True`
  - T-10-07: all JSON/OTEL parse paths wrapped in try/except — malformed output degrades to None
  - T-10-08: only numeric token fields + cost_usd captured, raw stdout never stored in engine_meta
- Modified `src/prevue/engines/flow.py` `review_with_retry`:
  - Added optional `spec=` kwarg (None default — preserves backward compat for all existing callers)
  - Calls `capture_usage(spec, raw_stdout, otel_path)` after each invocation
  - Extends `engine_meta["tokens"]` with real fields when capture returns a dict (input/output/cache_read/cache_creation/cost_usd/estimated)
  - Falls back to bytes/4 estimate with `estimated=True` when capture returns None
  - Pitfall 3 fix: `_resolve_fence_source()` for stdout-json engines extracts the `result` field from the Claude envelope before running `extract_json_fence` — guards against non-JSON stdout by falling back to raw stdout path
- Modified `src/prevue/engines/cli_adapter.py`: passes `spec=self._spec` to `review_with_retry`
- Modified `src/prevue/engines/tokens.py`: updated docstring to label `estimate_tokens` as the explicit labeled fallback
- Extended `tests/test_usage_capture.py`: added `test_claude_stdout_json_fence_extraction_pitfall3` — asserts a Claude stdout-json envelope with a fenced `result` yields ≥1 finding (not degraded) + `estimated=False` + real token counts
- All 7 `test_usage_capture.py` tests GREEN; `test_engine_flow.py` + `test_engine_contract.py` GREEN (additive change)

## Task Commits

1. **Task 1: Vendor pricing snapshot as a package + pure compute_cost** - `6f2bd40` (feat)
2. **Task 2: Per-strategy usage capture + flow seam** - `314a7fb` (feat)

## Files Created/Modified

- `src/prevue/pricing/__init__.py` — package surface: `load_pricing_table` + `compute_cost`; source URL + pin date comment
- `src/prevue/pricing/model_prices.json` — vendored LiteLLM pricing snapshot (2918 models, 2026-06-29)
- `src/prevue/engines/usage.py` — `capture_usage` strategy dispatcher + `_parse_stdout_json` + `_parse_copilot_otel`
- `src/prevue/engines/flow.py` — `review_with_retry` extended with `spec=` kwarg, `capture_usage` integration, `_resolve_fence_source` Pitfall 3 guard
- `src/prevue/engines/tokens.py` — docstring updated: labeled fallback, not primary accounting path
- `src/prevue/engines/cli_adapter.py` — `review()` passes `spec=self._spec` to flow
- `tests/test_usage_capture.py` — Pitfall 3 regression test added

## Verification Results

- `uv run pytest tests/test_usage_capture.py tests/test_pricing.py tests/test_engine_flow.py tests/test_engine_contract.py -x -q` — 54 passed
- `uv run pytest -q` — 761 passed, 23 failed (all pre-existing RED tests from Plan 01 for Plans 04-05)
- `grep -REq 'requests|urlopen|httpx|urllib.request' src/prevue/pricing/` — CLEAN (T-10-06)
- `test -f src/prevue/pricing/__init__.py && ! test -f src/prevue/pricing.py` — PASS
- `uv run python -c "import prevue.pricing as p; t=p.load_pricing_table(); assert len(t)>50; print(len(t))"` — 2918
- `uv run python -c "from prevue.pricing import compute_cost; print(compute_cost('x','no-such-model',{'input':10,'output':10}))"` — None
- `uv run ruff check . && uv run ruff format --check .` — CLEAN

## Deviations from Plan

None — plan executed exactly as written. Minor implementation decisions:

- `load_pricing_table` uses `Path(__file__).parent / "model_prices.json"` (not `importlib.resources.files()`) — both are valid per the plan; the `Path(__file__)` approach is simpler and correct under `uv_build`'s layout.
- The Pitfall 3 test used `make_sample_request()` from `engine_helpers.py` for the `ReviewRequest` (not a hand-built dict) since `ReviewRequest.diff` requires a `DiffBundle` model.

## Threat Flags

No new threat surface introduced beyond what the threat model covers:

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-10-06 | src/prevue/pricing/\* | No network imports; data read from package-dir JSON only |
| mitigated: T-10-07 | src/prevue/engines/usage.py | try/except on all JSON/OTEL parse → None fallback |
| mitigated: T-10-08 | src/prevue/engines/usage.py | Only numeric fields captured; raw stdout not stored |
| mitigated: T-10-SC | src/prevue/pricing/model_prices.json | One-time vendoring commit; no new pip packages |

## Known Stubs

None — all token capture strategies are wired. Copilot OTEL is deliberately None-returning until Plan 05 wires `COPILOT_OTEL_FILE_EXPORTER_PATH` into the workflow (this is a documented cross-wave dependency, WARNING 3, not a stub — it falls back correctly to `estimated=True`).

## Self-Check

Files exist:
- src/prevue/pricing/__init__.py: FOUND
- src/prevue/pricing/model_prices.json: FOUND
- src/prevue/engines/usage.py: FOUND
- src/prevue/engines/flow.py: FOUND (modified)
- src/prevue/engines/tokens.py: FOUND (modified)
- src/prevue/engines/cli_adapter.py: FOUND (modified)
- tests/test_usage_capture.py: FOUND (extended)

Commits exist: 6f2bd40, 314a7fb

## Self-Check: PASSED

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-29*
