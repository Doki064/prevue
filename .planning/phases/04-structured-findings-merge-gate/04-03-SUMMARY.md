---
phase: 04-structured-findings-merge-gate
plan: 03
subsystem: api
tags: [unidiff, pydantic, gate-policy, merge-gate, review-config]

requires:
  - phase: 04-01
    provides: RED scaffolds in test_gate.py and test_positions.py pinning API contracts
provides:
  - commentable_lines/build_valid_lines unidiff position validity (D-17)
  - ReviewConfig + load_review_config fail-closed consumer thresholds (D-12/D-13/D-16)
  - conclude ladder and apply_gate pipeline with GateResult accounting (D-05/D-06/D-14/D-18/D-19)
  - verdict_title/severity_counts_line/thresholds_line single-source helpers (D-07)
affects: [04-04, 04-05]

tech-stack:
  added: []
  patterns:
    - "Fixed-order gate pipeline: verdict/counts → threshold → position → budget"
    - "Synthesized ---/+++ headers before PatchSet for GitHub patch fragments"

key-files:
  created:
    - src/prevue/github/positions.py
    - src/prevue/gate.py
  modified:
    - tests/test_positions.py

key-decisions:
  - "Position validation before budget allocation so unplaceable findings never consume inline slots"
  - "load_review_config owned by gate.py — policy module owns its config surface"

patterns-established:
  - "GateResult mirrors ClassificationResult as single accounting object for renderers"
  - "UnidiffParseError → empty sets (unplaceable, never crash)"

requirements-completed: [NOIS-02, NOIS-03, OUTP-02, OUTP-03]

duration: 15min
completed: 2026-06-13
---

# Phase 04 Plan 03: Gate Policy Pipeline Summary

**Deterministic merge gate: unidiff position sets, fail-closed ReviewConfig, apply_gate budget pipeline, D-07 verdict strings**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-13T05:40:00Z
- **Completed:** 2026-06-13T05:55:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- `commentable_lines` / `build_valid_lines` compute RIGHT/LEFT validity from GitHub patch fragments via unidiff with synthesized headers
- `ReviewConfig` + `load_review_config` + `conclude` implement fail-closed thresholds and neutral-never-blocks ladder
- `apply_gate` produces `GateResult` with fixed pipeline ordering; verdict string helpers pinned for 04-04/04-05

## Task Commits

1. **Task 1: positions.py GREEN** - `1f754a7` (feat)
2. **Task 2: ReviewConfig + conclude** - `8769a6f` (feat)
3. **Task 3: apply_gate + verdict strings** - `167f18f` (feat)

## Files Created/Modified

- `src/prevue/github/positions.py` - unidiff-backed commentable line sets per file/side
- `src/prevue/gate.py` - ReviewConfig, conclude, apply_gate, GateResult, verdict helpers
- `tests/test_positions.py` - corrected hunk headers for unidiff 0.7.5 strict parsing

## Decisions Made

- Position validation runs before budget allocation (unplaceable findings never consume slots)
- `load_review_config` lives in gate.py rather than classify/rules.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed RED scaffold patch hunk headers for unidiff strict parsing**
- **Found during:** Task 1 (positions.py GREEN)
- **Issue:** MODIFIED_PATCH and NO_NEWLINE_PATCH had incorrect `@@` line counts; unidiff 0.7.5 raised `UnidiffParseError: Hunk is shorter than expected`
- **Fix:** Corrected hunk headers; adjusted removed-line test to assert context-only RIGHT membership instead of contradictory line-11 exclusion on replace hunks
- **Files modified:** tests/test_positions.py
- **Verification:** `uv run pytest tests/test_positions.py -x` GREEN
- **Committed in:** 1f754a7

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test scaffold corrections required for unidiff contract; no implementation scope change.

## Issues Encountered

None beyond scaffold hunk header mismatch (documented above).

## User Setup Required

None.

## Next Phase Readiness

- 04-04 can consume `GateResult`, `PlacedFinding`, and verdict string helpers for sticky rendering
- 04-05 can wire `apply_gate` into `run_review()` with `build_valid_lines`

## Self-Check: PASSED

- FOUND: src/prevue/github/positions.py
- FOUND: src/prevue/gate.py
- FOUND: .planning/phases/04-structured-findings-merge-gate/04-03-SUMMARY.md
- FOUND: 1f754a7
- FOUND: 8769a6f
- FOUND: 167f18f

---
*Phase: 04-structured-findings-merge-gate*
*Completed: 2026-06-13*
