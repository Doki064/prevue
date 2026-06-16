<!-- generated-by: gsd-doc-writer -->

# Getting Started

Get Prevue running locally for development and testing. To wire Prevue into a consumer repository for production PR reviews, see [consumer-setup.md](./consumer-setup.md).

## Prerequisites

| Tool | Version | Required for |
|------|---------|--------------|
| **Python** | `>=3.12` | Framework runtime (`requires-python` in `pyproject.toml`) |
| **uv** | `0.11.x` recommended (CI pins `0.11.21`) | Dependency install and `uv run` commands |
| **Git** | any recent | Clone and contribute |

**Optional — only for live engine runs** (not needed for unit tests):

| Tool / credential | When needed |
|-------------------|-------------|
| **Node.js** `>=22` | Installing `copilot-cli` or `claude-code-cli` locally |
| **`COPILOT_GITHUB_TOKEN`** | Fine-grained user PAT with Copilot Requests (`github_pat_…`) for `copilot-cli` |
| **`ANTHROPIC_API_KEY`** | Claude Code CLI adapter |
| **`CURSOR_API_KEY`** | Cursor CLI adapter |
| **`GITHUB_TOKEN`** | GitHub API access when running `prevue review` outside Actions |
| **`GITHUB_EVENT_PATH`** + **`GITHUB_REPOSITORY`** | PR event context for `prevue review` (normally set by Actions) |

Install uv if you do not have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Doki064/prevue.git
cd prevue
```

2. Install dependencies (creates a virtualenv and installs dev tools):

```bash
uv sync --locked
```

`uv sync --locked` installs the `prevue` CLI (`uv run prevue …`) and dev dependencies (`pytest`, `ruff`, `responses`).

## First run

Confirm the install with the test suite — no engine tokens or GitHub credentials required:

```bash
uv run pytest -q
```

Explore the CLI:

```bash
uv run prevue review --help
uv run prevue preflight --help
```

Run the same checks CI runs before opening a PR:

```bash
./scripts/ci-local.sh
```

That script runs `uv sync --locked`, pytest with coverage, ruff check/format, actionlint, and zizmor on workflow YAML.

### Optional: live `prevue review` locally

Unit tests mock GitHub and engine boundaries. A real review needs a PR event payload and API access:

```bash
export GITHUB_TOKEN="ghp_…"                    # repo-scoped token with pull-requests + checks access
export GITHUB_REPOSITORY="owner/repo"
export GITHUB_EVENT_PATH="/path/to/event.json" # pull_request webhook JSON
export PREVUE_ENGINE="copilot-cli"             # or claude-code-cli, cursor-cli
export COPILOT_GITHUB_TOKEN="github_pat_…"     # when using copilot-cli

uv run prevue review
```

Install the matching engine CLI first (see `.github/scripts/install-engine-cli.sh`). For day-to-day framework work, prefer `uv run pytest` over local live reviews.

## Common setup issues

### `requires-python >=3.12` install failure

**Symptom:** `uv sync` or package resolution fails on an older Python.

**Fix:** Install Python 3.12 or newer and point uv at it (`uv python install 3.12`, or set `UV_PYTHON`).

### `prevue review` exits with missing env vars

**Symptom:** `KeyError` or errors referencing `GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, or `GITHUB_TOKEN`.

**Fix:** Export the variables above, or use fixture payloads under `tests/fixtures/` (for example `event_pull_request.json`) with a PAT that can read the target PR. For framework development, run `uv run pytest` instead.

### Engine auth errors on live runs

**Symptom:** `COPILOT_GITHUB_TOKEN must be a fine-grained…` or similar from an engine adapter.

**Fix:** Set the secret for your chosen engine (`COPILOT_GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, or `CURSOR_API_KEY`). Copilot requires a **user-owned** fine-grained PAT — not the Actions `GITHUB_TOKEN`. See [consumer-setup.md](./consumer-setup.md#per-engine-named-secrets).

### `./scripts/ci-local.sh` fails on actionlint

**Symptom:** `actionlint not found and go is not installed`.

**Fix:** Install [actionlint](https://github.com/rhysd/actionlint#installation) or Go (the script auto-installs actionlint via `go install`). Workflow YAML linting is optional for quick pytest-only loops.

## Next steps

| Goal | Doc |
|------|-----|
| Adopt Prevue in your repo (caller workflow, secrets, merge gate) | [consumer-setup.md](./consumer-setup.md) |
| Tune `prevue.yml` knobs and defaults | [configuration.md](./configuration.md) |
| Understand pipeline modules and data flow | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Local dev workflow, lint, and PR conventions | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Test layout, coverage, and CI test commands | [TESTING.md](./TESTING.md) |
| Custom review skills | [skills.md](./skills.md) |
| Threat model and trust boundaries | [security.md](./security.md) |
