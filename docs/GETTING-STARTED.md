<!-- generated-by: gsd-doc-writer -->

# Getting Started

Add Prevue AI PR review to your repository in four steps. This doc is for developers who want to consume Prevue from their own repo — not for contributors who want to develop Prevue itself (see [DEVELOPMENT.md](./DEVELOPMENT.md)).

## Prerequisites

You need these before starting:

| What | Requirement | Notes |
|------|-------------|-------|
| **GitHub repository** | Any visibility | Prevue runs on `pull_request` events; fork PRs are unsupported in v1 |
| **Engine secret** | At least one (see table below) | Copilot CLI is the default engine |
| **Branch protection** (optional) | Ability to add required checks | Needed if you want Prevue to gate merges |

### Engine secrets

Pick one engine. You only need the secret for the engine you choose.

| Engine | Workflow input | Secret name | How to get it |
|--------|---------------|-------------|---------------|
| `copilot-cli` (default) | `engine: copilot-cli` | `COPILOT_GITHUB_TOKEN` | Fine-grained user-owned PAT with **Copilot Requests** permission (prefix `github_pat_`) — not the Actions `GITHUB_TOKEN` |
| `claude-code-cli` | `engine: claude-code-cli` | `CLAUDE_CODE_OAUTH_TOKEN` | Long-lived token from `claude setup-token` |
| `cursor-cli` | `engine: cursor-cli` | `CURSOR_API_KEY` | Cursor API key |

## Step 1 — Add the caller workflow

