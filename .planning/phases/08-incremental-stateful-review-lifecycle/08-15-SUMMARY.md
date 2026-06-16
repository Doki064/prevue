---
phase: 08-incremental-stateful-review-lifecycle
plan: 15
subsystem: api
tags: [github, issue_comment, commands, dismiss, force_full, authorization]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: parse_command + load_comment_context + authorize_commenter (08-14)
provides:
  - run_command authorize-first /prevue dispatcher (review/dismiss/resolve)
  - run_review force_full escape hatch (D-17)
  - create_dismiss_entry guard-1 suppress-list writes
  - prevue command CLI subcommand
affects: [08-16]

tech-stack:
  added: []
  patterns:
    - "Authorize-first command dispatch before parse or engine"
    - "force_full sets marker_for_scope=None to bypass same-SHA noop"
    - "Dismiss sticky persist via merged body + _upsert_marker_comment"
    - "Lazy imports in dismiss.py to avoid comments circular import"

key-files:
  created: []
  modified:
    - src/prevue/commands.py
    - src/prevue/dismiss.py
    - src/prevue/review.py
    - src/prevue/cli.py
    - tests/test_commands.py
    - tests/test_review_flow.py

key-decisions:
  - "run_review accepts optional pr_ctx so command path works on issue_comment events without touching load_pr_context"
  - "Dismiss persistence merges render_dismiss_block into existing sticky via _upsert_marker_comment instead of upsert_sticky with synthetic ReviewResult"

patterns-established:
  - "Command path: load_comment_context → authorize → fork guard → parse → dispatch"
  - "Guard-1 dismiss: derive_prior_findings match by fingerprint or thread_id before write"

requirements-completed: [LIFE-03, LIFE-05]

duration: 18min
completed: 2026-06-16
---

# Phase 08 Plan 15: /prevue Command Surface Summary

**Authorize-first `/prevue` dispatcher with force-full review escape hatch and guard-1 dismiss suppress-list creation**

## Performance

- **Duration:** 18 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `run_command` gates write access first, refuses fork PRs, parses body, dispatches review/dismiss/resolve
- `run_review(force_full=True)` bypasses same-SHA noop and resets marker to head
- `create_dismiss_entry` enforces finding-exists + error-reason guards; persists bounded suppress-list
- `prevue command` CLI subcommand wired with same error handling as `prevue review`

## Task Commits

1. **Task 1: force_full review path + run_command dispatcher skeleton** - `0d7ce4a` (feat)
2. **Task 2: dismiss creation guard 1 + resolve passthrough** - `41209ca` (feat)

## Files Created/Modified

- `src/prevue/review.py` - `force_full` flag, optional `pr_ctx` for command path
- `src/prevue/commands.py` - `run_command` dispatcher + dismiss/resolve handlers
- `src/prevue/dismiss.py` - `create_dismiss_entry` guard-1 creation + sticky merge persist
- `src/prevue/cli.py` - `prevue command` subcommand
- `tests/test_commands.py` - dispatch, dismiss_create, resolve tests
- `tests/test_review_flow.py` - `test_force_full_runs_engine_on_unchanged_head_and_resets_marker`

## Decisions Made

- Optional `pr_ctx` on `run_review` keeps `load_pr_context` untouched while allowing issue_comment workflow to drive review
- Dismiss-only sticky updates merge dismiss block into existing body rather than regenerating full sticky from empty ReviewResult

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `pr_ctx` parameter to `run_review`**
- **Found during:** Task 1
- **Issue:** Command workflow uses issue_comment events; `load_pr_context()` would KeyError on missing `pull_request`
- **Fix:** `run_command` passes `PrContext` derived from `CommentContext` into `run_review(pr_ctx=...)`
- **Files modified:** `src/prevue/review.py`, `src/prevue/commands.py`
- **Committed in:** `0d7ce4a`, `41209ca`

**2. [Rule 3 - Blocking] Lazy imports in `dismiss.py`**
- **Found during:** Task 2
- **Issue:** Top-level import from `github.comments` caused circular import with `DismissEntry`
- **Fix:** Import `derive_prior_findings` / `_upsert_marker_comment` inside `create_dismiss_entry`
- **Files modified:** `src/prevue/dismiss.py`
- **Committed in:** `41209ca`

**3. [Rule 2 - Missing Critical] Sticky dismiss persist via body merge**
- **Found during:** Task 2
- **Issue:** `upsert_sticky` requires full `ReviewResult`; dismiss-only path would overwrite sticky verdict/review sections
- **Fix:** Merge `render_dismiss_block` into existing sticky body, persist with `_upsert_marker_comment`
- **Files modified:** `src/prevue/dismiss.py`
- **Committed in:** `41209ca`

---

**Total deviations:** 3 auto-fixed (2 Rule 2, 1 Rule 3)
**Impact on plan:** All necessary for correctness; no scope creep.

## Issues Encountered

None beyond deviations above.

## User Setup Required

None — 08-16 ships the `issue_comment` workflow.

## Next Phase Readiness

- Python command surface complete for 08-16 workflow + §L7 security checkpoint
- Live verification of write-gate, fork refusal, dismiss guard-1 remains in 08-16 checkpoint

## Self-Check: PASSED

- FOUND: src/prevue/commands.py (run_command)
- FOUND: src/prevue/dismiss.py (create_dismiss_entry)
- FOUND: src/prevue/review.py (force_full)
- FOUND: src/prevue/cli.py (command subcommand)
- FOUND: .planning/phases/08-incremental-stateful-review-lifecycle/08-15-SUMMARY.md
- FOUND: commit 0d7ce4a
- FOUND: commit 41209ca
- pytest: 568 passed

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-16*
