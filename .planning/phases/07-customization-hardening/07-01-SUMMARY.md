---
phase: 07-customization-hardening
plan: 01
subsystem: testing
tags: [pytest, pydantic, skills, packing, injection]

requires:
  - phase: 06-reusable-workflow-hybrid-classification
    provides: PrevueConfig single-read loader and hybrid review pipeline
provides:
  - SkillsConfig + review token budget knobs in config/gate
  - Consumer skill fixture tree for merge tests
  - RED test scaffolds for DIFF-03, OUTP-04, SKIL-03, SECR-02
affects: [07-02, 07-03, 07-04, 07-05]

tech-stack:
  added: []
  patterns:
    - "SkillsConfig extra=forbid section mirroring SkipConfig"
    - "RED scaffolds import target symbols inside test bodies"

key-files:
  created:
    - tests/test_pack.py
    - tests/test_tokens.py
    - tests/test_skills_merge.py
    - tests/test_injection_adversarial.py
    - tests/fixtures/skills/consumer/
  modified:
    - src/prevue/config.py
    - src/prevue/gate.py
    - tests/test_config.py

key-decisions:
  - "max_input_tokens default 120000 — under MAX_PROMPT_BYTES bytes/4 ceiling"
  - "Consumer fixtures use exact bundle/filename keys for override tests"

patterns-established:
  - "Phase 7 RED files collect cleanly; fail on missing implementation not import errors"

requirements-completed: [DIFF-03, OUTP-04, SKIL-03, SECR-02]

duration: 15min
completed: 2026-06-15
---

# Phase 7 Plan 01 Summary

**Wave 0 RED contracts and config knobs for customization, packing, transparency, and injection hardening**

## Performance

- **Duration:** 15 min
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added `SkillsConfig` (exclude + byte/count caps) and `ReviewConfig` budget fields
- Created five consumer skill fixtures (override, custom, over-cap, malformed, non-canonical)
- Shipped 12 RED tests across four new test modules; 321 prior tests remain green

## Task Commits

1. **Task 1: Config knobs** - `aae04ed` (feat)
2. **Task 2: Consumer fixtures** - `e50f877` (test, includes Task 3 files)
3. **Task 3: RED scaffolds** - `e50f877` + `ad11633` (style fix)

## Files Created/Modified

- `src/prevue/config.py` — `SkillsConfig` wired into `PrevueConfig`
- `src/prevue/gate.py` — `max_input_tokens`, `output_reserve_tokens`
- `tests/test_*.py` — RED scaffolds for four Phase 7 slices
- `tests/fixtures/skills/consumer/` — merge test fixtures

## Decisions Made

None — followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## Self-Check: PASSED

- key-files.created exist on disk
- git log contains 07-01 commits
- `pytest tests/test_config.py` green; RED files collect; 321 prior tests green

## Next Phase Readiness

Wave 1 complete. Plans 07-02 (packing) and 07-05 (injection) can proceed in parallel on Wave 2.

---
*Phase: 07-customization-hardening*
*Completed: 2026-06-15*
