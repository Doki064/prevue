---
phase: 08-incremental-stateful-review-lifecycle
plan: 02
subsystem: testing
tags: [severity, parse-back, unidiff, hunk-overlap, d-09, d-12, tdd]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: "Wave 0 fingerprint + fixtures (08-01)"
provides:
  - parse_severity_from_body + BADGE_TO_SEVERITY inverse map (D-12)
  - regions_changed + finding_region_changed hunk-overlap helpers (D-09)
affects:
  - 08-03 (gate-over-open-set severity recovery, decide_scope wiring)
  - 08-05 (outdated resolve trigger uses finding_region_changed)

tech-stack:
  added: []
  patterns:
    - "Severity parse-back: first non-empty line leading badge only; None fail-safe"
    - "Region-changed: conservative C=3 overlap on unidiff hunk RIGHT-side ranges"

key-files:
  created: []
  modified:
    - src/prevue/github/comments.py
    - src/prevue/github/positions.py
    - tests/test_comments.py
    - tests/test_positions.py

key-decisions:
  - "parse_severity_from_body scans first non-empty line only — badge emoji anchor, no eval (T-08-03)"
  - "finding_region_changed default context=3 — conservative bias toward NOT resolving (D-09)"

patterns-established:
  - "BADGE_TO_SEVERITY sits beside SEVERITY_BADGES as tested inverse contract"
  - "regions_changed reuses commentable_lines PatchSet header synthesis + UnidiffParseError fail-safe"

requirements-completed: []

duration: 2min
completed: 2026-06-15
---

# Phase 8 Plan 02: Severity Parse-Back + Region-Changed Helpers Summary

**Tested inverse of SEVERITY_BADGES for live comment severity recovery, plus conservative C=3 unidiff hunk overlap for outdated-thread detection**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-15T12:30:12Z
- **Completed:** 2026-06-15T12:31:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `parse_severity_from_body` round-trips all three severities through `render_inline_comment`; human/empty bodies return None
- `regions_changed` emits per-hunk RIGHT-side (start, end) ranges from incremental patches via PatchSet
- `finding_region_changed` detects direct overlap and within-C proximity; distant changes and bad patches fail-safe to False

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: Severity parse-back (D-12)** — RED `0eb501a`, GREEN `bc86277` (feat)
2. **Task 2: Region-changed hunk-overlap (D-09)** — RED `10304c7`, GREEN `996feba` (feat)

**Plan metadata:** `114cec2` (docs: complete plan)

## Files Created/Modified

- `src/prevue/github/comments.py` — `BADGE_TO_SEVERITY`, `parse_severity_from_body`
- `src/prevue/github/positions.py` — `regions_changed`, `finding_region_changed`
- `tests/test_comments.py` — `TestSeverityParseBack` (6 cases)
- `tests/test_positions.py` — `TestRegionsChanged`, `TestFindingRegionChanged` (9 cases)

## Decisions Made

- Leading-badge-only anchoring on first non-empty line (pattern-match, no eval/exec)
- Default context window C=3 for region overlap — biases toward leaving comments open
- `UnidiffParseError` and None patch → empty regions (fail-safe, do not resolve)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected MODIFIED_PATCH hunk range expectation**
- **Found during:** Task 2 (GREEN)
- **Issue:** Test expected `(10, 11)` but hunk includes trailing context line at RIGHT line 12
- **Fix:** Updated test assertions to `(10, 12)` — matches actual unidiff target lines
- **Files modified:** `tests/test_positions.py`
- **Verification:** `uv run pytest tests/test_positions.py -k region` passes
- **Committed in:** `996feba` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Test correction only; implementation matched plan spec from the start.

## TDD Gate Compliance

- Task 1: RED `0eb501a` (test) → GREEN `bc86277` (feat) ✓
- Task 2: RED `10304c7` (test) → GREEN `996feba` (feat) ✓

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- D-12 severity parse-back ready for D-11 gate-over-open-set in 08-03
- D-09 region-changed helper ready for outdated resolve trigger in 08-05
- LIFE-04 requirement remains open until GraphQL resolve + orchestration land (08-05+)

## Self-Check: PASSED

- FOUND: src/prevue/github/comments.py (parse_severity_from_body)
- FOUND: src/prevue/github/positions.py (regions_changed, finding_region_changed)
- FOUND: tests/test_comments.py (TestSeverityParseBack)
- FOUND: tests/test_positions.py (TestRegionsChanged, TestFindingRegionChanged)
- FOUND: 0eb501a, bc86277, 10304c7, 996feba

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
