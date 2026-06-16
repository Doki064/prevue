---
phase: 08-incremental-stateful-review-lifecycle
plan: 01
subsystem: testing
tags: [fingerprint, sha256, nfkc, casefold, fixtures, graphql, compare-api, tdd]

requires: []
provides:
  - normalize_title + fingerprint pure functions (D-04 / LIFE-02)
  - Shared REST compare fixtures (ahead/diverged/identical)
  - Shared GraphQL fixtures (reviewThreads, resolve, FORBIDDEN)
affects:
  - 08-02 through 08-07 (HTTP mocking and fingerprint identity)

tech-stack:
  added: []
  patterns:
    - "Content-addressed finding identity: sha256(path|normalize(title))[:16]"
    - "Unicode-normalized title: NFKC → casefold → strip punctuation → collapse whitespace"

key-files:
  created:
    - src/prevue/fingerprint.py
    - tests/test_fingerprint.py
    - tests/fixtures/compare_ahead.json
    - tests/fixtures/compare_diverged.json
    - tests/fixtures/compare_identical.json
    - tests/fixtures/graphql_review_threads.json
    - tests/fixtures/graphql_resolve_ok.json
    - tests/fixtures/graphql_forbidden.json
  modified: []

key-decisions:
  - "LAST_SHA fixture constant deadbeef123456789012345678901234567890ab — merge_base in compare_ahead equals this last-reviewed marker SHA"
  - "HEAD_SHA abc123def456789012345678901234567890abcd aligned with tests/test_diff.py for downstream compare wiring"
  - "Diverged merge_base uses BASE_SHA base000def456789012345678901234567890abcd — differs from LAST_SHA to model force-push fallback"

patterns-established:
  - "Pure stdlib fingerprint module mirroring gate.py constant + pure-fn style"
  - "Class-grouped fingerprint tests mirroring test_prompt.py layout"

requirements-completed: [LIFE-02]

duration: 5min
completed: 2026-06-15
---

# Phase 8 Plan 01: Fingerprint + Shared Fixtures Summary

**Deterministic D-04 fingerprint (NFKC+casefold title normalize, 16-hex sha256) plus six REST/GraphQL fixtures for downstream incremental lifecycle mocks**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15T12:20:00Z
- **Completed:** 2026-06-15T12:25:29Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `normalize_title` and `fingerprint` implement LIFE-02/D-04 identity contract with unicode-correct normalization
- Nine pytest cases pin determinism, exclusion of line/severity/suggestion, and reworded-title distinction
- Six shared JSON fixtures unblock Waves 2–5 compare/GraphQL HTTP mocking via `responses`

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — fingerprint/normalize determinism + exclusion contract** - `74a637c` (test)
2. **Task 2: GREEN — implement fingerprint.py to pass the contract** - `7b1e5ea` (feat)
3. **Task 3: Shared compare-API + GraphQL JSON fixtures** - `16d4187` (chore)

**Plan metadata:** `5e1595a` (docs: complete plan)

## Files Created/Modified

- `src/prevue/fingerprint.py` — `normalize_title` + `fingerprint` pure functions (stdlib only)
- `tests/test_fingerprint.py` — D-04 contract tests (casefold, NFKC, determinism, identity scope)
- `tests/fixtures/compare_ahead.json` — incremental scope: status=ahead, merge_base=LAST_SHA
- `tests/fixtures/compare_diverged.json` — force-push fallback: status=diverged, merge_base≠LAST_SHA
- `tests/fixtures/compare_identical.json` — noop path: status=identical, empty files
- `tests/fixtures/graphql_review_threads.json` — reviewThreads with resolved + unresolved nodes
- `tests/fixtures/graphql_resolve_ok.json` — resolveReviewThread success body
- `tests/fixtures/graphql_forbidden.json` — FORBIDDEN scope-failure body

## Fixture SHA Convention

| Constant | SHA | Used in |
|----------|-----|---------|
| LAST_SHA | `deadbeef123456789012345678901234567890ab` | Marker last-reviewed head; compare_ahead merge_base |
| HEAD_SHA | `abc123def456789012345678901234567890abcd` | Current PR head (matches `tests/test_diff.py`) |
| DIVERGED_MERGE_BASE | `base000def456789012345678901234567890abcd` | compare_diverged merge_base (≠ LAST_SHA) |

## Decisions Made

- Followed PATTERNS.md D-04 normalize pipeline exactly: NFKC → casefold → punctuation strip → whitespace collapse
- Fixture SHAs aligned with existing `test_diff.py` HEAD_SHA/BASE_SHA where downstream plans must wire compare calls
- No third-party dependencies — hashlib/re/unicodedata only

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 2 plans can import `prevue.fingerprint` and register compare/GraphQL fixtures
- `08-02` severity parse-back and region-changed helpers can proceed with zero file conflicts

## TDD Gate Compliance

- RED commit `74a637c` (test) precedes GREEN commit `7b1e5ea` (feat) — gate satisfied

## Self-Check: PASSED

- FOUND: src/prevue/fingerprint.py
- FOUND: tests/test_fingerprint.py
- FOUND: tests/fixtures/compare_ahead.json
- FOUND: tests/fixtures/compare_diverged.json
- FOUND: tests/fixtures/compare_identical.json
- FOUND: tests/fixtures/graphql_review_threads.json
- FOUND: tests/fixtures/graphql_resolve_ok.json
- FOUND: tests/fixtures/graphql_forbidden.json
- FOUND: 74a637c
- FOUND: 7b1e5ea
- FOUND: 16d4187

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
