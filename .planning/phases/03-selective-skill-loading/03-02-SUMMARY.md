---
phase: 03-selective-skill-loading
plan: 02
subsystem: api
tags: [skills, loader, frontmatter, pathspec, security]

requires:
  - phase: 03-selective-skill-loading
    provides: RED test scaffolds and python-frontmatter dependency
provides:
  - prevue.skills package with Skill model and loader
  - security bundle (3 skills)
  - run_review selective load + assemble wiring
  - loaded_skills sticky Metadata audit (D-13)
affects: [03-03, 04]

tech-stack:
  added: []
  patterns: [importlib.resources packaged skills, per-skill glob selection, canonical_index ordering]

key-files:
  created:
    - src/prevue/skills/models.py
    - src/prevue/skills/loader.py
    - src/prevue/skills/security/*.md
  modified:
    - src/prevue/classify/models.py
    - src/prevue/review.py
    - src/prevue/github/comments.py

requirements-completed: [SKIL-01, SKIL-04]

duration: 12min
completed: 2026-06-12
---

# Phase 03 Plan 02 Summary

**Selective skill loader with security bundle wired end-to-end — changed paths select matching skills, assemble instructions, audit in sticky Metadata**

## Task Commits

1. **Task 1: canonical_index lift** - `0c515a7` (refactor)
2. **Task 2: Skill model + loader** - `1563ee1` (feat)
3. **Task 3: Security bundle + wiring** - `7ed128b` (feat)

## Deviations from Plan

None - plan executed exactly as written.

---
*Phase: 03-selective-skill-loading*
*Completed: 2026-06-12*
