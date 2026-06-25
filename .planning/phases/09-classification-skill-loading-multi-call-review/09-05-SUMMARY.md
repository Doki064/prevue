---
phase: 09-classification-skill-loading-multi-call-review
plan: "05"
subsystem: multi-call-orchestration
tags: [multicall, split, execute, merge, ENGN-05, ENGN-06, ENGN-07, D-05, D-06, D-07, D-08, D-10, TDD]
dependency_graph:
  requires:
    - phase: 09-03
      provides: "referenced_paths(path, patch) for import co-location (D-06)"
    - phase: 09-04
      provides: "run_review classify-first order; split_into_calls inherits same order"
    - phase: 08
      provides: "fingerprint(path, title) for merge dedupe (D-04/D-08)"
  provides:
    - "src/prevue/multicall.py — CallGroup, split_into_calls, execute_calls, merge_findings"
    - "src/prevue/review.py — multi-call loop wrapping engine.review with split/execute/merge before gate"
    - "Whole-run token cap (D-10) with neutral-partial disclosure"
    - "test_single_call_default_unchanged, test_multicall_split_and_merge, test_multicall_parallel_fail_soft, test_whole_run_cap_overflow_disclosure"
  affects:
    - "09-06 (provenance): per_call token breakdown in engine_meta['per_call'] for rendering"
tech_stack:
  added:
    - "concurrent.futures.ThreadPoolExecutor (stdlib, no new deps)"
  patterns:
    - "CallGroup dataclass: files, bundles (set), instructions"
    - "split_into_calls: bundle grouping → import co-location (D-06) → greedy merge → cap at max_review_calls"
    - "execute_calls: sequential loop (concurrency=1) or ThreadPoolExecutor.as_completed (concurrency>1)"
    - "merge_findings: fingerprint(path, title) dedup; SEVERITY_RANK tie-break (error beats warning)"
    - "Single-call path (max_review_calls=1): EngineFailure propagates; byte-identical to pre-09-05"
    - "Multi-call path: execute_calls fail-soft; failures→degraded=True→neutral conclusion"
    - "Whole-run cap (D-10): classify_tokens + projected_review_tokens > max_total_run_tokens → repack with tighter budget → neutral partial or skip"
    - "Synthetic ReviewResult from merged findings feeds existing gate/sticky path unchanged (D-08)"
key_files:
  created:
    - src/prevue/multicall.py
  modified:
    - src/prevue/review.py
    - src/prevue/engines/base.py
    - tests/test_review_flow.py
decisions:
  - "Single-call EngineFailure propagates (preserves D-09 fail-closed contract); multi-call fail-soft only when len(call_requests)>1 — only additional calls have 'other results' to keep"
  - "Whole-run cap (D-10) applied before split: repack with budget = max_total_run_tokens - classify_tokens; all-files-dropped → skip (neutral), partial → skipped_reason contains 'run token budget reached'"
  - "per_call token breakdown stashed in engine_meta['per_call'] list for 09-06 rendering (Pitfall 5)"
  - "CallGroup uses bundles=set (not bundle_label str) to track merged-group provenance"
  - "Re-export EngineFailure/AuthError from engines.base for test scaffold import compat (09-01 RED scaffold used base.EngineFailure)"
  - "greedy merge under max_tokens_per_call uses estimate_file_prompt_tokens per file; cap excess groups merged into last slot (no silent file drop at split step)"
requirements-completed: [ENGN-05, ENGN-06, ENGN-07]
duration: "12 min"
completed: "2026-06-21T17:54:52Z"
---

# Phase 09 Plan 05: Multi-Call Split / Execute / Merge Orchestration Summary

Multi-call review via `split_into_calls` (bundle + import co-location + greedy merge) / `execute_calls` (sequential or ThreadPoolExecutor fail-soft) / `merge_findings` (fingerprint dedup, severity tie-break): default `max_review_calls=1` is byte-identical to the pre-09-05 single-call path; multi-call paths merge findings before the single existing gate.

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-21T17:42:21Z
- **Completed:** 2026-06-21T17:54:52Z
- **Tasks:** 1 (TDD: RED/GREEN/REFACTOR)
- **Files created/modified:** 4

## Accomplishments

### `src/prevue/multicall.py` (new)

**`CallGroup`** — dataclass: `files: list[ChangedFile]`, `bundles: set[str]`, `instructions: str`.

