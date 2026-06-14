---
quick_id: 260613-w0q
slug: fix-phase-6-prevue-self-review-findings
date: 2026-06-13
status: complete
---

# Quick Task 260613-w0q — Summary

Remediated Prevue's own PR #13 (Phase 6) self-review findings on a fresh branch,
post-merge. All fixes respect project constraints (reusable `workflow_call`,
minimal scopes, no `pull_request_target`, no `secrets: inherit`, forks skip in v1,
hybrid deterministic-first classification, zero-config adoption).

## Findings addressed

| # | Severity | Finding | Resolution | Commit |
|---|----------|---------|------------|--------|
| 5 | warning | Inline upsert leaves mixed state on edit failure | `post_inline_review` now edits first, creates, then ALWAYS cleans stale; aggregate `ok` return — no early abort. **Two tests that encoded the buggy behavior were rewritten** (root cause of the recurrence across all 10 PR iterations) + new edit-failure resilience test. | `82748a9` |
| 2 | warning | Reusable workflow lacks fork-PR job guard | Added `head.repo == github.repository` to job `if:` (defense-in-depth) + YAML guard test. | `c32fd06` |
| 4 | warning | Missing config silently uses defaults | stderr warning when `prevue.yml` absent; zero-config behavior unchanged. | `f1d191f` |
| 1 | warning | Unpinned `curl \| bash` Cursor install | Download installer to file then exec (no truncated-pipe exec); residual risk documented — no upstream pin/checksum exists. | `8ee8968` |
| 3 | warning | Consumer example omits fork guard | Documented forks skip automatically via reusable self-guard (no caller `if:` needed). | `8ee8968` |
| 6 | info | `review_bots` inverted allowlist | Documented as allowlist of bots TO review (empty = skip all bots). No rename (breaking config change avoided). | `8ee8968` |

## Deferred

- **#7 (info)** — multi-label classification vs path-glob skill loading. Needs skill-loader
  inspection to decide between aligning skill selection to classified labels or clarifying
  the sticky Metadata that bundles are classification hints. Out of scope for this task.

## Verification

- `uv run ruff check .` — all checks passed
- `uv run pytest` — 313 passed

## Note on recurrence (#5)

The defect persisted across every PR #13 iteration because `tests/test_comments.py`
asserted the abort-before-cleanup ordering (`test_create_failure_skips_stale_delete`,
`test_create_failure_skips_existing_inline_edit`). Green-test pressure reverted any real
fix. Tests now assert convergence (stale cleanup always runs; edits precede creates).