Create `.github/workflows/prevue-review.yml` in your repository. Pin to a [release tag](https://github.com/Doki064/prevue/releases) — do not use `@main`.

```yaml
name: Prevue Review

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: write
  pull-requests: write
  checks: write

concurrency:
  group: prevue-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  prevue:
    uses: Doki064/prevue/.github/workflows/prevue-review.yml@v0.6.0
    with:
      engine: copilot-cli
    secrets:
      copilot-github-token: ${{ secrets.COPILOT_GITHUB_TOKEN }}
```

**Permission notes:**
- `contents: write` — required for resolving outdated review threads via GraphQL. Prevue does not commit to your repository.
- `pull-requests: write` — post sticky summary and inline comments.
- `checks: write` — create the `prevue/review` merge-gate check.
- Do **not** use `secrets: inherit` — pass only the named secret for your engine.

**To use Claude Code CLI instead**, replace the `with:` / `secrets:` block:

```yaml
    with:
      engine: claude-code-cli
    secrets:
      claude-code-oauth-token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## Step 2 — Add the secret to your repository

Go to **Settings → Secrets and variables → Actions → New repository secret** and add the secret matching your chosen engine:

| Engine | Secret name |
|--------|-------------|
| `copilot-cli` | `COPILOT_GITHUB_TOKEN` |
| `claude-code-cli` | `CLAUDE_CODE_OAUTH_TOKEN` |
| `cursor-cli` | `CURSOR_API_KEY` |

The secret name in your repository settings must match the name in the `secrets:` block of your caller workflow exactly.

## Step 3 — Add the Prevue config file

Create `.github/prevue.yml` on your **default branch** (not just on a feature branch — Prevue reads config from the PR base ref for security).

Copy the minimal starter below, or use the [full annotated example](./examples/prevue.yml):

```yaml
review:
  max_input_tokens: 120000
  output_reserve_tokens: 12000
  min_severity_to_comment: warning
  min_severity_to_fail: null
  max_inline_comments: 10
  incremental: true
  resolve_outdated: true
  max_known_issues: 20

skills:
  exclude: []
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50

classification:
  fallback:
    enabled: true
    model: null

engine:
  name: copilot-cli

skip:
  review_bots: []
  skip_labels:
    - skip-review
  skip_title_patterns: []
```

Commit this file to your default branch before opening a test PR. Config changes on a PR head branch take effect only after merge.

## Step 4 — Open a test PR

Open a non-draft pull request that touches at least one non-ignored file. The workflow triggers on `opened`, `synchronize`, `reopened`, and `ready_for_review` events.

## Verifying it works

After the workflow runs, check these three places:

**1. Actions tab — workflow run**

Open the `Prevue Review` workflow run. Successful output looks like:

- `Pre-flight: head changed or no marker — full install` (first run)
- `Install engine CLI` step completes
- `Run review` step completes with exit 0

If the run is skipped (shows as green but no steps ran), the PR may be from a fork (unsupported in v1) or the PR was in draft state.

**2. PR — sticky summary comment**

Prevue posts a sticky comment titled `Prevue Review`. It includes:

- A verdict line (`pass`, `neutral`, or `fail`)
- A **Coverage** section listing which files were reviewed and which were skipped due to token budget
- Open findings with severity and fingerprints

**3. PR — Checks tab**

Look for the `prevue/review` check (not the `prevue / review` job check). The Python-posted check is what you require in branch protection — the Actions job check is a separate entry and should not be the required gate.

| Check result | Meaning |
|--------------|---------|
| `pass` | No findings at or above `min_severity_to_fail` |
| `neutral` | Skipped (draft, bot, label, title), or partial review with no threshold-triggering findings |
| `fail` | At least one finding at or above `min_severity_to_fail` |

If the Coverage section says "⚠️ Partial review — some files not reviewed", some files were dropped due to the token budget. Raise `review.max_input_tokens` or add `labels` globs for high-risk paths so they pack with higher priority.

## What happens on each subsequent PR

- **On each push:** Prevue reviews only files changed since the last reviewed SHA (`incremental: true` default). Same-SHA re-runs skip engine CLI install entirely.
- **Outdated threads:** When findings are resolved or go stale, Prevue collapses the inline review threads (`resolve_outdated: true` default).
- **Skip labels:** Add the `skip-review` label to a PR to skip review for that PR. Customize the list in `skip.skip_labels`.

## Common setup issues

### Workflow runs but no `prevue/review` check appears

The Python step may have exited early. Check the `Run review` step logs for error output. Common causes:

- Missing or wrong secret name (the secret name in repository settings must match exactly)
- `COPILOT_GITHUB_TOKEN` is the Actions `GITHUB_TOKEN` instead of a user-owned fine-grained PAT — Copilot CLI requires `github_pat_` prefix

### `prevue/review` check is `neutral` on first run

The PR may have matched a skip condition (`skip_labels`, `skip_title_patterns`) or no non-ignored files changed. Check the sticky summary comment for the skip reason.

### `contents: write` permission error

If you see a GraphQL 403 on thread resolution, ensure your caller workflow grants `contents: write` (not `contents: read`). This scope is required for the `resolveReviewThread` mutation and was verified live against the GitHub API. If you cannot grant write scope, set `review.resolve_outdated: false` in `.github/prevue.yml`.

### Config changes not taking effect

Prevue reads `.github/prevue.yml` from the **PR base ref** (your default branch), not the PR head. Commit config changes to your default branch first; they take effect on the next PR opened after the merge.

## Optional: enable `/prevue` commands

Phase 8 adds on-demand commands via PR issue comments (`/prevue review`, `/prevue dismiss <id>`, `/prevue resolve <id>`). This requires a separate caller workflow. Copy the template from the Prevue repo and pin `ref:` to a release tag — see [consumer-setup.md](./consumer-setup.md) for the full snippet and permission requirements.

## Next steps

| Goal | Doc |
|------|-----|
| Tune token budgets, severity gates, skip rules | [configuration.md](./configuration.md) |
| Add custom review skills for your codebase | [skills.md](./skills.md) |
| `/prevue` commands, branch protection, upgrade notes | [consumer-setup.md](./consumer-setup.md) |
| Understand the pipeline internals | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Threat model, trust boundaries, D-08 tool posture | [security.md](./security.md) |
| Develop and contribute to Prevue itself | [DEVELOPMENT.md](./DEVELOPMENT.md) |
