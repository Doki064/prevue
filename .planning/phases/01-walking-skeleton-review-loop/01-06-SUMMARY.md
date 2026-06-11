---
phase: 01-walking-skeleton-review-loop
plan: 06
subsystem: api
tags: [orchestration, cli, fork-guard, tdd, fail-closed]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: GitHub diff fetch + sticky upsert (Plan 04)
  - phase: 01-walking-skeleton-review-loop
    provides: CopilotCliAdapter engine seam (Plan 05)
provides:
  - run_review() fetch → adapt → post pipeline
  - ForkPrUnsupported guard via PrContext head/base repo compare (SECR-01 runtime)
  - D-09 fail-closed — engine errors propagate before upsert_sticky
  - prevue review CLI entrypoint with exit-code mapping
affects:
  - 01-07 secure workflow wrapper + live E2E

tech-stack:
  added: []
  patterns:
    - "Single load_pr_context() parse for fork guard (no second event read)"
    - "Optional adapter injection for orchestration tests"
    - "CLI maps ForkPrUnsupported → exit 0, EngineFailure/CopilotAuthError → exit 1"

key-files:
  created:
    - src/prevue/review.py
    - tests/test_review_flow.py
    - tests/test_fork_guard.py
    - tests/fixtures/event_pull_request_fork.json
  modified:
    - src/prevue/cli.py

key-decisions:
  - "Fork guard compares ctx.head_repo_full vs ctx.base_repo_full from one PrContext parse"
  - "BASELINE_INSTRUCTIONS module constant until Phase 3 skills replace it"
  - "CLI prints sanitized exception messages only — never tokens (T-05)"

patterns-established:
  - "Orchestration layer owns fork guard + fail-closed; adapter/comments stay pure"
  - "TDD RED→GREEN for orchestration with patched I/O seams"

requirements-completed: [DIFF-01, ENGN-01, ENGN-02, OUTP-01]

duration: 12min
completed: 2026-06-12
---

# Phase 01 Plan 06: Review Orchestration + CLI Summary

**run_review() wires fetch → CopilotCliAdapter → sticky upsert with fork guard and D-09 fail-closed; `prevue review` CLI exposes the loop**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-11T20:02:00Z
- **Completed:** 2026-06-11T20:14:01Z
- **Tasks:** 2 (TDD orchestration + CLI)
- **Files modified:** 5

## Accomplishments

- `run_review()` orchestrates load_pr_context → fork guard → fetch_diff → adapter.review → upsert_sticky
- Fork PRs raise `ForkPrUnsupported` before any fetch/engine/post side effects
- Engine failures propagate without touching sticky comment (D-09)
- `prevue review` subcommand with argparse; fork no-op exits 0, engine errors exit 1
- 3 orchestration tests (happy path, fail-closed, fork guard)

## Task Commits

1. **Task 1 RED: orchestration + fork guard + fail-closed tests** - `88cf673` (test)
2. **Task 1 GREEN: run_review implementation** - `6d85c92` (feat)
3. **Task 2: prevue review CLI entrypoint** - `32739fe` (feat)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `src/prevue/review.py` — `run_review()`, `ForkPrUnsupported`, `BASELINE_INSTRUCTIONS`
- `src/prevue/cli.py` — `main()` with `review` subcommand and exit-code mapping
- `tests/test_review_flow.py` — happy path + D-09 fail-closed tests
- `tests/test_fork_guard.py` — fork early-exit without side effects
- `tests/fixtures/event_pull_request_fork.json` — fork PR event payload

## Decisions Made

- Fork guard uses `PrContext` from single `load_pr_context()` call (D-07 seam)
- `adapter` kwarg on `run_review()` for test injection without mocking subprocess
- SECR-01 workflow trigger + docs deferred to Plan 07; fork guard runtime ships here

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed isinstance check against conftest stub ReviewResult**
- **Found during:** Task 1 GREEN
- **Issue:** `fake_engine` returns conftest stub `ReviewResult`, not `prevue.models.ReviewResult`
- **Fix:** Assert on `summary_markdown` content instead of strict isinstance
- **Files modified:** `tests/test_review_flow.py`
- **Committed in:** `6d85c92`

**2. [Rule 1 - Bug] Fixed fork guard test regex case sensitivity**
- **Found during:** Task 1 GREEN
- **Issue:** `match="fork"` failed on message starting with "Fork"
- **Fix:** Changed to `match="unsupported"`
- **Files modified:** `tests/test_fork_guard.py`
- **Committed in:** `6d85c92`

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Test fixes only; orchestration behavior matches plan.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Walking skeleton spine complete — ready for Plan 07 workflow wrapper + live E2E
- SECR-01 `pull_request` trigger enforcement and fork documentation land in Plan 07

## Self-Check: PASSED

- FOUND: src/prevue/review.py
- FOUND: src/prevue/cli.py
- FOUND: tests/test_review_flow.py
- FOUND: tests/test_fork_guard.py
- FOUND: 88cf673, 6d85c92, 32739fe

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*
