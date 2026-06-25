---
phase: 08-incremental-stateful-review-lifecycle
plan: 07
subsystem: infra
tags: [incremental, lifecycle, permissions, uat, resolve-outdated, consumer-docs]

requires:
  - phase: 08-06
    provides: run_review incremental orchestration, noop path, resolve-before-gate
provides:
  - Live-runner verification that resolveReviewThread returns 403 under minimal scope (pull-requests: write) with graceful skip
  - Confirmed incremental scoping + marker advance on real sandbox PR pushes (LIFE-01)
  - Confirmed noop re-run skips engine and avoids duplicate comments
  - Test-pinned minimal workflow permissions + consumer docs for incremental/resolve_outdated/max_known_issues knobs
affects:
  - Phase 8 completion; v1 milestone closure

tech-stack:
  added: []
  patterns:
    - "resolveReviewThread 403 → best-effort skip; review.resolve_outdated: false opt-out (no contents: write broadening)"
    - "YAML test guard: permissions == {contents: read, pull-requests: write, checks: write}"

key-files:
  created: []
  modified:
    - .github/workflows/prevue-review.yml
    - docs/consumer-setup.md
    - tests/test_reusable_workflow_yaml.py
    - src/prevue/github/comments.py
    - src/prevue/review.py

key-decisions:
  - "resolveReviewThread requires broader scope on gap-demo-sandbox sandbox (403 FORBIDDEN); ship LIFE-04 as best-effort with resolve_outdated opt-out — do NOT add contents: write (WKFL-04)"
  - "Post-UAT fixes: line=null outdated crash, open-set dedupe by (path,line), sticky-before-inline write order"

patterns-established:
  - "Live scope verification: 403 confirms RESEARCH Open Q #1; LIFE-01/02 ship green regardless"

requirements-completed: [LIFE-04, LIFE-01]

duration: 45min
completed: 2026-06-15
---

# Phase 8 Plan 07: Live Scope + Incremental E2E Summary

**resolveReviewThread 403 under minimal scope confirmed; incremental scoping + noop re-run green on sandbox PRs; consumer knobs documented; no contents:write broadening**

## Performance

- **Duration:** 45 min (Task 1 automated + UAT checkpoint + post-UAT fixes)
- **Started:** 2026-06-15T13:30:00Z
- **Completed:** 2026-06-15T15:00:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Minimal token scope test-pinned (`contents: read`, `pull-requests: write`, `checks: write`); workflow comment documents graceful 403 degradation
- Consumer docs cover `review.incremental`, `review.resolve_outdated`, `review.max_known_issues` with defaults and scope caveat
- Live UAT on gap-demo-sandbox sandbox: resolve scope **403** (best-effort skip, LIFE-01/02 green); incremental scoping **PASS**; noop re-run **PASS**
- Post-UAT bug fixes committed: outdated inline `line=null` crash, open-set dedupe by `(path,line)`, sticky-before-inline write order

## Task Commits

1. **Task 1: Assert minimal token scope unchanged + document the new knobs** - `48ff762` (docs)
2. **Task 2: Live sandbox UAT (checkpoint)** - UAT approved; post-UAT fixes `eac308c`, `0c92a04` (fix)

## Live UAT Results (gap-demo-sandbox sandbox)

### 1. Resolve scope (RESEARCH Open Q #1) — **403**

| Aspect | Result |
|--------|--------|
| PR | gap-demo-sandbox #21 |
| Observation | `prevue: review thread resolve failed (FORBIDDEN)` in workflow logs |
| Scope | `pull-requests: write` insufficient for `resolveReviewThread` in this account |
| Run outcome | LIFE-01/02 still green — best-effort skip works; sticky + check published, marker advanced |
| Decision | **Do NOT** broaden workflow to `contents: write` (WKFL-04). Consumers who need LIFE-04 thread collapse can set `review.resolve_outdated: false` or grant broader scope at their discretion |

### 2. Incremental scoping (LIFE-01) — **PASS**

| Aspect | Result |
|--------|--------|
| PR | gap-demo-sandbox #21, commit 5 (Create test2.js) |
| In-scope review | Only `test2.js` re-reviewed |
| Carry-forward | `test1.js` priors carried as position-fallback out of scope |
| Marker | `head=<sha>` advanced to new head |

### 3. No-op re-run (Pitfall 3) — **PASS**

| Aspect | Result |
|--------|--------|
| PR | gap-demo-sandbox #22, workflow re-run attempt 2 on same SHA |
| Engine | Not re-invoked (~6s prevue step) |
| Sticky | Updated in place |
| Comments | No duplicates |

## Files Created/Modified

- `tests/test_reusable_workflow_yaml.py` — permissions block assertion (no `contents: write`)
- `docs/consumer-setup.md` — incremental/resolve_outdated/max_known_issues knobs + scope caveat
- `.github/workflows/prevue-review.yml` — permissions comment linking opt-out
- `src/prevue/github/comments.py` — post-UAT: `line=null` outdated handling, `(path,line)` dedupe
- `src/prevue/review.py` — post-UAT: sticky-before-inline write order

## Decisions Made

- **403 scope outcome:** Ship LIFE-04 as best-effort with documented `review.resolve_outdated: false` opt-out; minimal scope unchanged (explicit user direction + WKFL-04)
- **Post-UAT fixes:** Three bugs found during live runs — fixed on branch before plan close (`eac308c`, `0c92a04`)

## Deviations from Plan

### Post-UAT Bug Fixes (outside plan tasks, user-directed)

**1. [Rule 1 - Bug] Outdated inline `line=null` crash**
- **Found during:** UAT on gap-demo-sandbox PR #21
- **Issue:** Resolve path crashed when outdated finding had `line=null`
- **Fix:** Guard null line in outdated resolution
- **Commit:** `eac308c`

**2. [Rule 1 - Bug] Open-set dedupe by `(path,line)`**
- **Found during:** UAT
- **Issue:** Duplicate sticky rows for same path/line
- **Fix:** Dedupe open-set entries by `(path,line)` tuple
- **Commit:** `eac308c`

**3. [Rule 1 - Bug] Sticky-before-inline write order**
- **Found during:** UAT
- **Issue:** Inline comments published before sticky marker update
- **Fix:** Reorder to publish sticky before inline comments
- **Commit:** `0c92a04`

---

**Total deviations:** 3 post-UAT bug fixes (all Rule 1, user-approved)
**Impact on plan:** Required for correct live behavior; no scope broadening.

## Issues Encountered

- `gsd-tools` unavailable in executor shell — STATE/ROADMAP updated manually
- `resolveReviewThread` returns 403 under minimal scope on sandbox account — expected fallback path; documented in consumer-setup.md

## User Setup Required

None - no external service configuration required. Consumers needing LIFE-04 thread collapse on accounts where `pull-requests: write` is insufficient should set `review.resolve_outdated: false` or evaluate granting `contents: write` at their own risk boundary.

## Next Phase Readiness

- Phase 8 complete — all 7 plans executed; LIFE-01/02/04 verified live (LIFE-04 degrades gracefully under 403)
- v1 milestone ready for close/audit

## Self-Check: PASSED

- FOUND: .planning/phases/08-incremental-stateful-review-lifecycle/08-07-SUMMARY.md
- FOUND: tests/test_reusable_workflow_yaml.py
- FOUND: docs/consumer-setup.md
- FOUND: .github/workflows/prevue-review.yml
- FOUND: commit 48ff762
- FOUND: commit eac308c
- FOUND: commit 0c92a04
- FOUND: commit a4d9b44

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