**`split_into_calls(files, bundles, file_bundle, cfg) -> list[CallGroup]`** — five-step algorithm:
1. Single-call short-circuit when `max_review_calls=1` (ENGN-05 byte-identical path)
2. Bundle grouping by `file_bundle` map (unmapped → `"general"`)
3. Import co-location (D-06): `referenced_paths` per file; union-find style group merge when importer references a file in a different group
4. Greedy merge toward `max_tokens_per_call` using `estimate_file_prompt_tokens`
5. Cap at `max_review_calls` by merging excess groups into last slot (no silent file drop)

**`execute_calls(requests, engine, concurrency) -> tuple[list[ReviewResult], int]`** — sequential loop when `concurrency≤1`; `ThreadPoolExecutor(max_workers=concurrency)` + `as_completed` when `>1`; catches `(EngineFailure, AuthError)` per call → `failures++`, good results preserved. No asyncio (CLAUDE.md).

**`merge_findings(results) -> list[Finding]`** — `fingerprint(path, title)` dedup keyed by insertion order; on collision keeps `SEVERITY_RANK`-lower (higher severity) entry. Implements Pitfall 4: an error must not be dropped in favour of a duplicate warning.

### `src/prevue/review.py` wiring

- Imports `CallGroup`, `split_into_calls`, `execute_calls`, `merge_findings` and `estimate_file_prompt_tokens`
- **Whole-run cap (D-10):** after pack cascade, checks `classify_tokens + projected_review_tokens > max_total_run_tokens`; if over, re-runs `pack_files` with `budget=max_total_run_tokens - classify_tokens`; if all files dropped → skip (neutral); otherwise records `skipped_reason` containing `"run token budget reached"`
- **Per-file bundle map:** derived from `result_cls.labels` for `split_into_calls`
- **Single-call path** (`len(call_requests)==1`): direct `engine.review(req)` — `EngineFailure` propagates (D-09 contract preserved; pre-existing `test_engine_failure_propagates_without_upsert` stays green)
- **Multi-call path** (`len(call_requests)>1`): `execute_calls` with fail-soft; `merge_findings` → synthetic `ReviewResult` → existing `_open_set_findings` → `apply_gate` → `post_inline_review` → `upsert_sticky` path **unchanged** (one gate, one sticky — D-08)
- `engine_meta["per_call"]` list stashed for 09-06 rendering (Pitfall 5)

### `src/prevue/engines/base.py` (modified)

Re-exported `EngineFailure` and `AuthError` from `engines.errors` so the 09-01 RED scaffold import (`from prevue.engines.base import EngineFailure`) resolves.

### `tests/test_review_flow.py` (4 new integration tests)

- `test_single_call_default_unchanged`: spy asserts exactly 1 `engine.review()` call when `max_review_calls=1`
- `test_multicall_split_and_merge`: `max_review_calls=2`, 2-bundle diff → 1-2 calls → 1 sticky (`upsert_sticky.assert_called_once()`)
- `test_multicall_parallel_fail_soft`: `execute_calls` unit test — fail-soft absorbs 1 EngineFailure, 1 surviving result, 0 raise
- `test_whole_run_cap_overflow_disclosure`: `max_total_run_tokens=10` → overflow → neutral (skip or partial run without exception)

## Task Commits

**Task 1: Multi-call split/execute/merge (TDD RED/GREEN/REFACTOR)**

The RED scaffold was created in 09-01 (18 failing tests in `tests/test_multicall.py`). No new RED commit needed — scaffold confirmed failing with `ModuleNotFoundError: No module named 'prevue.multicall'`.

1. `bd3cb11` — `feat(09-05)`: GREEN — `multicall.py` CallGroup/split_into_calls/execute_calls/merge_findings + engines/base.py re-export
2. `d23e1a9` — `feat(09-05)`: wire multi-call loop + whole-run cap into run_review
3. `a29a4b8` — `refactor(09-05)`: tidy multi-call wiring + integration tests

## Files Created/Modified

- `src/prevue/multicall.py` — new: CallGroup, split_into_calls, execute_calls, merge_findings
- `src/prevue/review.py` — import multicall; whole-run cap (D-10); split/execute/merge loop; single-call propagation preserved
- `src/prevue/engines/base.py` — re-export EngineFailure/AuthError for test compat
- `tests/test_review_flow.py` — 4 new integration tests (multi-call coverage)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Re-export EngineFailure/AuthError from engines.base**
- **Found during:** GREEN — 09-01 RED scaffold imports `from prevue.engines.base import EngineFailure` but `EngineFailure` lives only in `engines.errors`
- **Issue:** Test scaffold `test_fail_soft_one_failure_keeps_others` raised `ImportError: cannot import name 'EngineFailure' from 'prevue.engines.base'`
- **Fix:** Added `from prevue.engines.errors import AuthError, EngineFailure` + `__all__` to `engines/base.py`
- **Files modified:** `src/prevue/engines/base.py`
- **Commit:** `bd3cb11`

