---
phase: 04-structured-findings-merge-gate
plan: 05
subsystem: api
tags: [pygithub, check-run, merge-gate, github-actions, gate]

requires:
  - phase: 04-02
    provides: Engine JSON parsing with retry-then-degrade (ENGN-03)
  - phase: 04-03
    provides: Gate policy pipeline — apply_gate, load_review_config, position validity
  - phase: 04-04
    provides: Batched inline review POST, gate-aware sticky, uniform template

provides:
  - prevue/review check run on PR head SHA (success/neutral/failure)
  - conclude_skip_check for all-filtered PRs
  - Full run_review post-engine pipeline wired end-to-end
  - checks:write workflow permission pinned by test

affects:
  - phase-05-reusable-workflow
  - branch-protection merge gates

tech-stack:
  added: []
  patterns:
    - "Single completed-only create_check_run — no in_progress dangling check"
    - "Write order: inline review → sticky → check (check links to sticky)"
    - "head_sha from DiffBundle.head_sha, never GITHUB_SHA"

key-files:
  created:
    - src/prevue/github/checks.py
  modified:
    - src/prevue/github/client.py
    - src/prevue/review.py
    - .github/workflows/review.yml
    - tests/test_review_flow.py
    - tests/test_workflow_yaml.py

key-decisions:
  - "Single completed-only check run — avoids dangling in_progress on engine hard-fail"
  - "load_review_config before fetch_diff — D-16 fail-closed before engine spend"
  - "Fork PR creates no check — absence holds required checks pending (D-09)"

patterns-established:
  - "Check output mirrors gate.py verdict helpers — D-07 single source of truth"
  - "Minimal permissions exact-equality test pins checks:write without scope creep"

requirements-completed: [OUTP-03, OUTP-02, ENGN-03, NOIS-03]

duration: 20min
completed: 2026-06-13
---

# Phase 4 Plan 5: Check-run merge gate + pipeline wiring Summary

**`prevue/review` check run on PR head SHA with full post-engine pipeline — inline → sticky → check — and `checks:write` permission pinned**

## Performance

- **Duration:** 20 min
- **Started:** 2026-06-13T04:33:00Z
- **Completed:** 2026-06-13T04:53:18Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `conclude_review_check` / `conclude_skip_check` post single completed check runs using gate verdict helpers (D-08/D-09/D-10)
- `run_review()` wires config → gate → inline review → sticky → check with all edge states (degraded neutral, skip success, fork no-op, engine hard-fail no check)
- Workflow gains `checks: write`; `test_minimal_permissions` pins exact minimal block
- Full suite 205 tests green, zero ignores

## Task Commits

Each task was committed atomically:

1. **Task 1: get_repo + checks.py GREEN (D-08/D-09/D-10)** - `b16a449` (feat)
2. **Task 2: run_review post-engine stage + edge states** - `0e17302` (feat)
3. **Task 3: checks:write permission + workflow test + suite gate** - `0623008` (feat)

## Files Created/Modified

- `src/prevue/github/checks.py` — CHECK_NAME, conclude_review_check, conclude_skip_check, _render_check_output
- `src/prevue/github/client.py` — get_repo() for repo-scoped Checks API
- `src/prevue/review.py` — Full post-engine pipeline with edge-state handling
- `.github/workflows/review.yml` — checks: write permission
- `tests/test_review_flow.py` — Pipeline assertions: call order, gate kwarg, edge states
- `tests/test_workflow_yaml.py` — Updated minimal permissions assertion

## Decisions Made

- Single completed-only `create_check_run` — no in_progress pre-create (avoids dangling check on engine hard-fail between calls)
- `load_review_config()` immediately after `load_ruleset()`, before `fetch_diff` — D-16 fail-closed
- `post_inline_review` return value ignored in v1 per 04-04 discretion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Finding line number in test fixture**
- **Found during:** Task 2 (findings-bearing flow test)
- **Issue:** Test used line=2 but unidiff parsed patch yields RIGHT line 1 only — gate.inline empty
- **Fix:** Changed Finding line to 1 in FindingsEngine test fixture
- **Files modified:** tests/test_review_flow.py
- **Committed in:** 0e17302

None other — plan executed as written.

## Issues Encountered

- Pre-existing ruff E501/I001 in `tests/test_copilot_adapter.py` and `tests/test_positions.py` — out of scope; task-modified files pass ruff clean

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 4 goal TRUE on unit/integration tests; live UAT on sandbox PR recommended (inline comments, check in merge box, degraded neutral observable)
- Phase 5 can package reusable workflow with consumer config threading `load_review_config(consumer_path)`

## Self-Check: PASSED

- FOUND: src/prevue/github/checks.py
- FOUND: b16a449
- FOUND: 0e17302
- FOUND: 0623008

---
*Phase: 04-structured-findings-merge-gate*
*Completed: 2026-06-13*
