---
phase: 07-customization-hardening
plan: 07
subsystem: docs
tags: [prevue.yml, consumer-setup, configuration]
requires: []
provides:
  - docs/examples/prevue.yml copy-paste starter
  - consumer-setup.md Starter config section with links
affects: [07-UAT]
tech-stack:
  added: []
  patterns: ["Single starter YAML aligned with PrevueConfig defaults"]
key-files:
  created:
    - docs/examples/prevue.yml
  modified:
    - docs/consumer-setup.md
key-decisions:
  - "Inline minimal block plus link to full examples/prevue.yml — avoid duplicating configuration.md"
patterns-established: []
requirements-completed: [WKFL-03]
duration: 5min
completed: 2026-06-15
---

# Phase 7 Plan 07 Summary

**Copy-paste `.github/prevue.yml` starter shipped with consumer-setup wiring**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `docs/examples/prevue.yml` — full starter with review, skills, classification, engine, skip sections
- Commented `skills.exclude` example and `review_bots` allowlist hint
- `consumer-setup.md` Starter config section links examples + configuration.md + skills.md

## Task Commits

1. **Task 1: Add docs/examples/prevue.yml** — `9e174a5` (docs)
2. **Task 2: Wire starter into consumer-setup.md** — `bbd6fd8` (docs)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- YAML parses; required sections present
- consumer-setup.md grep checks pass

---
*Phase: 07-customization-hardening*
*Completed: 2026-06-15*
