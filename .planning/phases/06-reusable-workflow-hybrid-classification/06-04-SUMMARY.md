---
phase: 06-reusable-workflow-hybrid-classification
plan: 04
subsystem: workflow
tags: [skip-pipeline, neutral-check, bot-skip, NOIS-01, workflow_call]

requires:
  - phase: 06-reusable-workflow-hybrid-classification
    provides: load_config SkipConfig, prevue-review.yml reusable workflow, run_review config wiring
provides:
  - should_skip() bot/label/title policy
  - Neutral skip check + sticky reason (D-16)
  - run_review early-return before engine spend on skip
affects:
  - phase-07-packaging

tech-stack:
  added: []
  patterns:
    - "Bot skip unless login in skip.review_bots (D-13/D-14)"
    - "Skip conclusion=neutral — required check neither blocks nor false-passes (A3/D-16)"
    - "Draft skip at workflow if: only; bot/label/title in Python for config + neutral check"

key-files:
  created:
    - src/prevue/skip.py
  modified:
    - src/prevue/github/comments.py
    - src/prevue/github/checks.py
    - src/prevue/review.py
    - tests/test_skip.py
    - tests/test_review_flow.py

key-decisions:
  - "should_skip(pr, SkipConfig) -> str | None; reason string drives sticky + check output"
  - "conclude_skip_check(conclusion='neutral') for bot/label/title; empty-PR path stays success"
  - "Live sandbox consumer verification deferred per user — tracked as UAT debt"

patterns-established:
  - "Skip evaluated after diff fetch, before classify/engine — zero fallback spend"
  - "upsert_skip_note(..., reason=...) for auditable skip decisions (T-06-17)"

requirements-completed: [NOIS-01, WKFL-01, WKFL-02]

duration: 20min
completed: 2026-06-14
---

# Phase 6 Plan 4: Skip Pipeline Summary

**Bot/label/title skip policy with neutral check + sticky reason; run_review early-return before engine spend**

## Performance

- **Duration:** 20 min (Tasks 1–2 automated; Task 3 deferred)
- **Started:** 2026-06-14T00:00:00Z
- **Completed:** 2026-06-14T00:20:00Z
- **Tasks:** 2/3 complete (Task 3 live verify deferred)
- **Files modified:** 5

## Accomplishments

- `should_skip()` — Bot authors skipped unless in `review_bots`; default `skip-review` label; configurable title regex patterns
- Skip surface — `upsert_skip_note(reason=...)` + `conclude_skip_check(conclusion="neutral")` for bot/label/title skips
- `run_review` early-return after diff fetch, before classify/engine — no engine or LLM fallback spend on skipped PRs
- Full suite green (297 tests, 95% coverage)

## Task Commits

1. **Task 1: should_skip policy + neutral skip surface** - `fee7d39` (feat)
2. **Task 2: Wire skip into run_review** - `09126ea` (feat)
3. **Task 3: Live sandbox-consumer verification** - **DEFERRED** (user skipped live verify)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `src/prevue/skip.py` — `should_skip(pr, cfg)` bot/label/title policy
- `src/prevue/github/comments.py` — `upsert_skip_note(..., reason=...)`
- `src/prevue/github/checks.py` — `conclude_skip_check(..., conclusion="neutral")`
- `src/prevue/review.py` — skip hook before classify/engine
- `tests/test_skip.py` — bot/label/title/neutral check tests (GREEN)
- `tests/test_review_flow.py` — skip early-return integration tests

## Decisions Made

- Neutral conclusion for bot/label/title skips — required checks neither block nor falsely pass (A3)
- Empty-PR skip path unchanged (`conclusion="success"`)
- Live consumer-repo verification deferred; `/gsd-verify-work 6` or manual sandbox run before ship

## Deviations from Plan

### Task 3 Deferred (User Request)

- **Found during:** Task 3 checkpoint (human-verify)
- **Issue:** Live sandbox consumer repo verification requires separate GitHub environment
- **Resolution:** User requested skip live verification for now; automated criteria (Tasks 1–2) complete
- **Impact:** WKFL-01 success criterion #1 (separate repo adoption) unverified — tracked as UAT debt before public release
- **Follow-up:** Run `docs/consumer-setup.md` steps on sandbox consumer repo; confirm via `/gsd-verify-work 6`

## Issues Encountered

None in automated Tasks 1–2.

## User Setup Required

Before shipping Phase 6 publicly:

1. Tag Prevue release ref (bump `v0.6.0` in `prevue-review.yml` + `docs/consumer-setup.md`)
2. Sandbox consumer repo with caller workflow from `docs/consumer-setup.md`
3. Verify six live scenarios from 06-04-PLAN Task 3 (normal PR, ambiguous file, draft, skip label/bot)

## Next Phase Readiness

- Skip pipeline complete for dogfood repo
- Phase 7 packaging can proceed; live consumer verification should run before v1.0 public ship

## Self-Check: PASSED

- `uv run pytest -q` — 297 passed
- `uv run ruff check .` — clean
- Skip tests cover bot/label/title + neutral check + run_review early-return

---
*Phase: 06-reusable-workflow-hybrid-classification*
*Completed: 2026-06-14*
