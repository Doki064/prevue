---
phase: 08-incremental-stateful-review-lifecycle
plan: 05
subsystem: github
tags: [comments, carry-forward, escalation, graphql-resolve, fingerprint, incremental]

# Dependency graph
requires:
  - phase: 08-01
    provides: fingerprint(path, title) for prior re-derivation and current-set comparison
  - phase: 08-02
    provides: parse_severity_from_body, finding_region_changed for escalation and D-09 trigger
  - phase: 08-03
    provides: in_scope_paths contract from decide_scope incremental file-set
  - phase: 08-04
    provides: fetch_review_threads, resolve_review_thread best-effort GraphQL transport
provides:
  - post_inline_review scoped stale cleanup (D-05) and escalation-only refresh (D-06)
  - derive_prior_findings re-deriving path/line/side/fingerprint/severity/thread_id from live comments (D-01/D-12)
  - resolve_outdated_prior_findings conservative D-09 triple-condition resolve branch (D-08/D-09)
affects: [08-06, 08-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "in_scope_paths gates stale delete + outdated resolve; None preserves full-review behavior"
    - "SEVERITY_RANK escalation check skips .edit() when prior rank <= new rank (D-06)"
    - "Outdated threads resolved via GraphQL; same-run duplicates still hard-deleted"

key-files:
  created: []
  modified:
    - src/prevue/github/comments.py
    - tests/test_comments.py

key-decisions:
  - "resolve_outdated_prior_findings reuses single fetch_review_threads call — avoids double-fetch KeyError in derive path"
  - "prior_severity None → treat as escalation (edit allowed) — legacy/human comments without badge"
  - "post_inline_review resolve_outdated gated on owner/repo/regions_by_path all present"

patterns-established:
  - "PriorFinding dataclass: live-comment re-derivation source for gate open-set (Plan 06)"
  - "Title parse from first-line badge+**title** with _unescape_inline_markdown for fingerprint match"

requirements-completed: [LIFE-02, LIFE-04]

# Metrics
duration: 8min
completed: 2026-06-15
---

# Phase 08 Plan 05: Scoped Reconciliation Summary

**Incremental inline reconciliation: in-scope carry-forward, escalation-only refresh, conservative outdated→resolve, prior findings re-derived from live comments**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-15T12:35:00Z
- **Completed:** 2026-06-15T12:43:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `post_inline_review` accepts `in_scope_paths`; out-of-scope priors never edited or deleted (D-05)
- Matched-location refresh only when new severity strictly more severe than parsed prior (D-06)
- `derive_prior_findings` rebuilds fingerprints/severities/thread ids from live Prevue inline comments (D-01/D-12)
- `resolve_outdated_prior_findings` resolves threads only when in-scope AND region-changed AND fingerprint absent from current run (D-09)
- 403/FORBIDDEN resolve logged to stderr; run continues (best-effort, T-08-13)

## Task Commits

1. **Task 1: Scoped carry-forward + escalation-only refresh (D-05/D-06)** - `b790511` (test RED), `9b01fac` (feat)
2. **Task 2: Outdated→resolve + prior-finding re-derivation (D-08/D-09/D-01/D-12)** - `9b01fac` (feat + tests)

## Files Created/Modified

- `src/prevue/github/comments.py` - PriorFinding, derive_prior_findings, resolve_outdated_prior_findings; post_inline_review scoped stale set + escalation branch + optional resolve_outdated hook
- `tests/test_comments.py` - TestPostInlineReview carry-forward/escalation/duplicate tests; TestPriorFindings; TestOutdatedResolve with responses-mocked GraphQL

## Decisions Made

- Combined Task 1+2 implementation in one feat commit — both touch comments.py reconciliation loop; surgical edits not separable without churn
- `resolve_outdated_prior_findings` inlines prior iteration over `_existing_prevue_inline_by_location` instead of calling `derive_prior_findings` (avoids duplicate GraphQL fetch)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Double GraphQL fetch caused KeyError in resolve path**
- **Found during:** Task 2 implementation
- **Issue:** `resolve_outdated_prior_findings` called `derive_prior_findings`, which re-fetched threads; second response was resolve_ok payload missing `reviewThreads` keys
- **Fix:** Inline prior iteration in resolve function using threads from single fetch
- **Files modified:** `src/prevue/github/comments.py`
- **Committed in:** `9b01fac`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Necessary for correct GraphQL mock behavior; no scope change.

## Issues Encountered

None beyond the double-fetch bug (auto-fixed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-06 can wire `derive_prior_findings`, scoped `post_inline_review`, and `resolve_outdated` into `run_review` orchestration
- `post_inline_review` signature ready: `in_scope_paths`, `regions_by_path`, `owner`, `repo`, `resolve_outdated`

## Self-Check: PASSED

- FOUND: `.planning/phases/08-incremental-stateful-review-lifecycle/08-05-SUMMARY.md`
- FOUND: `src/prevue/github/comments.py`
- FOUND: `tests/test_comments.py`
- FOUND: commit `b790511`
- FOUND: commit `9b01fac`

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
