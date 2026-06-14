---
phase: 07-customization-hardening
plan: 06
subsystem: api
tags: [skills, sticky, engine-meta, provenance]
requires:
  - phase: 07-04
    provides: consumer skill merge and exclude
  - phase: 07-03
    provides: sticky token and metadata lines
provides:
  - Skill.source (builtin | consumer) on loader merge
  - engine_meta.engine from adapter.name in run_review
  - Sticky Engine line reads engine_meta (no hardcoded copilot-cli)
  - Consumer skills tagged in Skills line as "(bundle, consumer)"
affects: [07-UAT]
tech-stack:
  added: []
  patterns: ["Display-only provenance strings sourced from orchestration, not PR diff"]
key-files:
  created: []
  modified:
    - src/prevue/skills/models.py
    - src/prevue/skills/loader.py
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_skills_merge.py
    - tests/test_comments.py
key-decisions:
  - "Consumer tag format: Name (bundle, consumer) — audit aid only, not security boundary"
patterns-established:
  - "engine_meta.engine set immediately after engine.review(req) from adapter.name"
requirements-completed: [SKIL-03, OUTP-04]
duration: 8min
completed: 2026-06-15
---

# Phase 7 Plan 06 Summary

**Sticky Metadata truthfully reports active engine and consumer vs built-in skill provenance**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `Skill.source` field (`builtin` | `consumer`) persisted through loader merge
- `result.engine_meta["engine"]` populated from `engine.name` after review
- `render_body` uses `engine_meta.get("engine")` — removed hardcoded `copilot-cli`
- Consumer-loaded skills render as `Name (bundle, consumer)` in sticky Skills line

## Task Commits

1. **Task 1: Skill.source + loader provenance** — `4af9610` (feat)
2. **Task 2: engine_meta + sticky render** — `dcef188` (feat)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `pytest tests/test_skills_merge.py tests/test_comments.py tests/test_review_flow.py -x -q` green
- `grep copilot-cli src/prevue/github/comments.py` — no hardcoded Engine line
- Full suite: 350 passed

---
*Phase: 07-customization-hardening*
*Completed: 2026-06-15*
