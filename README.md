<!-- generated-by: gsd-doc-writer -->
# Prevue

Token-efficient AI PR review for GitHub Actions — classify the diff, load only matching review skills, run your chosen engine, and post a sticky summary, inline comments, and an optional merge gate.

[![CI](https://github.com/Doki064/prevue/actions/workflows/ci.yml/badge.svg)](https://github.com/Doki064/prevue/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What it does

On each pull request, Prevue:

1. **Fetches the diff** via the GitHub API (no PR-head checkout for review content)
2. **Classifies changed files** with deterministic glob rules and an optional LLM fallback
3. **Routes to review skills** — built-in and consumer-defined `SKILL.md` bundles loaded only for matching labels
4. **Packs the diff** under a token budget, prioritizing high-risk paths
5. **Runs an AI engine** — `copilot-cli`, `claude-code-cli`, or `cursor-cli`
6. **Posts results** — sticky summary comment, inline review comments, and a `prevue/review` check run

**Incremental review** (default) re-reviews only files changed since the last sticky marker SHA, carries forward open findings, and skips engine CLI install on same-SHA no-op re-runs.

## Quick start

Add a caller workflow that invokes the reusable workflow. Pin to a [release tag](https://github.com/Doki064/prevue/releases) — do not use `@main`.

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

Full setup — engine secrets, optional `/prevue` commands, CI gating — is in [docs/consumer-setup.md](docs/consumer-setup.md).

## How it runs

```
pull_request → classify → route skills → pack diff → engine review → sticky + inline + check
```

The reusable workflow (`.github/workflows/prevue-review.yml`) checks out the framework and consumer base ref, then runs `uv run prevue review`. All review logic lives in Python.

## Features

| Capability | Description |
|------------|-------------|
| **Classification** | Gitignore-style glob rules map files to labels (`security`, `frontend`, `backend`, …); LLM fallback for unmatched paths in the packed set |
| **Skill routing** | Loads only skills whose `applies-to` labels match the PR; consumer overrides under `.github/prevue/skills/` |
| **Inline comments** | Findings placed on changed lines via unified-diff positions; capped by `review.max_inline_comments` |
| **Merge gate** | `prevue/review` check run — pass/fail from `review.min_severity_to_fail` (independent of inline comment threshold) |
| **Multi-engine** | Pluggable adapters: Copilot CLI, Claude Code CLI, Cursor CLI |
| **Incremental review** | Diff scoped to changes since last reviewed SHA; outdated threads resolved when enabled |
| **`/prevue` commands** | Optional issue-comment workflow for force re-review, dismiss findings, resolve threads |

Configure thresholds, skills, and classification in `.github/prevue.yml` on your default branch. See [docs/configuration.md](docs/configuration.md) and [docs/skills.md](docs/skills.md).

## Supported triggers

| Trigger | Same-repo PR | Fork PR |
|---------|--------------|---------|
| `pull_request` (`opened`, `synchronize`, `reopened`, `ready_for_review`) | **Supported** | **Unsupported in v1** |

**Same-repo PRs** run the full pipeline: diff fetch, classify, engine review, sticky comment, inline comments, and check run.

**Fork PRs** are unsupported in v1. GitHub gives fork `pull_request` runs a read-only `GITHUB_TOKEN` and does not expose repository secrets, so comment writes would 403 and engine tokens are absent. Prevue detects `head.repo != base.repo` at startup, prints `Fork PRs are unsupported in v1; skipping review.`, and exits 0 without engine spend.

Prevue uses `pull_request` only — never `pull_request_target`.

## Required permissions

Consumer workflows need:

```yaml
permissions:
  contents: write      # resolve outdated review threads (GraphQL)
  pull-requests: write # fetch PR metadata, post sticky and inline comments
  checks: write        # prevue/review merge gate
```

Diff content is fetched via the REST API; the workflow does not check out the PR head ref for review.

## Engine authentication

Each engine requires its own secret passed through the reusable workflow — never `secrets: inherit`.

| Engine | Workflow secret | Env var |
|--------|-----------------|---------|
| `copilot-cli` | `copilot-github-token` | `COPILOT_GITHUB_TOKEN` |
| `claude-code-cli` | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
| `cursor-cli` | `cursor-api-key` | `CURSOR_API_KEY` |

Copilot CLI needs a **fine-grained, user-owned** PAT with **Copilot Requests** permission (prefix `github_pat_`), not the Actions `GITHUB_TOKEN`. Details in [docs/consumer-setup.md](docs/consumer-setup.md).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Prerequisites, install, first run |
| [docs/consumer-setup.md](docs/consumer-setup.md) | Adopt Prevue, engine secrets, `/prevue` commands |
| [docs/configuration.md](docs/configuration.md) | `prevue.yml` reference — budgets, gate, skills |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline, components, data flow |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local dev workflow, project layout |
| [docs/TESTING.md](docs/TESTING.md) | pytest, fixtures, CI expectations |
| [docs/skills.md](docs/skills.md) | Custom and override skills |
| [docs/security.md](docs/security.md) | Threat model and trust boundaries |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

## Local development

```bash
git clone https://github.com/Doki064/prevue.git
cd prevue
uv sync --locked
uv run pytest
uv run prevue review --help
```

Run the same checks as CI before opening a PR:

```bash
./scripts/ci-local.sh
```

See [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) for prerequisites and environment setup. Live engine runs need the appropriate API token and a PR event context (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`); unit tests mock those boundaries.

## License

MIT — see [LICENSE](LICENSE).
