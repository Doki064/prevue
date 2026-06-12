---
phase: 02-zero-token-classification-routing
plan: 02
subsystem: api
tags: [pathspec, classification, routing, canonical-order, general-fallback, zero-token]

requires:
  - phase: 02-zero-token-classification-routing
    provides: Plan 01 thin classify/route wired into run_review with Metadata audit trail
provides:
  - Multi-label union classify (D-01) with PR-level general fallback (D-03)
  - CANONICAL_LABEL_ORDER + GENERAL_LABEL constants in models.py
  - Canonical-order route() and Metadata rendering for stable sticky comments
affects: [02-03, phase-3-selective-skill-loading, phase-5-hybrid-classification]

tech-stack:
  added: []
  patterns:
    - CANONICAL_LABEL_ORDER pinned to dependency-free models.py for presentation imports
    - PR-level general only when real-label union is empty (Pitfall 3)
    - route sorts by canonical index before 1:1 bundle mapping

key-files:
  created: []
  modified:
    - src/prevue/classify/models.py
    - src/prevue/classify/classifier.py
    - src/prevue/classify/router.py
    - src/prevue/github/comments.py
    - tests/test_classify_classifier.py
    - tests/test_classify_router.py
    - tests/test_comments.py

key-decisions:
  - "CANONICAL_LABEL_ORDER + GENERAL_LABEL live in models.py — comments.py never imports classifier"
  - "Union loop: all files × all labels; first match per label wins; no break after first label"
  - "route() re-sorts input labels by canonical index for deterministic bundle order"

patterns-established:
  - "Presentation layer imports order constants from models only (pathspec isolation)"
  - "Metadata Labels/Bundles iterate CANONICAL_LABEL_ORDER, not alphabetical sorted()"

requirements-completed: [CLSF-01, CLSF-03, ROUT-01]

duration: 8min
completed: 2026-06-12
---

# Phase 2 Plan 2: Classifier Refinement Summary

**Multi-label union classify with PR-level `general` fallback, canonical label ordering, and stable Metadata audit trail**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-12T03:02:43Z
- **Completed:** 2026-06-12T03:10:43Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- `classify` returns union of all matched labels (D-01); `{general}` only when union empty (D-03)
- `CANONICAL_LABEL_ORDER` and `GENERAL_LABEL` in models.py; classify output deterministically ordered
- `route` handles `general` 1:1 (override-able) with canonical bundle ordering
- Metadata renders labels + bundles in canonical order — no alphabetical churn (Pitfall 5)
- 89 tests green; full RED→GREEN TDD discipline per task

## Task Commits

Each task was committed atomically:

1. **Task 1: Multi-label union + PR-level general + canonical ordering** — `4dc7fe9` (test RED), `2377c7f` (feat GREEN)
2. **Task 2: Route general label + canonical Metadata rendering** — `a312e72` (test RED), `8d6cc68` (feat GREEN)

## TDD Gate Compliance

- Task 1: RED (`4dc7fe9`) before GREEN (`2377c7f`) ✓
- Task 2: RED (`a312e72`) before GREEN (`8d6cc68`) ✓

## Files Created/Modified

- `src/prevue/classify/models.py` — `CANONICAL_LABEL_ORDER`, `GENERAL_LABEL` constants
- `src/prevue/classify/classifier.py` — full union loop, PR-level general, `_order_labels`
- `src/prevue/classify/router.py` — canonical sort before bundle mapping
- `src/prevue/github/comments.py` — Metadata uses `CANONICAL_LABEL_ORDER` (not `sorted()`)
- `tests/test_classify_classifier.py` — union, general, canonical, overlap, provenance tests
- `tests/test_classify_router.py` — general routing + canonical order tests
- `tests/test_comments.py` — canonical Metadata ordering test (security before infra)

## Decisions Made

- Strengthened metadata canonical-order test with security/infra pair (alphabetical would fail)
- Shared `_canonical_index` helper duplicated in router and comments (small, keeps models dependency-free)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-03 can add consumer merge (D-05/D-07), empty-PR skip (D-10), dropped-count audit
- `general` label is the named seam for Phase 5 LLM fallback upgrade
- Engine still receives baseline instructions only — skill loading is Phase 3

---
*Phase: 02-zero-token-classification-routing*
*Completed: 2026-06-12*

## Self-Check: PASSED

- FOUND: src/prevue/classify/models.py
- FOUND: src/prevue/classify/classifier.py
- FOUND: src/prevue/classify/router.py
- FOUND: src/prevue/github/comments.py
- FOUND: 4dc7fe9, 2377c7f, a312e72, 8d6cc68
