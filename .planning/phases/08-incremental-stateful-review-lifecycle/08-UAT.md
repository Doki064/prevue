---
status: testing
phase: 08-incremental-stateful-review-lifecycle
source: 08-11-SUMMARY.md, 08-12-SUMMARY.md, 08-13-SUMMARY.md, 08-14-SUMMARY.md, 08-15-SUMMARY.md, 08-16-SUMMARY.md
started: 2026-06-16T12:00:00Z
updated: 2026-06-16T22:00:00Z
session: life03-life05-supplemental
prior_session: gap-closure-supplemental (14/14 pass, 2026-06-16)
sandbox_pr: https://github.com/[redacted]/[redacted]/pull/24
sandbox_repo: https://github.com/[redacted]/[redacted]
---

## Current Test

number: 16
name: Dismiss Creates Sticky Audit Entry (D-14/D-15)
expected: |
  `/prevue dismiss <id> reason: text` adds a row to the sticky Dismissed findings audit section with id, reason, author, and timestamp. Sticky verdict/review sections remain intact (not overwritten).
awaiting: user response

## Tests

### 1. First Run Full Review + Marker SHA
expected: New PR with no head-bearing sticky marker gets full base..head review; sticky comment embeds `head=<sha>` matching PR head after run; check publishes.
result: pass
note: Round 1

### 2. Incremental Second Push (LIFE-01)
expected: Push a new commit that changes only some files on an already-reviewed PR. Prevue re-reviews only the newly touched files (not the whole PR). Sticky marker `head=` advances to the new head SHA. Workflow completes green for LIFE-01/02 path.
result: pass
note: Round 1

### 3. Carry-Forward Out-of-Scope Priors (LIFE-02)
expected: On an incremental run, prior Prevue inline comments on files NOT touched since the last marker SHA remain on the PR unchanged — not deleted, not duplicated, not edited (unless severity escalated on a re-touched file).
result: issue
reported: "Inline comments correctly untouched when not fixed, but sticky Findings table no longer lists the carried finding — PR #23 line 1 inline still shows 'Scratch code with no clear purpose' while sticky table shows different title"
severity: major
note: Round 1 — fixed in 08-08

### 4. No-Op Re-Run on Same SHA
expected: Re-trigger the review workflow on the same head SHA (e.g. workflow re-run). Prevue step completes quickly without re-invoking the engine. Sticky comment and check refresh in place. No duplicate inline comments appear.
result: pass
note: Round 1

### 5. Gate Blocks False Green (LIFE-02 / D-11)
expected: With an unresolved error-severity Prevue inline comment still open from a prior run, push a new commit that only touches unrelated/clean files. The check verdict stays fail (or partial per gate config) — it does NOT turn green while the carried error remains unresolved.
result: pass
note: Round 1

### 6. Outdated Thread Resolve (LIFE-04)
expected: On an incremental run where a prior finding's line region changed and no current finding matches its fingerprint, Prevue attempts to resolve the review thread (GraphQL). If token scope returns 403 FORBIDDEN, workflow logs the skip and still completes (best-effort); if scope permits, thread collapses as resolved.
result: pass
note: Round 1

### 7. Force-Push Full Fallback (LIFE-01)
expected: After a rebase or force-push where the stored marker SHA is no longer an ancestor of head, Prevue falls back to a full base..head review (not a bogus incremental range). Marker resets to the new head SHA after completion.
result: pass
note: Round 1

### 8. Consumer Config Knobs Documented
expected: `docs/consumer-setup.md` documents `review.incremental`, `review.resolve_outdated`, and `review.max_known_issues` with defaults, plus the 403 resolve-outdated scope caveat. Workflow permissions remain minimal (`contents: read`, `pull-requests: write`, `checks: write` only — no `contents: write`).
result: pass
note: Round 1

### 9. Sticky Findings Matches Inline on Rephrase
expected: On incremental run with engine rephrase at same (path, line) and equal severity, sticky Findings table row title matches live inline comment — not the new engine title.
result: pass
note: PR #24 incremental run — 4/4 uat-phase08-a.js table rows match inline titles exactly

### 10. GFM Inline Footer on New Comments
expected: Newly posted Prevue inline comments show GFM attribution `_posted by Prevue_` (italic/emphasis styling), not literal raw `<sub>posted by Prevue</sub>` HTML tags in the comment body.
result: pass
note: PR #24 — 4 inline threads all have `_posted by Prevue_`, zero legacy `<sub>` on new comments

