---
phase: 01-walking-skeleton-review-loop
plan: 07
subsystem: infra
tags: [github-actions, secr-01, workflow, e2e, copilot-cli]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: prevue review CLI + orchestration (Plan 06)
provides:
  - Secure pull_request-only wrapper workflow (.github/workflows/review.yml)
  - SECR-01 static guards (tests/test_workflow_yaml.py)
  - Adopter README (trigger matrix + COPILOT_GITHUB_TOKEN recipe)
  - Live E2E proof on real Actions runner (D-11)
affects:
  - Phase 2 classification/routing (workflow on main after merge)
  - Phase 5 reusable workflow packaging

tech-stack:
  added: []
  patterns:
    - "Thin workflow, fat CLI — review.yml only sets up runner + uv run prevue review"
    - "setup-uv SHA-pinned; checkout @v6 tag; copilot @1.0.61 npm pin"
    - "Copilot prompt via stdin (not -p) for ARG_MAX safety on large diffs"

key-files:
  created:
    - .github/workflows/review.yml
    - tests/test_workflow_yaml.py
    - README.md
  modified:
    - .github/workflows/ci.yml

key-decisions:
  - "Version tags for checkout@v6; SHA pin for astral-sh/setup-uv@v8.2.0"
  - "Copilot CLI stdin mode verified on runner (run 27378511750)"
  - "Throwaway spike-copilot.yml deleted after live E2E sign-off"

patterns-established:
  - "Workflow YAML enforces SECR-01 via pytest static guards + zizmor in CI"
  - "Human-verify checkpoint gates live PR proof before phase close"

requirements-completed: [SECR-01, OUTP-01, DIFF-01, ENGN-02]

duration: 45min
completed: 2026-06-12
---

# Phase 01 Plan 07: Secure Workflow + Live E2E Summary

**pull_request-only review.yml on Actions, SECR-01 static guards, README adopter docs, and live sticky-comment E2E on PR #2**

## Performance

- **Duration:** ~45 min (includes CI iteration + human-verify)
- **Started:** 2026-06-11T21:00:00Z
- **Completed:** 2026-06-12T00:00:00Z
- **Tasks:** 3 (workflow+test, README, live E2E checkpoint)
- **Files modified:** 6

## Accomplishments

- `.github/workflows/review.yml` — `pull_request` only, minimal permissions, concurrency, single `uv run prevue review`
- `tests/test_workflow_yaml.py` — trigger, permissions, no PR-head checkout, setup-uv SHA, copilot version pins
- `README.md` — fork matrix, `COPILOT_GITHUB_TOKEN` recipe, minimal permissions
- **Live E2E (D-11):** [PR #2](https://github.com/Doki064/prevue/pull/2) — one sticky comment created, updated in place on subsequent pushes ([run 27378511750](https://github.com/Doki064/prevue/actions/runs/27378511750/job/80908947334?pr=2))
- Deleted throwaway `spike-copilot.yml` after sign-off

## Task Commits

Squashed into branch commit `0f2d600` during PR prep; close-out commits follow.

1. **Task 1: Secure wrapper + SECR-01 guard** — in `0f2d600`
2. **Task 2: README trigger matrix + token recipe** — in `0f2d600`
3. **Task 3: Live E2E verification** — human-approved 2026-06-12

## Files Created/Modified

- `.github/workflows/review.yml` — Prevue Review workflow
- `.github/workflows/ci.yml` — aligned setup-uv SHA + uv 0.11.21
- `tests/test_workflow_yaml.py` — SECR-01 static enforcement
- `README.md` — adopter documentation
- `.github/workflows/spike-copilot.yml` — **deleted** post-E2E

## Decisions Made

- Copilot prompt via stdin (not `-p`) after ARG_MAX failure on large PR diff
- `actions/checkout@v6` tag + `astral-sh/setup-uv@fac544c…` SHA + `@github/copilot@1.0.61`
- Sticky upsert requires bot author + marker at body start (`_is_prevue_sticky`)

## Deviations from Plan

### Auto-fixed Issues

**1. Checkout SHA typo → version tags → SHA for setup-uv only**
- **Found during:** CI runs on PR #2
- **Issue:** Wrong checkout SHA; user preferred tags for checkout, SHA for setup-uv
- **Fix:** `actions/checkout@v6`, `setup-uv@fac544c…`, uv 0.11.21, copilot 1.0.61
- **Verification:** Run 27378511750 success

**2. Copilot -p ARG_MAX on large diff**
- **Found during:** Prevue Review run 27377558166
- **Issue:** `[Errno 7] Argument list too long`
- **Fix:** `subprocess.run(..., input=prompt)` without `-p`
- **Verification:** Runs 27377693449, 27378511750 success

**3. Branch squashed to single commit for reviewable PR**
- **Found during:** PR hygiene
- **Issue:** 44 atomic plan commits noisy for merge PR
- **Fix:** `git reset --soft main` → one feat commit
- **Verification:** PR #2 shows clean history

---

**Total deviations:** 3 auto-fixed (all correctness/ops)
**Impact on plan:** No scope creep; E2E goal met.

## Issues Encountered

- CI workflow `startup_failure` until `ci.yml` lands on `main` (expected pre-merge)
- GitHub `pull_request` workflows need default-branch presence for reliable triggers post-merge

## User Setup Required

`COPILOT_GITHUB_TOKEN` fine-grained PAT (`github_pat_…`) with Copilot Requests — documented in README.

## Live E2E Evidence

| Item | Result |
|------|--------|
| PR | https://github.com/Doki064/prevue/pull/2 |
| Run | https://github.com/Doki064/prevue/actions/runs/27378511750/job/80908947334?pr=2 |
| Sticky comment | One `github-actions[bot]` comment, edited in place on re-push |
| Spike removed | `spike-copilot.yml` deleted on checkpoint approval |

## Self-Check: PASSED

- `uv run pytest` — 48 passed
- `tests/test_workflow_yaml.py` — 11 passed
- Live runner — Prevue Review succeeded, sticky comment upsert confirmed

## Next Phase Readiness

- Merge PR #2 → `review.yml` + `ci.yml` on `main`
- Phase 2 can add deterministic classifier without breaking the loop
- Open follow-up PR post-merge to re-verify workflow from default branch

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*
