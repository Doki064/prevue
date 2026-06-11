---
phase: 01-walking-skeleton-review-loop
plan: 04
subsystem: api
tags: [pygithub, responses, github-actions, diff-fetch, sticky-comment]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: pydantic DiffBundle/ReviewResult contract (Plan 03)
provides:
  - load_pr_context() with head/base repo full names for fork guard
  - fetch_diff() via pr.get_files() into DiffBundle (no checkout)
  - upsert_sticky() marker-based create-or-edit comment
affects:
  - 01-06 orchestration CLI
  - 01-07 secure workflow wrapper

tech-stack:
  added: []
  patterns:
    - "P3: deterministic Python owns all GitHub writes"
    - "Single GITHUB_EVENT_PATH parse for PR context"
    - "Hidden marker sticky comment upsert (D-06)"

key-files:
  created:
    - src/prevue/github/client.py
    - src/prevue/github/diff.py
    - src/prevue/github/comments.py
    - tests/test_diff.py
    - tests/test_comments.py
  modified: []

key-decisions:
  - "PrContext dataclass in client.py — not models.py (D-07)"
  - "get_authenticated_pull() shared resolver for diff fetch"
  - "Regex URL mocks for PyGithub :443 port in responses tests"

patterns-established:
  - "GitHub I/O as mockable boundary modules under prevue.github"
  - "TDD RED→GREEN per task with atomic commits"

requirements-completed: [DIFF-01, OUTP-01]

duration: 12min
completed: 2026-06-12
---

# Phase 01 Plan 04: GitHub I/O Summary

**Diff fetch and sticky comment upsert via PyGithub REST — no checkout, single event parse, marker upsert invariant**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-11T19:24:00Z
- **Completed:** 2026-06-11T19:36:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `load_pr_context()` reads `GITHUB_EVENT_PATH` once → `PrContext` with `head_repo_full` / `base_repo_full` for Plan 06 fork guard
- `fetch_diff()` maps `pr.get_files()` → `DiffBundle`, preserving `patch=None` for large/binary files (DIFF-01, D-08)
- `upsert_sticky()` creates one comment or edits in place via `<!-- prevue:sticky -->` marker (OUTP-01, D-06)
- Sectioned sticky body with Verdict/Review/Metadata and "no verdict in v1" placeholder (D-04/D-05)

## Task Commits

Each task was committed atomically with TDD RED→GREEN:

1. **Task 1: Diff fetch** — `3b6dc23` (test RED), `517383c` (feat GREEN)
2. **Task 2: Sticky comment upsert** — `535c15c` (test RED), `bf0e380` (feat GREEN)

## Files Created/Modified

- `src/prevue/github/client.py` — `PrContext`, `load_pr_context()`, `get_authenticated_pull()`
- `src/prevue/github/diff.py` — `fetch_diff()` → `DiffBundle`
- `src/prevue/github/comments.py` — `MARKER`, `render_body()`, `upsert_sticky()`
- `tests/test_diff.py` — responses mocks for repo/pull/files endpoints
- `tests/test_comments.py` — MagicMock PR for create vs edit branches

## Decisions Made

- `PrContext` lives in `client.py` (not `models.py`) to keep `DiffBundle` free of PR metadata beyond SHAs (D-07)
- Exposed `get_authenticated_pull()` as shared resolver rather than inlining in `fetch_diff()`
- Test mocks use regex URLs to match PyGithub's `:443` host variant

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PyGithub repo prefetch requires extra mock**
- **Found during:** Task 1 (GREEN)
- **Issue:** `get_repo().get_pull()` hits `GET /repos/{owner}/{repo}` before pull endpoints; tests only mocked pull/files
- **Fix:** Added repo payload mock; switched all GitHub URL mocks to regex matching `:443` port
- **Files modified:** `tests/test_diff.py`
- **Committed in:** `517383c`

**2. [Rule 1 - Bug] Case-sensitive verdict assertion**
- **Found during:** Task 2 (GREEN)
- **Issue:** Test checked lowercase `"no verdict in v1"` but render uses `"No verdict in v1"`
- **Fix:** Use `.lower()` in test assertion
- **Files modified:** `tests/test_comments.py`
- **Committed in:** `bf0e380`

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Test fixes only; implementation matches research examples.

## Issues Encountered

None beyond PyGithub mock URL port normalization (resolved in Task 1).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GitHub fetch/post boundaries ready for Plan 05 (Copilot adapter) and Plan 06 (orchestration CLI)
- `head_repo_full` / `base_repo_full` on `PrContext` available for fork guard

## Self-Check: PASSED

- FOUND: src/prevue/github/client.py
- FOUND: src/prevue/github/diff.py
- FOUND: src/prevue/github/comments.py
- FOUND: tests/test_diff.py
- FOUND: tests/test_comments.py
- FOUND: 3b6dc23
- FOUND: 517383c
- FOUND: 535c15c
- FOUND: bf0e380

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*
