# Prevue

Token-efficient AI PR review framework for GitHub Actions.

Phase 1 is a walking skeleton: on a pull request event, Prevue fetches the diff via the GitHub API (no PR-head checkout), runs a Copilot CLI review, and posts or updates one sticky summary comment on the PR.

## How it runs

`pull_request` event → fetch diff via API → Copilot CLI review → sticky comment upsert.

The workflow (`.github/workflows/review.yml`) only sets up the runner and invokes `uv run prevue review`; all logic lives in Python.

## Supported triggers

| Trigger | Same-repo PR | Fork PR |
|---------|--------------|---------|
| `pull_request` (`opened`, `synchronize`, `reopened`) | **Supported** | **Unsupported in v1** |

**Same-repo PRs** run the full loop: diff fetch, Copilot review, sticky comment create/update.

**Fork PRs** are unsupported in v1. GitHub gives fork `pull_request` runs a read-only `GITHUB_TOKEN` and does not expose repository secrets, so comment writes would 403 and `COPILOT_GITHUB_TOKEN` is absent. Prevue detects `head.repo != base.repo` at startup, prints `Fork PRs are unsupported in v1; skipping review.`, and exits 0 without fetching the diff, calling Copilot, or posting a comment.

Prevue uses `pull_request` only — never `pull_request_target`.

## Required permissions

The workflow needs exactly:

```yaml
permissions:
  contents: read
  pull-requests: write
```

- `contents: read` — checkout Prevue's own code on the runner
- `pull-requests: write` — fetch PR metadata and post/update the sticky comment

Diff content is fetched via the REST API as data; the workflow does not check out the PR head ref.

## `COPILOT_GITHUB_TOKEN` setup

Copilot CLI auth requires a **fine-grained, user-owned** personal access token — not a classic `ghp_` PAT and not the Actions `GITHUB_TOKEN` (which lacks Copilot entitlement and would shadow the Copilot token if used).

1. **Copilot seat** — the PAT owner must have an active GitHub Copilot subscription.
2. **Create a fine-grained PAT** (Settings → Developer settings → Fine-grained tokens):
   - Resource owner: your personal account (not an organization token)
   - Repository access: the repo(s) where Prevue runs
   - Permissions: enable **Copilot Requests**
3. **Confirm prefix** — the token must start with `github_pat_` (confirmed by the Phase 1 spike). Classic `ghp_` tokens are rejected.
4. **Add as a repository secret** — name it exactly `COPILOT_GITHUB_TOKEN` (Settings → Secrets and variables → Actions).

The review step sets `GITHUB_TOKEN: ${{ github.token }}` (GitHub API) and `COPILOT_GITHUB_TOKEN: ${{ secrets.COPILOT_GITHUB_TOKEN }}` (Copilot CLI) as separate environment variables so the Actions token never shadows the Copilot token.

**Important:** If `GITHUB_TOKEN` is set in the environment, the Copilot CLI attempts to use it first (before `COPILOT_GITHUB_TOKEN`). The workflow passes both separately to avoid shadowing. Never set both to the same value, and do not export `GITHUB_TOKEN` in a step that also runs Copilot unless you intend the Actions token for API calls only.

## Phase 1 scope

What works today:

- Sticky summary comment with Verdict / Review / Metadata sections
- Copilot CLI adapter (zero-tool, diff inlined in prompt)
- Fork guard and fail-closed engine errors (failed run, comment untouched)

Not in Phase 1:

- Classification or skill routing
- Inline review comments
- Pass/fail checks or merge gate
- Fork PR support
- Consumer reusable-workflow packaging

## Local development

```bash
uv sync --locked
uv run pytest
uv run prevue review --help
```

Run the same checks as CI before opening a PR:

```bash
./scripts/ci-local.sh
```

Requires `go` (actionlint) and `zizmor` or Docker (workflow security scan). Python steps use `uv` only.

Live Copilot runs require `COPILOT_GITHUB_TOKEN` and a PR event context (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`); unit tests mock those boundaries.