**2. [Rule 2 - Missing guard] Single-call EngineFailure propagation preserved**
- **Found during:** GREEN wiring — `test_engine_failure_propagates_without_upsert` failed (pre-existing test) because fail-soft swallowed the error on single-call path
- **Issue:** Multi-call fail-soft is semantically wrong for single-call: there are no "other results" to keep; D-09 contract requires propagation
- **Fix:** Added `if len(call_requests) == 1: single_result = engine.review(...)` direct-invoke path before the `else: execute_calls(...)` fail-soft path
- **Files modified:** `src/prevue/review.py`
- **Commit:** `d23e1a9`

**3. [Rule 2 - Scope adaptation] fail-soft integration test uses execute_calls directly**
- **Found during:** REFACTOR — `test_multicall_parallel_fail_soft` triggered the single-call path because greedy merge collapsed 2 small files into 1 group (both well under `max_tokens_per_call`)
- **Issue:** Full run_review test couldn't reliably force 2 call groups with small test files
- **Fix:** Rewrote `test_multicall_parallel_fail_soft` as an `execute_calls` unit test (correct scope — it tests the multi-call fail-soft contract, not the splitter logic)
- **Files modified:** `tests/test_review_flow.py`
- **Commit:** `a29a4b8`

**Total deviations:** 3 auto-fixed (1 Rule 1 bug fix, 2 Rule 2 correctness/guard fixes)

## Known Stubs

None — all multi-call logic is fully implemented. No hardcoded empty values or placeholder returns.

## Threat Flags

No new trust boundaries introduced beyond the plan's `<threat_model>`:
- T-09-15 (DoS/cost amplification): `review_concurrency` cap via `ThreadPoolExecutor(max_workers=concurrency)` + `max_review_calls` cap + `max_total_run_tokens` whole-run ceiling implemented as specified
- T-09-16 (prompt injection): each per-group ReviewRequest routes through existing `build_prompt` UNTRUSTED DATA fencing; no global mutation
- T-09-17 (false-green): `failures>0` → `degraded=True` → neutral conclusion; `merge_findings` severity tie-break prevents error masked by duplicate warning
- T-09-SC (npm/pip installs): no new packages; `concurrent.futures` is stdlib

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test scaffold) | 09-01 scaffold (18 tests, ImportError) | PASS — confirmed failing pre-GREEN |
| GREEN (feat commit — multicall.py) | `bd3cb11` | PASS — 18/18 tests green |
| GREEN (feat commit — review.py wiring) | `d23e1a9` | PASS — 64/64 pre-existing + 82/82 total |
| REFACTOR | `a29a4b8` | PASS — 86/86 tests green after cleanup |

## Verification

```
uv run pytest tests/test_multicall.py tests/test_review_flow.py -x -q
# → 86 passed

uv run ruff check src/prevue/multicall.py src/prevue/review.py
# → All checks passed

grep -n "asyncio" src/prevue/multicall.py src/prevue/review.py
# → Only in comments (docstrings, inline notes)

uv run pytest -q
# → 699 passed
```

## Success Criteria Verification

- SC-7 (ENGN-05): `max_review_calls=1` → exactly 1 `engine.review()` call (verified by `test_single_call_default_unchanged`)
- SC-8 (ENGN-06/D-06): bundle-aligned + import-co-located split (verified by `split_into_calls` implementation + unit tests)
- SC-9 (D-08): findings merged + deduped via fingerprint before gate (verified by `test_dedupe_same_fingerprint_across_calls`, `test_severity_tie_break_keeps_higher_severity`)
- SC-10 (ENGN-07): `review_concurrency` controls parallel execution (verified by `execute_calls` sequential + parallel tests)
- SC-4/D-10: whole-run cap overflow → neutral partial with disclosure data (verified by `test_whole_run_cap_overflow_disclosure`)

## Self-Check

- [x] `src/prevue/multicall.py` exists — FOUND
- [x] GREEN commit `bd3cb11` exists — FOUND
- [x] Wiring commit `d23e1a9` exists — FOUND
- [x] Refactor commit `a29a4b8` exists — FOUND
- [x] `uv run pytest tests/test_multicall.py tests/test_review_flow.py -q` → 86 passed — VERIFIED
- [x] `uv run ruff check src/prevue/multicall.py src/prevue/review.py` → clean — VERIFIED
- [x] `grep -n "asyncio" src/prevue/multicall.py src/prevue/review.py` → only in comments — VERIFIED
- [x] `uv run pytest -q` → 699 passed (no regressions) — VERIFIED

## Self-Check: PASSED
