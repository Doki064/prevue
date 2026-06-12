---
phase: 02-zero-token-classification-routing
plan: 01
subsystem: api
tags: [pathspec, pyyaml, classification, gitignore, pydantic, zero-token]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: run_review orchestration, DiffBundle models, sticky comment upsert
provides:
  - classify package with default_rules.yml and RuleSet/ClassificationResult models
  - filter_diff, classify, route pure functions (zero subprocess/network)
  - filter→classify→route wired into run_review with Metadata audit trail
affects: [02-02, 02-03, phase-3-selective-skill-loading]

tech-stack:
  added: [pathspec==1.1.*, PyYAML==6.0.*]
  patterns: [importlib.resources for packaged YAML, GitIgnoreSpec.from_lines gitignore factory, pure-transform via model_copy]

key-files:
  created:
    - src/prevue/classify/default_rules.yml
    - src/prevue/classify/models.py
    - src/prevue/classify/rules.py
    - src/prevue/classify/filter.py
    - src/prevue/classify/classifier.py
    - src/prevue/classify/router.py
    - tests/test_classify_rules.py
    - tests/test_classify_filter.py
    - tests/test_classify_classifier.py
    - tests/test_classify_router.py
  modified:
    - pyproject.toml
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_review_flow.py
    - tests/test_comments.py

key-decisions:
  - "GitIgnoreSpec.from_lines(globs) — pathspec 1.x factory, not 0.12 gitwildmatch"
  - "ClassificationResult threaded separately to upsert_sticky for D-09 Metadata audit"
  - "Thin single-pass classify — no general fallback until Plan 02-02 (D-03)"

patterns-established:
  - "Pure classify stage: filter/classify/route never mutate DiffBundle in place"
  - "Packaged rules via importlib.resources + yaml.safe_load fail-closed into RuleSet"

requirements-completed: [DIFF-02, CLSF-01, CLSF-03, ROUT-01]

duration: 12min
completed: 2026-06-12
---

# Phase 2 Plan 1: Foundation + E2E Classification Slice Summary

**Zero-token filter→classify→route wired into run_review with YAML rules, pathspec filtering, and sticky Metadata showing labels + matched globs**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-12T02:55:00Z
- **Completed:** 2026-06-12T03:07:00Z
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments

- Added pathspec and PyYAML; shipped `default_rules.yml` with ignore/label/routing data
- Built thin pure functions: `filter_diff`, `classify`, `route` with matched-glob provenance
- Wired classify stage into `run_review()` — engine receives reduced diff (D-08); Metadata shows labels (D-09)
- 81 tests green; classify package has zero subprocess/network calls

## Task Commits

Each task was committed atomically:

1. **Task 1: Add deps, scaffold classify package** - `69cf638` (feat)
2. **Task 2: filter + classify + route pure functions** - `49ddd4d` (test RED), `9943361` (feat GREEN)
3. **Task 3: Wire run_review + Metadata render** - `8370ba3` (test RED), `690af5b` (feat GREEN)

**Plan metadata:** pending (docs commit)

## TDD Gate Compliance

- Task 2: RED (`49ddd4d`) before GREEN (`9943361`) ✓
- Task 3: RED (`8370ba3`) before GREEN (`690af5b`) ✓

## Files Created/Modified

- `src/prevue/classify/default_rules.yml` — built-in ignore globs, label rules, empty routing map
- `src/prevue/classify/rules.py` — `load_ruleset()` via importlib.resources + safe_load
- `src/prevue/classify/filter.py` — drops lockfiles/binaries before engine (D-08)
- `src/prevue/classify/classifier.py` — single-pass label assignment with matched glob
- `src/prevue/classify/router.py` — 1:1 bundle mapping with consumer override (D-06)
- `src/prevue/review.py` — filter→classify→route between fetch_diff and ReviewRequest
- `src/prevue/github/comments.py` — Metadata renders Labels/Bundles when classification provided

## Decisions Made

- Used `GitIgnoreSpec.from_lines(globs)` without explicit factory arg (pathspec 1.x default)
- Set `dropped_count` on ClassificationResult in run_review for future D-10 disclosure
- Left consumer_path stub and Plan 02/03 TODOs at insertion sites per plan scope

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial git commit failed (1Password signing buffer) — retried with full permissions; succeeded

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-02 can refine classifier: multi-label union (D-01), general fallback (D-03), canonical ordering
- Plan 02-03 can add consumer merge (D-05/D-07), empty-PR skip (D-10), dropped-count audit
- Engine still receives baseline instructions only — skill loading is Phase 3

---
*Phase: 02-zero-token-classification-routing*
*Completed: 2026-06-12*

## Self-Check: PASSED

- FOUND: src/prevue/classify/default_rules.yml
- FOUND: src/prevue/classify/filter.py
- FOUND: src/prevue/classify/classifier.py
- FOUND: src/prevue/classify/router.py
- FOUND: 69cf638, 49ddd4d, 9943361, 8370ba3, 690af5b