### 11. Legacy HTML Marker Carry-Forward
expected: PRs with existing inline comments stamped with legacy `<sub>posted by Prevue</sub>` marker still participate in carry-forward, dedupe, and resolve on incremental runs — not orphaned or duplicated.
result: pass
note: PR #21 API — 3 legacy `<sub>` threads intact; unit tests TestInlineMarkerDetection (6 pass); PR #24 incremental carried 4 open findings on untouched uat-phase08-a.js (carry-forward mechanism verified live)

### 12. Consumer Repo Context in Review Prose
expected: Sticky Review section prose describes the consumer repository under review (e.g. test files, app code in the PR), not the Prevue framework / GitHub Actions codebase from the `.prevue` checkout.
result: pass
note: PR #24 incremental Review references uat-phase08-b.js, src/index.js, React entry — no .prevue/framework leak

### 13. Noop Skips Engine CLI Install
expected: Same-SHA workflow re-run: workflow logs show preflight detected noop and the "Install engine CLI" step is skipped. Total run time noticeably shorter than first full review (engine install absent).
result: pass
note: Run 27572927811 re-run — "Pre-flight: same-SHA noop detected"; Install engine CLI step conclusion=skipped

### 14. Incremental Scope Disclaimer in Sticky Review
expected: On an incremental run, sticky Review section includes a deterministic disclaimer that review is scoped to files changed since last marker SHA and that prior open findings on unchanged files are carried forward. If carried open count > 0, disclaimer mentions the count.
result: pass
note: PR #24 incremental sticky — blockquote disclaimer + "4 prior open finding(s) may be on files outside this incremental diff"

### 15. Full Review Authoritative Resolve (D-13)
expected: On full-scope review, engine-silent priors auto-resolve without line-region change; incremental runs keep conservative D-09 gate.
result: blocked
blocked_by: prior-phase
reason: "/prevue review on PR #16 did nothing — command workflow not on main (issue_comment requires default branch). No Actions run after comment 2026-06-16T06:04:45Z."

### 16. Dismiss Creates Sticky Audit Entry (D-14/D-15)
expected: `/prevue dismiss <id> reason: text` adds a row to the sticky Dismissed findings audit section with id, reason, author, and timestamp. Sticky verdict/review sections remain intact (not overwritten).
result: [pending]

### 17. Dismiss Excludes from Gate Open-Set (LIFE-05)
expected: After dismissing the only open error-severity finding, the `prevue/review` check can turn green (dismissed fingerprint excluded from gate open-set). Non-dismissed errors still block.
result: [pending]

### 18. /prevue review Force-Full Bypasses Noop (D-17)
expected: On a PR whose head SHA matches the sticky marker, posting `/prevue review` runs the engine (full review) — not the same-SHA noop path. Marker head SHA refreshes after completion.
result: blocked
blocked_by: prior-phase
reason: "Same bootstrap blocker — command workflow not on main."

### 19. Write Collaborator Can Run /prevue review (LIFE-03)
expected: A collaborator with write or admin permission posting `/prevue review` on a PR triggers the command workflow successfully — review runs and sticky/check update.
result: blocked
blocked_by: prior-phase
reason: "Same bootstrap blocker — command workflow not on main."

### 20. Read-Only Collaborator Denied (LIFE-03 §L7)
expected: A read-only collaborator posting `/prevue review` receives a denial reply on the PR. Workflow logs show no engine invocation / zero model spend.
result: [pending]

### 21. Fork PR Refusal (LIFE-03)
expected: Posting any `/prevue` command on a fork-originated PR is refused with an explanatory comment — no review engine run.
result: [pending]

### 22. /prevue resolve Thread (LIFE-03)
expected: `/prevue resolve <thread_id>` attempts to resolve the named review thread. On 403 FORBIDDEN (scope limit), workflow logs skip best-effort and still completes; with sufficient scope, thread collapses as resolved.
result: [pending]

### 23. prevue-command Workflow Security + Docs (08-16)
expected: Command workflow logs show only framework + consumer default-branch checkout (no PR head/merge ref). Comment body passed via `PREVUE_COMMENT_BODY` env only. `docs/consumer-setup.md` documents all three commands, write gate, fork refusal, and minimal permissions.
result: [pending]

## Summary

total: 23
passed: 14
issues: 0
pending: 6
skipped: 0
blocked: 3

## Gaps

[none yet — LIFE-03/LIFE-05 supplemental round in progress]
