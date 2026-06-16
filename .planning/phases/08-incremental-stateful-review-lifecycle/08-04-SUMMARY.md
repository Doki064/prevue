---
phase: 08-incremental-stateful-review-lifecycle
plan: 04
subsystem: github
tags: [graphql, prompt-fencing, review-threads, untrusted-data, dedupe]

# Dependency graph
requires:
  - phase: 08-01
    provides: GraphQL fixtures (graphql_review_threads.json, graphql_forbidden.json, graphql_resolve_ok.json)
provides:
  - Thin requests-based GraphQL transport for reviewThreads query and resolveReviewThread mutation
  - Best-effort thread resolve (403/FORBIDDEN logs to stderr, returns False, never fails run)
  - Known-issues list injected into review prompt as capped UNTRUSTED DATA fence (D-07)
affects: [08-06, 08-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw requests GraphQL helper isolated from PyGithub internals (D-08/D-10)"
    - "Best-effort GitHub I/O: log + skip on FORBIDDEN, mirror _delete_prevue_inline_comments"
    - "Engine-derived known-issues fenced with _escape_line + INSTRUCTION_REASSERTION (SECR-02)"

key-files:
  created:
    - src/prevue/github/graphql.py
    - tests/test_graphql.py
  modified:
    - src/prevue/engines/prompt.py
    - tests/test_prompt.py

key-decisions:
  - "GraphQL via raw requests.post to api.github.com/graphql — not PyGithub internals (D-10 stability)"
  - "resolve_review_thread returns bool; caller checks isResolved before mutate (idempotency Pitfall 3)"
  - "Known-issues cap N passed as max_known_issues kwarg — no config import in prompt.py"

patterns-established:
  - "GraphQLError carries errors payload; resolve path never raises to orchestrator"
  - "build_known_issues_block renders ## Already reported section before INSTRUCTION_REASSERTION"

requirements-completed: [LIFE-02, LIFE-04]

# Metrics
duration: 2min
completed: 2026-06-15
---

# Phase 08 Plan 04: GraphQL Transport + Known-Issues Prompt Summary

**Thin GraphQL review-thread resolve (best-effort 403-skip) and capped UNTRUSTED-DATA known-issues list in review prompt**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-15T12:38:28Z
- **Completed:** 2026-06-15T12:39:55Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `fetch_review_threads` paginates reviewThreads (id, isResolved, isOutdated, path, line, body)
- `resolve_review_thread` best-effort: FORBIDDEN/403 → stderr log, return False, no raise
- `build_known_issues_block` injects capped (path, line, title) list as ~~~UNTRUSTED DATA before reassertion
- `estimate_prompt_overhead_tokens` accounts for known-issues framing when packing

## Task Commits

1. **Task 1: GraphQL transport** - `78f4a90` (feat)
2. **Task 2: Known-issues prompt fencing** - `86d2b6f` (feat)

## Files Created/Modified

- `src/prevue/github/graphql.py` - GraphQL query/mutation transport with GraphQLError and best-effort resolve
- `tests/test_graphql.py` - responses-mocked fetch, resolve success, FORBIDDEN skip, idempotency surface test
- `src/prevue/engines/prompt.py` - build_known_issues_block, optional known_issues on _build_prompt
- `tests/test_prompt.py` - TestKnownIssues: fence, cap, adversarial escape, empty regression, overhead

## Decisions Made

- Raw `requests` for GraphQL (plan/research alignment; survives PyGithub internal churn)
- Idempotency delegated to caller via `isResolved` field — resolve helper does not re-query before mutate
- Empty known_issues preserves byte-identical prompt for full reviews (no regression)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 06 can wire `fetch_review_threads` + `resolve_review_thread` into outdated-thread cleanup
- Plan 06/07 can pass in-scope priors as `known_issues` to `build_prompt`
- Live scope verification for resolveReviewThread remains gated in Plan 07 (Open Q #1)

## Self-Check: PASSED

- FOUND: src/prevue/github/graphql.py
- FOUND: tests/test_graphql.py
- FOUND: 78f4a90
- FOUND: 86d2b6f

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
