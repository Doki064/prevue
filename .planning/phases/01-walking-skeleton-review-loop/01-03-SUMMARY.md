---
phase: 01-walking-skeleton-review-loop
plan: 03
subsystem: api
tags: [pydantic, engine-adapter, contract, tdd]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: uv scaffold, pytest infrastructure, CI gate (Plan 02)
provides:
  - pydantic v2 adapter contract (ChangedFile, DiffBundle, ReviewRequest, Finding, ReviewResult)
  - contract tests enforcing ENGN-01 shape, D-02 findings default, D-07 no title/body
affects: [01-04, 01-05, 01-06, phase-4-findings]

tech-stack:
  added: []
  patterns:
    - "P1 pydantic v2 adapter contract — ReviewRequest → ReviewResult seam"
    - "D-07 injection posture — DiffBundle/ReviewRequest carry no PR title/body"

key-files:
  created:
    - src/prevue/models.py
    - tests/test_models.py
  modified: []

key-decisions:
  - "Locked ENGN-01 final shape now — Phase 4 fills findings without reshaping models (D-02)"
  - "DiffBundle deliberately omits PR title/body fields — structural injection defense (D-07)"

patterns-established:
  - "P1: pydantic v2 BaseModel + Field(default_factory=...) for all cross-component I/O"
  - "Finding schema present now; ReviewResult.findings defaults [] until Phase 4"

requirements-completed: [ENGN-01]

duration: 5min
completed: 2026-06-12
---

# Phase 01 Plan 03: Adapter Contract Models Summary

**pydantic v2 engine adapter contract (ReviewRequest → ReviewResult) with D-02 empty findings default and D-07 no title/body injection surface**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-12T00:00:00Z
- **Completed:** 2026-06-12T00:05:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Locked ENGN-01 adapter contract in `src/prevue/models.py` — single import surface for all downstream components
- Contract tests enforce defaults (`findings=[]`, `engine_meta={}`, `budget_seconds=300`, `model=None`)
- D-07 enforced via `model_fields` assertions — no `title`/`body`/`pr_title`/`pr_body` on `DiffBundle` or `ReviewRequest`
- JSON round-trip validated for populated `ReviewResult` with `Finding`

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — contract tests for the adapter models** - `741bceb` (test)
2. **Task 2: GREEN — implement the pydantic v2 contract** - `7ef46fe` (feat)

**Plan metadata:** `25fec38` (docs: complete plan)

## Files Created/Modified

- `src/prevue/models.py` — ChangedFile, DiffBundle, ReviewRequest, Finding, ReviewResult
- `tests/test_models.py` — validation, defaults, D-07 field absence, JSON round-trip

## Decisions Made

- Followed RESEARCH.md Pattern 1 canonical definitions exactly — no field additions beyond ENGN-01
- `Finding` included now with full schema; v1 returns empty `findings` list per D-02

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED commit `741bceb` (test) precedes GREEN commit `7ef46fe` (feat) — compliant

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04 (GitHub I/O) and Plan 05 (Copilot adapter) can import `from prevue.models import ...`
- conftest.py still has stub types — Plan 06 orchestration should migrate fixtures to real models

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*

## Self-Check: PASSED

- FOUND: src/prevue/models.py
- FOUND: tests/test_models.py
- FOUND: 741bceb
- FOUND: 7ef46fe
