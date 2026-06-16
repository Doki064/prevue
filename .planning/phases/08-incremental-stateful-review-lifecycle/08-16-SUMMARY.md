---
phase: 08-incremental-stateful-review-lifecycle
plan: 16
subsystem: infra
tags: [github-actions, issue_comment, prevue-command, actionlint, zizmor, LIFE-03]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: prevue command CLI + authorize_commenter dispatcher (08-14/08-15)
provides:
  - issue_comment /prevue command workflow (env-isolated body, minimal scopes, no PR-head checkout)
  - CI actionlint coverage for prevue-command.yml
  - consumer-setup /prevue commands documentation
affects: [LIFE-03 ship gate]

tech-stack:
  added: []
  patterns:
    - "Comment body via PREVUE_COMMENT_BODY env only — never shell interpolation"
    - "Unconditional engine install on command path (no preflight noop gate)"

key-files:
  created:
    - .github/workflows/prevue-command.yml
  modified:
    - .github/workflows/ci.yml
    - docs/consumer-setup.md

key-decisions:
  - "Command workflow uses consumer default-branch checkout only — no PR head/merge ref"
  - "author_association pre-filter in job if:; Python permission API is authoritative gate"
  - "vars.PREVUE_REF / vars.PREVUE_ENGINE for consumer pinning (defaults v0.6.0 / copilot-cli)"

patterns-established:
  - "Separate prevue-command.yml workflow file consumers add alongside prevue-review caller"

requirements-completed: []

# Metrics
duration: partial (Task 1 only)
completed: 2026-06-16
---

# Phase 8 Plan 16: /prevue Command Workflow Summary

**issue_comment trigger workflow with env-isolated body, minimal token scopes, unconditional engine install, and consumer docs — Task 2 §L7 security checkpoint PENDING**

## Status

| Task | Status | Commit |
|------|--------|--------|
| Task 1: prevue-command.yml + CI + docs | **Complete** | `2ca1715` |
| Task 2: §L7 pre-ship security review (live sandbox PR) | **PENDING** — human verification required | — |

**Plan is NOT complete.** Task 2 blocking checkpoint must pass before LIFE-03 is shippable.

## Performance

- **Tasks completed:** 1 / 2
- **Files modified:** 3

## Accomplishments

- Created `.github/workflows/prevue-command.yml` — `issue_comment:[created]` trigger, job-level `if:` gate (PR + `/prevue` prefix + author_association pre-filter), minimal permissions, framework + consumer-default-branch checkouts only, unconditional engine install, `uv run prevue command` with env-isolated body
- Extended `ci.yml` actionlint to explicitly lint `prevue-command.yml` (zizmor already scans `.github/workflows/`)
- Added `/prevue commands` section to `docs/consumer-setup.md` (three commands, write-access gate, fork refusal, minimal scopes, separate workflow snippet)

## Task Commits

1. **Task 1: prevue-command.yml issue_comment workflow + CI static analysis + docs** — `2ca1715` (feat)

## Verification (Task 1)

| Check | Result |
|-------|--------|
| `actionlint .github/workflows/prevue-command.yml` | PASS (v1.7.12 binary) |
| `zizmor .github/workflows/prevue-command.yml` | Not run locally (no zizmor binary); CI zizmor-action covers `.github/workflows/` |
| `uv run pytest -q` | PASS — 568 passed |
| No PR-head/merge checkout | PASS — grep confirms no `pull_request.head`/`merge` refs |
| permissions block | PASS — `contents: read`, `pull-requests: write`, `checks: write` only |
| Engine install unconditional | PASS — no `if:` on Install engine CLI step |
| Body env-only (Fact 4) | PASS — `comment.body` only in `if:` expression and `PREVUE_COMMENT_BODY` env |

## Pending: Task 2 §L7 Security Checkpoint

**Gate:** `checkpoint:human-verify` (blocking-human)

Before ship, verify on a live sandbox PR:

1. Write/admin collaborator: `/prevue review` runs full review
2. Read-only collaborator: denied with zero engine spend
3. Actions log: no PR-head/merge checkout — only framework + consumer default branch
4. `/prevue dismiss` guard-1 behavior confirmed
5. Fork PR refusal (if testable)

**Resume signal:** Type `approved` when all checks pass, or describe issues found.

## Deviations from Plan

None — Task 1 executed as written.

## Self-Check: PASSED

- FOUND: `.github/workflows/prevue-command.yml`
- FOUND: `.github/workflows/ci.yml` (modified)
- FOUND: `docs/consumer-setup.md` (modified)
- FOUND: commit `2ca1715`

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Task 1 completed: 2026-06-16*
*Task 2 §L7: PENDING*
