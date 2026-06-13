# Consumer Setup

Adopt Prevue in your repository with a minimal caller workflow that invokes the reusable workflow.

## Minimal caller snippet

Pin to a [release tag](https://github.com/Doki064/prevue/releases) — do not use `@main`.

```yaml
name: Prevue Review

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read
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

Optional inputs:

| Input | Default | Purpose |
|-------|---------|---------|
| `engine` | `copilot-cli` | Review engine (`copilot-cli`, `claude-code-cli`, `cursor-cli`) |
| `config-path` | `.github/prevue.yml` | Path to Prevue config inside the consumer repo |
| `prevue-ref` | `v0.6.0` | Prevue branch/tag/SHA for self-checkout (use your feature branch pre-release) |

`classification.fallback.enabled` defaults to **`true`** — unmatched file paths trigger a cheap LLM classify call before review. Set `enabled: false` in `.github/prevue.yml` for purely deterministic (zero-token) classification.

Include `ready_for_review` in `pull_request.types` so draft→ready PRs trigger a run (re-run alone keeps stale draft payload).

`config-path` must be relative to the consumer checkout (no `..`). It is read from the PR base branch for security, not from the PR head branch. Config edits in the same PR take effect after merge.

## Required permissions

The caller workflow must grant these scopes to the reusable workflow:

| Permission | Scope | Why |
|------------|-------|-----|
| `contents` | `read` | Checkout consumer base ref for config and diff |
| `pull-requests` | `write` | Post review comments and sticky summary |
| `checks` | `write` | Create pass/fail check run |

Do **not** use `secrets: inherit`. Pass only the named secret for your chosen engine.

## Branch protection

Require the **`prevue/review`** check (posted by Prevue Python), not the **`prevue / review`** workflow job check. On skip, Prevue posts `prevue/review` as **neutral**; the Actions job still exits 0 and its job check shows **success** — that is expected and must not be the required gate.

## Per-engine named secrets

| Engine | Secret name | Maps to |
|--------|-------------|---------|
| `copilot-cli` | `copilot-github-token` | `COPILOT_GITHUB_TOKEN` |
| `claude-code-cli` | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
| `cursor-cli` | `cursor-api-key` | `CURSOR_API_KEY` |

Example for Claude Code:

```yaml
jobs:
  prevue:
    uses: Doki064/prevue/.github/workflows/prevue-review.yml@v0.6.0
    with:
      engine: claude-code-cli
    secrets:
      anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Skip ≠ auto-merge

Prevue **never merges** pull requests. Skip behavior depends on the skip type:

| Skip type | Where handled | Check posted? |
|-----------|---------------|---------------|
| **Draft PR** | Workflow `if: !draft` guard | No — job does not run |
| **Bot / label / title** | Python `should_skip()` | Yes — neutral `prevue/review` check + sticky reason |

Skipping does not approve or merge the PR — your existing branch protection and human review process still applies.
