---
quick_id: 260706-g0e
subsystem: engines
tags: [copilot-cli, otel, retry, jq, docs]

provides:
  - Distinct per-attempt OTEL export paths for Copilot first+retry invocations (WR-T11)
  - Degrade-path isolation so a later call's makedirs OSError can't over-count an
    earlier call's real OTEL spans (WR-T12)
  - Single documented `_build_copilot_otel_path` helper replacing inline path logic (WR-T13)
  - Accurate flow.py comments describing per-attempt-path OTEL accumulation (IN-T04)
  - Automated coverage of update-pricing.yml's jq idempotency filter (WR-T04)
  - Current CliEngineSpec + get_adapter() docs, dead per-engine adapter-class
    references removed (WR-T05)
affects: [10-boundary-contracts]

key-files:
  created: []
  modified:
    - src/prevue/engines/cli_adapter.py
    - src/prevue/engines/flow.py
    - tests/test_copilot_adapter.py
    - tests/test_reusable_workflow_yaml.py
    - docs/DEVELOPMENT.md
    - docs/TESTING.md

key-decisions:
  - "_build_copilot_otel_path nests each attempt under its own fresh subdirectory (base_dir/<uuid>/<uuid>.jsonl) instead of a flat base_dir/<uuid>.jsonl sibling, so the OSError-degrade fallback's directory-level glob can never pick up another call's real span (WR-T12)"
  - "otel_accumulates now requires retry_otel_path == otel_path (not just usage_capture == otel-jsonl) — production's two distinct per-attempt paths correctly sum first+retry captures instead of discarding the first"

duration: ~15min
completed: 2026-07-06
---

# Quick Task 260706-g0e: Fix actionable Phase 10 Thermos re-review findings Summary

**Copilot first/retry invocations now get distinct, never-pre-created OTEL export paths (each nested under its own subdirectory), closing both the retry-degrades-to-estimate gap (WR-T11) and the makedirs-OSError sibling-span over-count (WR-T12); plus jq idempotency test coverage and doc cleanup for the deleted per-engine adapter classes.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-06T11:58Z
- **Tasks:** 4/4 completed
- **Files modified:** 6

## Accomplishments

- Extracted `_build_copilot_otel_path(base_dir)` helper in `cli_adapter.py`: builds a fresh per-attempt subdirectory (`base_dir/<uuid>/<uuid>.jsonl`), never pre-creating the leaf file, degrading to `None` on `OSError` (WR-T13).
- `review()` now calls the helper twice (once per attempt) and threads a per-attempt env closure into `flow.review_with_retry` via new `retry_otel_path` kwarg — first and retry Copilot subprocess invocations each get their own OTEL path, so a real retry capture is no longer silently discarded (WR-T11).
- `flow.py`'s `_otel_accumulates` now additionally requires `retry_otel_path == otel_path` — production's distinct per-attempt paths correctly sum both real captures via the existing `_retry_token_meta`/`_sum_real_token_fields` path; the legacy shared-path test model (both `test_engine_flow.py` OTEL tests) is unaffected since `retry_otel_path` defaults to `otel_path` when not passed.
- Nested subdirectory layout means a later call's `makedirs` OSError degrade (falling back to reading the job-wide top-level dir) can no longer accidentally glob-match an earlier call's real nested span file — isolating WR-T12 without touching the accepted fail-open degrade design itself.
- Updated the two stale OTEL comments (`_merge_retry_tokens` block, `_otel_capture_grew` docstring) to state accumulation only holds when first+retry reuse the identical path (IN-T04).
- Added two regression tests to `TestOtelPerCallIsolation`: distinct-path real-capture summing (WR-T11) and sibling-span degrade isolation (WR-T12).
- Added `test_update_pricing_jq_idempotency_empty_and_existing_pr` to `test_reusable_workflow_yaml.py`, regex-extracting the real `--jq` filter from `update-pricing.yml` and exercising both the empty and populated `gh pr list` JSON shapes via `jq` subprocess calls (WR-T04).
- Rewrote `docs/DEVELOPMENT.md`'s "Adding an engine adapter" section and fixed two dead-import code examples in `docs/TESTING.md` to describe the current `CliEngineSpec` + `get_adapter()` pattern, removing all references to the deleted per-engine adapter subclasses (WR-T05).
- Full `scripts/ci-local.sh` gate passed: 838 tests green (835 existing + 3 new), `ruff check`/`format --check` clean, `actionlint` clean, `zizmor` clean (no code changes needed for this task).

## Task Commits

1. **Task 1: OTEL retry/degrade accounting** - `815a884` (fix)
2. **Task 2: update-pricing.yml jq idempotency test** - `9b37ab8` (test)
3. **Task 3: Update stale dev docs** - `fd1aecb` (docs)
4. **Task 4: Full CI-local gate** - verification-only, no commit (all checks passed as-is)

## Files Created/Modified

- `src/prevue/engines/cli_adapter.py` - `_build_copilot_otel_path` helper; `review()` builds two per-attempt OTEL paths and a per-attempt env closure
- `src/prevue/engines/flow.py` - `retry_otel_path` param on `review_with_retry`; `_otel_accumulates` gated on path equality; retry capture reads `retry_otel_path`; updated comments
- `tests/test_copilot_adapter.py` - two new regression tests in `TestOtelPerCallIsolation`
- `tests/test_reusable_workflow_yaml.py` - `UPDATE_PRICING_WORKFLOW` constant + new jq idempotency test
- `docs/DEVELOPMENT.md` - "Adding an engine adapter" section rewritten for `CliEngineSpec`
- `docs/TESTING.md` - two code examples updated to `get_adapter("copilot-cli")`

## Deviations from Plan

None — plan executed exactly as written. Task 4 (full CI-local gate) surfaced no failures to fix.

## Verification Results

- `uv run pytest tests/test_copilot_adapter.py tests/test_engine_flow.py tests/test_usage_capture.py -x -q` — 66 passed
- `uv run pytest tests/test_reusable_workflow_yaml.py -x -q` — 26 passed
- `grep -rn "CopilotCliAdapter\|from prevue.engines.copilot_cli\|class MyEngineAdapter(EngineAdapter)" docs/DEVELOPMENT.md docs/TESTING.md` — zero matches
- `grep -n "CliEngineSpec\|get_adapter" docs/DEVELOPMENT.md docs/TESTING.md` — matches found in both files
- `scripts/ci-local.sh` — passed end-to-end: 838 pytest passed (90% coverage), ruff check clean, ruff format clean, actionlint clean, zizmor clean (0 findings)

## Self-Check: PASSED

- FOUND: src/prevue/engines/cli_adapter.py
- FOUND: src/prevue/engines/flow.py
- FOUND: tests/test_copilot_adapter.py
- FOUND: tests/test_reusable_workflow_yaml.py
- FOUND: docs/DEVELOPMENT.md
- FOUND: docs/TESTING.md
- FOUND commit 815a884
- FOUND commit 9b37ab8
- FOUND commit fd1aecb
