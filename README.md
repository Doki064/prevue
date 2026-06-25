<!-- generated-by: gsd-doc-writer -->
# Prevue

Token-efficient AI PR review for GitHub Actions — pack the diff under a token budget, load only the skills whose `applies-to` globs match changed paths, classify for metadata, run your chosen engine, and post a sticky summary, inline comments, and a merge-gate check run.

[![CI](https://github.com/Doki064/prevue/actions/workflows/ci.yml/badge.svg)](https://github.com/Doki064/prevue/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Why Prevue

Most AI review tools send the entire diff plus every guideline document to the model, burning context budget on irrelevant instructions. Prevue inverts this:

- **Pack first, then review** — the diff is trimmed to a configurable token budget before the engine call; high-priority paths (security, matched skills) win budget contention.
- **Load only matching skills** — review instructions come from skill files whose `applies-to` path globs match the packed file set. A Python-only PR does not load frontend or infra guidelines.
- **Deterministic classification with LLM fallback** — gitignore-style glob rules handle common cases at near-zero token cost; an optional LLM fallback classifies the remainder.
- **Review quality parity** — per-finding inline comments, a sticky summary with open/resolved tracking, and a configurable merge gate.

## What it does

On each pull request Prevue:

1. **Fetches the diff** via the GitHub REST API — no PR-head checkout for review content
2. **Classifies all filtered files** with deterministic glob rules (`security`, `frontend`, `backend`, `data`, `infra`); LLM fallback for unmatched paths — before packing so routing covers every file
3. **Packs the diff** under `review.max_input_tokens` (default 120 000 tokens), weighting files by label rank and skill `applies-to` coverage
4. **Routes labels to bundles** and selects skills via hybrid keyword-floor + LLM escalation for routed bundles; `applies-to` path globs only for non-routed bundles
5. **Assembles the prompt** from selected skills and sends it to the configured engine
6. **Runs an AI engine** — `copilot-cli`, `claude-code-cli`, or `cursor-cli`
7. **Posts results** — sticky summary comment, inline review comments (capped by `review.max_inline_comments`), and a `prevue/review` check run

**Incremental review** (default on) re-reviews only files changed since the last sticky-marker SHA, carries forward open findings, and resolves outdated threads when `review.resolve_outdated` is enabled. Same-SHA re-runs skip engine CLI install entirely.

## Quick start

Add a caller workflow in your repo that invokes the reusable workflow. Pin to a [release tag](https://github.com/Doki064/prevue/releases) — do not use `@main`.

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
pull_request
  → load skills (framework + consumer overrides)
  → pack diff under token budget
  → select skills by applies-to globs + hybrid routing
  → classify (deterministic globs → LLM fallback for remainder)
  → engine review (single call or multi-call if configured)
  → sticky summary + inline comments + prevue/review check
```

The reusable workflow (`.github/workflows/prevue-review.yml`) checks out the Prevue framework and the consumer base ref separately, then runs `uv run prevue review`. All review logic lives in Python.

## Features

| Capability | Description |
|------------|-------------|
| **Classification** | Gitignore-style glob rules map files to labels (`security`, `frontend`, `backend`, `data`, `infra`); LLM fallback for unmatched paths |
| **Skill selection** | Loads only skills whose `applies-to` path globs match packed files; consumer overrides and additions under `.github/prevue/skills/` |
| **Diff packing** | Files sorted by label rank and skill coverage; lowest-priority files dropped first when over `review.max_input_tokens` |
| **Inline comments** | Findings placed on changed lines via unified-diff positions; capped by `review.max_inline_comments` |
| **Merge gate** | `prevue/review` check run — pass/fail driven by `review.min_severity_to_fail`, evaluated against all findings |
| **Multi-engine** | Pluggable adapters: Copilot CLI, Claude Code CLI, Cursor CLI (Gemini CLI registered but not yet functional) |
| **Multi-call** | `review.max_review_calls` splits large diffs across parallel engine calls; findings merged and deduplicated |
| **Incremental review** | Diff scoped to changes since last reviewed SHA; outdated threads resolved automatically |
| **`/prevue` commands** | Optional issue-comment workflow for force re-review, dismiss findings, resolve threads |
| **Skip policy** | Skip review for bots, PR labels, or title regex patterns via `skip` config |

Configure thresholds, skills, and classification in `.github/prevue.yml` on your default branch. See [docs/configuration.md](docs/configuration.md) and [docs/skills.md](docs/skills.md).

## Supported triggers

| Trigger | Same-repo PR | Fork PR |
|---------|--------------|---------|
| `pull_request` (`opened`, `synchronize`, `reopened`, `ready_for_review`) | **Supported** | **Unsupported in v1** |

Fork PRs are unsupported in v1. GitHub gives fork `pull_request` runs a read-only `GITHUB_TOKEN` and does not expose repository secrets. Prevue detects `head.repo != base.repo` at startup and exits 0 without engine spend.

Prevue uses `pull_request` only — never `pull_request_target`.

## Required permissions

```yaml
permissions:
  contents: write      # resolve outdated review threads (GraphQL resolveReviewThread)
  pull-requests: write # fetch PR metadata, post sticky and inline comments
  checks: write        # prevue/review merge gate
```

`contents: write` is required for the GraphQL `resolveReviewThread` mutation. Prevue does not commit to the repository.

## Engine authentication

Pass only the secret for the engine you use — never `secrets: inherit`.

| Engine | Workflow secret | Environment variable |
|--------|-----------------|----------------------|
| `copilot-cli` | `copilot-github-token` | `COPILOT_GITHUB_TOKEN` |
| `claude-code-cli` | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
| `cursor-cli` | `cursor-api-key` | `CURSOR_API_KEY` |

Copilot CLI requires a **fine-grained, user-owned PAT** with **Copilot Requests** permission (prefix `github_pat_`), not the Actions `GITHUB_TOKEN`. Details in [docs/consumer-setup.md](docs/consumer-setup.md).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Prerequisites, install, first run |
| [docs/consumer-setup.md](docs/consumer-setup.md) | Adopt Prevue, engine secrets, `/prevue` commands |
| [docs/configuration.md](docs/configuration.md) | `prevue.yml` reference — budgets, gate, skills, skip |
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

Run the same checks as CI locally:

```bash
./scripts/ci-local.sh
```

See [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) for prerequisites and environment setup. Live engine runs need the appropriate API token and a PR event context (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`); unit tests mock those boundaries.

## License

MIT — see [LICENSE](LICENSE).
