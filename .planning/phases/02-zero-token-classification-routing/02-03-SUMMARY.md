---
phase: 02-zero-token-classification-routing
plan: 03
subsystem: api
tags: [yaml, consumer-config, empty-skip, audit-trail, zero-token]

requires:
  - phase: 02-zero-token-classification-routing
    provides: Plan 01 filter/classify/route wired; Plan 02 multi-label union + general fallback
provides:
  - merge_rules additive consumer config (D-05/D-06/D-07)
  - D-10 empty-PR neutral skip before engine call
  - dropped_count in Metadata and skip note (D-09)
affects: [phase-3-selective-skill-loading, phase-5-hybrid-classification]

tech-stack:
  added: []
  patterns:
    - merge_rules override-by-label replace for consumer label keys (D-05)
    - filter-first D-10 gate before classify/route/engine (Pitfall 4)
    - _upsert_marker_comment shared by upsert_sticky and upsert_skip_note

key-files:
  created: []
  modified:
    - src/prevue/classify/rules.py
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_classify_rules.py
    - tests/test_review_flow.py
    - tests/test_comments.py

key-decisions:
  - "D-05 label merge: consumer entry replaces that label's built-in globs (override-by-label)"
  - "Consumer YAML shape validated via RuleSet probe before merge (fail-closed T-02-08)"
  - "D-10 skip uses shared _upsert_marker_comment — same idempotent sticky mechanics"

patterns-established:
  - "load_ruleset(consumer_path) optional; Phase 5 wires trusted-base-ref fetch"
  - "run_review resolves PR after filter; empty reduced.files returns before classify"

requirements-completed: [DIFF-02, CLSF-03, ROUT-01]

duration: 2min
completed: 2026-06-12
---

# Phase 2 Plan 3: Edge Cases + Configurability Summary

**Consumer prevue.yml merges additively over built-ins; all-filtered PRs skip engine with idempotent sticky note and dropped-count audit**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-12T03:04:14Z
- **Completed:** 2026-06-12T03:05:49Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `merge_rules` + `load_ruleset(consumer_path)`: D-07 ignore append, D-05 label override-by-label, D-06 routing override; safe_load + fail-closed
- D-10 empty-PR neutral skip: filter-first branch returns before classify/route/engine — zero tokens on lockfile-only PRs
- `upsert_skip_note` idempotent sticky; Metadata and skip note disclose dropped-file count (D-09)
- 100 tests green; full RED→GREEN TDD discipline per task

## Task Commits

Each task was committed atomically:

1. **Task 1: Consumer-config additive merge** — `7ecf9dd` (test RED), `997cc8e` (feat GREEN)
2. **Task 2: D-10 empty-PR skip + dropped-count audit** — `36082bc` (test RED), `79b4cfe` (feat GREEN)

## TDD Gate Compliance

- Task 1: RED (`7ecf9dd`) before GREEN (`997cc8e`) ✓
- Task 2: RED (`36082bc`) before GREEN (`79b4cfe`) ✓

## Files Created/Modified

- `src/prevue/classify/rules.py` — `merge_rules`, consumer-path `load_ruleset` with safe_load validation
- `src/prevue/review.py` — D-10 filter-first skip branch; dropped_count on ClassificationResult
- `src/prevue/github/comments.py` — `upsert_skip_note`, `_upsert_marker_comment`, Metadata dropped count
- `tests/test_classify_rules.py` — merge, additive, routing, fail-closed tests
- `tests/test_review_flow.py` — `empty_skip` test; dropped_count assertion on filtered path
- `tests/test_comments.py` — skip note idempotency + metadata dropped count tests

## Decisions Made

- Label override-by-label uses **replace** (consumer globs replace built-in for that label key)
- Consumer field validation probes RuleSet before merge to catch `ignore: not-a-list` (string→char-list trap)
- Skip note body: `no reviewable files (N filtered)` per D-10 contract

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Consumer YAML type validation before merge**
- **Found during:** Task 1 (malformed consumer fail-closed test)
- **Issue:** `list("not-a-list")` silently produced char list passing RuleSet validation
- **Fix:** RuleSet probe on consumer fields before merge_rules
- **Files modified:** src/prevue/classify/rules.py
- **Commit:** 997cc8e

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 complete — zero-token classify/route/filter pipeline with consumer config and empty-PR skip
- Phase 3 can load SKILL.md bundles from route() output identifiers
- Phase 5 wires trusted-base-ref fetch for consumer prevue.yml path

---
*Phase: 02-zero-token-classification-routing*
*Completed: 2026-06-12*

## Self-Check: PASSED

- FOUND: src/prevue/classify/rules.py
- FOUND: src/prevue/review.py
- FOUND: src/prevue/github/comments.py
- FOUND: 7ecf9dd, 997cc8e, 36082bc, 79b4cfe
