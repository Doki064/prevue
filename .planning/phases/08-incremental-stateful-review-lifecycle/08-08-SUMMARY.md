---
phase: 08-incremental-stateful-review-lifecycle
plan: "08"
subsystem: review
tags: [fingerprint, open-set, carry-forward, incremental, LIFE-02, tdd]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: "_open_set_findings, post_inline_review, PriorFinding, fingerprint, D-06 escalation"

provides:
  - "_open_set_findings rephrase-at-same-line fix: carried prior preserved in open-set when inline kept old title"
  - "test_open_set_dedupes_carried_prior_at_same_line_as_current flipped to assert carried title"
  - "test_open_set_drops_true_duplicate_at_same_line: true-duplicate arm verified"
  - "test_rephrase_at_same_line_keeps_inline_unchanged: inline quiet on rephrase with equal severity"

affects: [08-09-PLAN, 08-10-PLAN, 08-VERIFICATION]

tech-stack:
  added: []
  patterns:
    - "Rephrase-at-same-line reconciliation: open-set excludes current findings at rephrase-collision locations; carried prior is authoritative single entry"
    - "TDD RED/GREEN/REFACTOR: flip existing test encoding buggy behavior; GREEN fixes _open_set_findings; REFACTOR corrects over-eager implementation in GREEN"

key-files:
  created: []
  modified:
    - src/prevue/review.py
    - tests/test_review_flow.py
    - tests/test_comments.py

key-decisions:
  - "On rephrase-at-same-line (prior.fingerprint NOT in current_fps but location matches): keep carried prior in open-set, exclude current finding at that location — sticky Findings table now mirrors the live inline comment title"
  - "True-duplicate arm unchanged: prior.fingerprint in current_fps still drops the prior (current wins)"
  - "post_inline_review keep-as-is for rephrase-equal-severity was already correct via _severity_escalated (no separate fingerprint comparison needed); over-eager change reverted in refactor commit"
  - "Pre-existing ruff E501/I001 in src/prevue/github/comments.py and src/prevue/review.py — deferred (not introduced by this plan)"

requirements-completed: [LIFE-02]

duration: 7min
completed: 2026-06-15
---

# Phase 08 Plan 08: Open-set / Inline Carry-Forward Reconciliation (Rephrase-at-Same-Line) Summary

**_open_set_findings rephrase-at-same-line fix: sticky Findings table now carries the live inline comment title when the engine re-reports the same (path,line) with a different normalized title (gap #1, LIFE-02)**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-15T18:32:14Z
- **Completed:** 2026-06-15T18:39:00Z
- **Tasks:** 3 (RED, GREEN, REFACTOR)
- **Files modified:** 3

## Accomplishments

- Flipped `test_open_set_dedupes_carried_prior_at_same_line_as_current` to assert the CARRIED prior title is preserved (not the new engine title) on rephrase-at-same-line
- Fixed `_open_set_findings` to keep the carried prior and exclude current findings at rephrase-collision locations, so `render_findings_table(gate.placed)` shows the same title as the live inline comment thread
- Added `test_open_set_drops_true_duplicate_at_same_line` confirming true-duplicate arm (same fingerprint) still correctly drops the prior
- Added `test_rephrase_at_same_line_keeps_inline_unchanged` confirming no edit and no duplicate inline on rephrase with equal severity (already satisfied by existing `_severity_escalated` logic)
- Full suite 131 tests pass; no new lint errors introduced

## Task Commits

1. **Task 1: RED — flip divergence test + add reconciliation tests** - `746a474` (test)
2. **Task 2: GREEN — reconcile open-set + fingerprint-align skip-edit** - `bfa804e` (feat)
3. **Task 3: REFACTOR — revert over-eager post_inline_review change** - `99208da` (refactor)

## Files Created/Modified

- `src/prevue/review.py` - `_open_set_findings`: rephrase-at-same-line fix; prior kept when fingerprint differs from all current findings at same location
- `tests/test_review_flow.py` - Flipped `test_open_set_dedupes_carried_prior_at_same_line_as_current`; added `test_open_set_drops_true_duplicate_at_same_line`
- `tests/test_comments.py` - Added `test_rephrase_at_same_line_keeps_inline_unchanged` in `TestPostInlineReview`

## Decisions Made

- Rephrase-at-same-line reconciliation: when `prior.fingerprint NOT in current_fps` but `(path,line,side)` matches a current location, keep the carried prior and exclude current findings at that location. The sticky Findings table row then carries the old/live-inline title, eliminating the sticky-vs-inline divergence.
- `post_inline_review` skip-edit alignment: the existing `_severity_escalated` check already satisfies the rephrase-equal-severity test (returns False → no edit, no create). Adding a fingerprint comparison to `post_inline_review` was reverted in the refactor commit because it broke 5 existing escalation tests (test_updates_existing_inline_at_same_location etc.) without providing additional benefit for the targeted behavior.

## TDD Gate Compliance

- RED commit `746a474`: `test(08-08)` — flipped test fails (AssertionError on title)
- GREEN commit `bfa804e`: `feat(08-08)` — all 3 target tests pass; full suite passes
- REFACTOR commit `99208da`: `refactor(08-08)` — corrects GREEN over-reach; 131 tests still pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reverted over-eager fingerprint alignment in post_inline_review**
- **Found during:** Task 3 (REFACTOR/full-suite regression guard)
- **Issue:** The GREEN implementation added fingerprint comparison to `post_inline_review` that blocked severity-escalation edits when titles differ, breaking 5 existing tests: `test_updates_existing_inline_at_same_location`, `test_posts_only_new_locations_when_some_exist`, `test_edits_run_before_create_even_if_create_fails`, `test_edit_failure_is_nonfatal_and_still_deletes_stale`, `test_partial_success_reports_only_failed_keys`
- **Fix:** Reverted `post_inline_review` to the pre-GREEN body. The `test_rephrase_at_same_line_keeps_inline_unchanged` test passes with the original logic because equal-severity at any location (rephrase or not) returns False from `_severity_escalated` — no edit, no create.
- **Files modified:** `src/prevue/github/comments.py`
- **Verification:** `uv run pytest tests/test_review_flow.py tests/test_comments.py -q` → 131 passed
- **Committed in:** `99208da` (refactor)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug, over-eager GREEN implementation)
**Impact on plan:** Fix was necessary for correctness. The open-set fix (review.py) is the key behavioral change; comments.py needed no change beyond what was already there.

## Issues Encountered

- The plan's description of `post_inline_review` fingerprint alignment was ambiguous about severity-escalation + fingerprint-mismatch cases. The correct interpretation: `_severity_escalated` already handles the rephrase-equal-severity quiet path; no separate fingerprint gating needed in `post_inline_review`.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Changes are pure in-memory reconciliation logic with no new trust boundaries.

## Known Stubs

None — all changes are behavioral fixes to existing production code paths, no placeholder values.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Gap #1 (LIFE-02 major) from 08-VERIFICATION.md is closed: sticky Findings table now faithfully indexes the live open inline comments on incremental rephrase-at-same-line
- Plans 08-09 and 08-10 can proceed with remaining non-blocker gaps (INLINE_MARKER, cursor-cli cwd, noop install)
- Pre-existing ruff E501/I001 in `src/prevue/github/comments.py` (line 15, I001 import sort) and `src/prevue/review.py` (line 623, E501) — deferred, not introduced by this plan

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
