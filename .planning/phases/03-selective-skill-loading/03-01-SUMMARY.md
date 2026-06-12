---
phase: 03-selective-skill-loading
plan: 01
subsystem: testing
tags: [python-frontmatter, pytest, skills, tdd]

requires:
  - phase: 02-zero-token-classification-routing
    provides: classification/routing pipeline for later loader wiring
provides:
  - python-frontmatter 1.3.* dependency installed
  - tests/fixtures/skills/ fixture tree
  - skills_fixture_root conftest fixture
  - RED test scaffolds (7 loader + 3 builtin tests)
affects: [03-02, 03-03]

tech-stack:
  added: [python-frontmatter==1.3.*]
  patterns: [fixture-tree decoupled from built-in content, Nyquist RED-before-GREEN]

key-files:
  created:
    - tests/fixtures/skills/**/*.md
    - tests/test_skills_loader.py
    - tests/test_skills_builtin.py
  modified:
    - pyproject.toml
    - uv.lock
    - tests/conftest.py

key-decisions:
  - "Human-approved python-frontmatter install after PyPI/GitHub legitimacy check"

patterns-established:
  - "Loader unit tests use skills_fixture_root + monkeypatch _skills_root, not production tree"

requirements-completed: [SKIL-01, SKIL-02, SKIL-04]

duration: 8min
completed: 2026-06-12
---

# Phase 03 Plan 01 Summary

**Wave 0 RED scaffold: python-frontmatter dependency, skills fixture tree, and 10 failing test contracts for selective skill loading**

## Performance

- **Duration:** 8 min
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Installed `python-frontmatter==1.3.0` after blocking human supply-chain gate
- Created 5 fixture SKILL.md files under `tests/fixtures/skills/`
- Added `skills_fixture_root` pytest fixture
- Wrote 7 loader + 3 builtin RED tests matching 03-VALIDATION.md names

## Task Commits

1. **Task 1: Verify legitimacy + install** - `96b42e6` (deps)
2. **Task 2: Fixture tree + conftest** - `055dd39` (test)
3. **Task 3: RED test scaffolds** - `392c847` (test)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## Next Phase Readiness

Plan 02 can implement `prevue.skills` loader against fixed test contract.

---
*Phase: 03-selective-skill-loading*
*Completed: 2026-06-12*
