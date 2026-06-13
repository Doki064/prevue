---
phase: 04-structured-findings-merge-gate
plan: 01
subsystem: testing
tags: [pytest, unidiff, tdd, red-scaffold, nyquist]

requires:
  - phase: 03-selective-skill-loading
    provides: Finding model, run_review orchestration, test conventions
provides:
  - unidiff 0.7.x dependency pinned in pyproject.toml/uv.lock
  - RED contract tests for parsing, positions, gate, and checks modules
  - wave_0_complete validation gate for Phase 4 parallel execution
affects: [04-02, 04-03, 04-04, 04-05]

tech-stack:
  added: [unidiff==0.7.*]
  patterns: [interface-first RED scaffolds, Nyquist per-task verify map]

key-files:
  created:
    - tests/test_findings_parsing.py
    - tests/test_positions.py
    - tests/test_gate.py
    - tests/test_checks.py
  modified:
    - pyproject.toml
    - uv.lock
    - .planning/phases/04-structured-findings-merge-gate/04-VALIDATION.md

key-decisions:
  - "Wave 0 pins all Phase 4 public API contracts as executable RED tests before any implementation"
  - "unidiff 0.7.* approved via 04-RESEARCH Package Legitimacy Audit — no human gate required"

patterns-established:
  - "RED scaffolds import only the target module symbols listed in plan artifacts"
  - "Position test fixtures use bare @@ hunk fragments without ---/+++ headers"

requirements-completed: []

duration: 12min
completed: 2026-06-13
---

# Phase 4 Plan 01: Wave 0 RED Scaffolds Summary

**unidiff 0.7.x locked plus four RED pytest scaffolds pinning parsing, positions, gate, and checks contracts**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-13T04:37:40Z
- **Completed:** 2026-06-13T04:40:02Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added audited `unidiff==0.7.*` dependency (0.7.5 resolved) for diff position validation
- Created four RED test files with real assertions against Phase 4 public APIs (524 lines total)
- Flipped `wave_0_complete: true` in 04-VALIDATION.md; existing 114-test suite stays green

## Task Commits

1. **Task 1: Add unidiff 0.7.x dependency** - `78110ac` (chore)
2. **Task 2: RED test scaffolds** - `26b737e` (test)

**Plan metadata:** `591d371` (docs)

## Files Created/Modified

- `pyproject.toml` / `uv.lock` — unidiff 0.7.* pinned
- `tests/test_findings_parsing.py` — ENGN-03 fence extraction + strict salvage (103 lines)
- `tests/test_positions.py` — OUTP-02 unidiff validity sets (95 lines)
- `tests/test_gate.py` — NOIS-02/03 + OUTP-03 config/ladder/budget/verdict (256 lines)
- `tests/test_checks.py` — OUTP-03 check-run MagicMock contracts (70 lines)
- `04-VALIDATION.md` — wave_0_complete + checklist ticked

## Decisions Made

None beyond plan — followed Wave 0 interface-first TDD strategy as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 04-02/04-03/04-05 have unambiguous GREEN targets via RED scaffolds
- Wave 2 parallel execution unblocked (`wave_0_complete: true`)
- Requirements ENGN-03/OUTP-02/OUTP-03/NOIS-02/NOIS-03 remain pending until implementation plans complete

## Self-Check: PASSED

- FOUND: tests/test_findings_parsing.py
- FOUND: tests/test_positions.py
- FOUND: tests/test_gate.py
- FOUND: tests/test_checks.py
- FOUND: 78110ac
- FOUND: 26b737e

---
*Phase: 04-structured-findings-merge-gate*
*Completed: 2026-06-13*
