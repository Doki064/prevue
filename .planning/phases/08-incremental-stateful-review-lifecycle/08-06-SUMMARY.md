---
phase: 08-incremental-stateful-review-lifecycle
plan: 06
subsystem: api
tags: [incremental, lifecycle, orchestration, open-set-gate, marker-sha, known-issues]

requires:
  - phase: 08-03
    provides: decide_scope, marker SHA, gate config knobs, incremental fetch
  - phase: 08-04
    provides: known-issues prompt fencing, GraphQL resolve transport
  - phase: 08-05
    provides: derive_prior_findings, scoped post_inline_review, resolve outdated
provides:
  - run_review incremental orchestration seam (marker → scope → priors → engine → open-set gate → marker write)
  - noop idempotent path (identical re-run refreshes marker/check without engine)
  - false-green-proof gate over carried unresolved priors (D-11)
affects:
  - 08-07 live-runner E2E and consumer docs

tech-stack:
  added: []
  patterns:
    - "Scope decision before fetch_diff; incremental uses fetch_diff_in_scope"
    - "Resolve outdated before apply_gate; open-set union minus resolved fingerprints"
    - "Temporary build_prompt patch injects known_issues during engine.review"

key-files:
  created: []
  modified:
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_review_flow.py

key-decisions:
  - "Resolve outdated runs before apply_gate; post_inline_review gets resolve_outdated=False to avoid double-resolve"
  - "resolve_outdated_prior_findings returns resolved fingerprint set for D-11 open-set subtraction"
  - "upsert_sticky/render_body accept head_sha to embed render_marker in sticky body"

patterns-established:
  - "Incremental orchestration: read marker → decide_scope → scoped fetch → pack/classify → priors → known-issues → engine → resolve → open-set gate → inline → sticky+marker → check"

requirements-completed: [LIFE-01, LIFE-02, LIFE-04]

duration: 35min
completed: 2026-06-15
---

# Phase 8 Plan 06: Incremental Orchestration Summary

**run_review wired end-to-end: marker-driven scope, known-issues prompt, resolve-before-gate open-set verdict, head SHA marker write, identical noop**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-15T12:45:00Z
- **Completed:** 2026-06-15T13:20:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `run_review` reads sticky marker SHA, calls `decide_scope`, uses incremental fetch for in-scope files only, and noops on identical re-runs (marker/check refresh, no engine)
- Prior findings re-derived; known-issues list injected into engine prompt on incremental runs (capped); resolve runs before gate; verdict reflects union(current, carried-unresolved) − resolved (D-11)
- Sticky body writes `head=<sha>` via `upsert_sticky(head_sha=...)`; `review.incremental=false` and force-push full paths covered by integration tests

## Task Commits

1. **Task 1: Read marker → decide_scope → scope packed/classified set** - `05db24d` (test)
2. **Task 2: Re-derive priors → known-issues → gate-over-open-set → write marker** - `b93ccfd` (feat)

## Files Created/Modified

- `src/prevue/review.py` — incremental orchestration seam, noop handler, open-set gate assembly
- `src/prevue/github/comments.py` — `head_sha` on sticky render/upsert; `resolve_outdated_prior_findings` returns resolved fingerprints
- `tests/test_review_flow.py` — 9 integration tests + autouse incremental mocks for legacy tests

## Decisions Made

- Resolve outdated before `apply_gate` so resolved fingerprints exclude from open set; `post_inline_review` called with `resolve_outdated=False` after pre-resolve
- Engine known-issues injected via temporary `prompt_mod.build_prompt` wrapper (no ReviewRequest schema change)
- Noop path re-derives priors for gate conclusion without engine or thread resolve

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `resolve_outdated_prior_findings` return value**
- **Found during:** Task 2
- **Issue:** Function returned None; caller needs resolved fingerprint set for D-11 gate subtraction
- **Fix:** Return `set[str]` of resolved prior fingerprints
- **Files modified:** `src/prevue/github/comments.py`
- **Commit:** `b93ccfd`

**2. [Rule 2 - Missing Critical] Sticky marker SHA write path**
- **Found during:** Task 2
- **Issue:** `render_body` always used legacy `MARKER` without head SHA
- **Fix:** Added optional `head_sha` to `render_body` / `upsert_sticky`
- **Files modified:** `src/prevue/github/comments.py`
- **Commit:** `b93ccfd`

**3. [Rule 3 - Blocking] Legacy `test_review_flow` tests broke on new hooks**
- **Found during:** Task 1 verification
- **Issue:** `derive_prior_findings` / `decide_scope` called without mocks → GraphQL/env failures
- **Fix:** Autouse fixture default-mocks incremental hooks; updated 3 assertions for new `post_inline_review` kwargs
- **Files modified:** `tests/test_review_flow.py`
- **Commit:** `05db24d`, `b93ccfd`

---

**Total deviations:** 3 auto-fixed (2 Rule 2, 1 Rule 3)
**Impact on plan:** All required for correct D-11 gate and test hermeticity. No scope creep.

## Issues Encountered

- `gsd-tools` unavailable in executor shell — STATE/ROADMAP/REQUIREMENTS updated manually

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-07 can run live-runner GraphQL scope verification and consumer docs against wired orchestration
- All Wave 1–4 units integrated; E2E sandbox PR is the remaining validation surface

## Self-Check: PASSED

- FOUND: src/prevue/review.py
- FOUND: src/prevue/github/comments.py
- FOUND: tests/test_review_flow.py
- FOUND: .planning/phases/08-incremental-stateful-review-lifecycle/08-06-SUMMARY.md
- FOUND: commit 05db24d
- FOUND: commit b93ccfd
- `uv run pytest tests/test_review_flow.py -q` — 39 passed
- `uv run pytest -q` — 452 passed

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
