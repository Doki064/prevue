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

Fork PRs are **not reviewed in v1**. The reusable workflow self-guards on `head.repo == github.repository`, so PRs from forks are skipped automatically — no caller-side `if:` guard is required.

## `/prevue` commands (issue comments)

Phase 8 adds an optional **second workflow** for on-demand commands via PR comments. This is separate from the reusable `prevue-review.yml` caller — add `.github/workflows/prevue-command.yml` to your repo (copy from [Prevue's template](https://github.com/Doki064/prevue/blob/main/.github/workflows/prevue-command.yml) and pin `ref:` to a release tag).

### Commands

| Command | Purpose |
|---------|---------|
| `/prevue review` | Force a **full** re-review of the PR (ignores incremental marker; resets sticky head SHA) |
| `/prevue dismiss <id> [reason: text]` | Dismiss a finding by fingerprint or thread id; `reason:` required for 🔴 error-severity findings |
| `/prevue resolve <id>` | Resolve a single outdated review thread by fingerprint or thread id (best-effort) |

### Write access required

Only collaborators with **write**, **maintain**, or **admin** permission may run commands. The workflow pre-filters on `author_association` (`OWNER`, `MEMBER`, `COLLABORATOR`); Python re-checks via the GitHub collaborator-permission API. Unauthorized commenters receive a one-line reply and **no engine run** occurs.

On personal repos, invited write collaborators are labeled **`COLLABORATOR`** (not read-only). Read-only access is enforced by the permission API, not by dropping `COLLABORATOR` from the workflow gate.

### Fork PRs refused

Commands on fork PRs are refused with no engine spend (same SECR-01 posture as automatic review). The command workflow runs in **default-branch context** and never checks out the PR head or merge ref — diff and state are fetched via the API only.

### Minimal scopes (same as review)

| Permission | Scope |
|------------|-------|
| `contents` | `write` |
| `pull-requests` | `write` |
| `checks` | `write` |

`contents: write` is required for LIFE-04 (`resolveReviewThread`). Verified on live dogfood (PR #16, 2026-06): `pull-requests: write` alone returns GraphQL **403 Forbidden**; with `contents: write`, thread resolution succeeds. Prevue only uses write scope for GraphQL lifecycle mutations — not for committing to the repository.

Do **not** use `pull_request_target` or `secrets: inherit`. Pass only the named engine secret(s) you need.

### Example workflow snippet

Pin Prevue to a [release tag](https://github.com/Doki064/prevue/releases) — do not use `@main`.

```yaml
name: Prevue Command

on:
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  checks: write

jobs:
  command:
    if: >-
      ${{ github.event.issue.pull_request
          && startsWith(github.event.comment.body, '/prevue')
          && contains(fromJson('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association) }}
    runs-on: ubuntu-latest
    steps:
      # Copy remaining steps from Prevue's prevue-command.yml template (framework checkout,
      # consumer default-branch checkout, uv sync, engine install on `/prevue review` only,
      # prevue command).
      # Set vars.PREVUE_REF to your pinned release (e.g. v0.6.0) and vars.PREVUE_ENGINE if not copilot-cli.
```

The `/prevue review` path installs the engine **unconditionally** (no same-SHA install skip) so forced reviews always have a CLI available.

Optional inputs:

| Input | Default | Purpose |
|-------|---------|---------|
| `engine` | `copilot-cli` | Review engine (`copilot-cli`, `claude-code-cli`, `cursor-cli`) |
| `config-path` | `.github/prevue.yml` | Path to Prevue config inside the consumer repo |
| `prevue-ref` | `v0.6.0` | Prevue branch/tag/SHA for self-checkout (use your feature branch pre-release) |

`classification.fallback.enabled` defaults to **`true`** — unmatched file paths trigger a cheap LLM classify call before review. Set `enabled: false` in `.github/prevue.yml` for purely deterministic (zero-token) classification.

Include `ready_for_review` in `pull_request.types` so draft→ready PRs trigger a run (re-run alone keeps stale draft payload).

`config-path` must be relative to the consumer checkout (no `..`). It is read from the PR base branch for security, not from the PR head branch. Config edits in the same PR take effect after merge.

## Starter config (prevue.yml)

Prevue loads `.github/prevue.yml` from your **base branch** (see `config-path` above). Copy the starter below or use the full file in the repo:

**Full starter:** [docs/examples/prevue.yml](./examples/prevue.yml)

```yaml
# Minimal copy — see examples/prevue.yml for commented defaults
review:
  max_input_tokens: 120000
  output_reserve_tokens: 12000
  min_severity_to_comment: warning
  min_severity_to_fail: null
  max_inline_comments: 10

skills:
  exclude: []   # bundle/filename keys, e.g. security/committed-secrets.md
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

- **Knob semantics:** [configuration.md](./configuration.md)
- **Custom skills:** [skills.md](./skills.md)
- **`skills.exclude`:** list paths like `security/committed-secrets.md` to drop a skill regardless of built-in or consumer source.

### Incremental review lifecycle

Phase 8 adds three optional knobs under `review:` (defaults shown):

| Knob | Default | Purpose |
|------|---------|---------|
| `incremental` | `true` | When `true`, only files changed since the last-reviewed head SHA are re-reviewed on each push. Set `false` to force a whole-PR review every run. |
| `resolve_outdated` | `true` | When `true`, Prevue resolves (collapses) inline review threads for outdated findings that are no longer reported. Set `false` to disable LIFE-04 thread resolution entirely. |
| `max_known_issues` | `20` | Cap on the known-issues dedupe hint list injected into the engine prompt on incremental runs. |

Example:

```yaml
review:
  incremental: true          # default — incremental scoping on synchronize pushes
  resolve_outdated: true     # default — resolve outdated inline threads (LIFE-04)
  max_known_issues: 20       # default — cap on engine dedupe hints
  max_input_tokens: 120000
  # ... other review knobs
```

The sticky comment marker stores the last-reviewed head SHA (`<!-- prevue:sticky head=<sha> -->`). On rebase, force-push, or squash (when the stored SHA is no longer an ancestor of head), Prevue falls back to a full base..head review and resets the marker.

### Outdated thread resolution scope

LIFE-04 (`resolveReviewThread`) requires **`contents: write`** on the workflow token in addition to `pull-requests: write`. Live verification (2026-06, dogfood PR #16) showed `pull-requests: write` alone returns GraphQL **403 Forbidden** on every resolve attempt; with `contents: write`, authoritative full-run resolve succeeds and stale threads collapse.

Prevue uses `contents: write` only for GraphQL lifecycle mutations — not for pushing commits. If you cannot grant write scope, set `review.resolve_outdated: false` in `.github/prevue.yml` to disable LIFE-04 entirely; carry-forward and incremental scoping still work.

### Review summary timeline cards

Each batched inline post (`create_review` with `event: COMMENT`) adds a timeline entry such as *"Prevue posted N new inline comment(s) — see the review summary."* Resolving inline threads collapses the diff threads but **does not remove** that card.

**Spike result (2026-06, PR #16):** submitted PR reviews **cannot be deleted** via GitHub API — GraphQL `deletePullRequestReview` returns **UNPROCESSABLE** (Actions `GITHUB_TOKEN`) or **403 Forbidden** (user token); REST `DELETE .../reviews/{id}` returns **404** for submitted reviews. Prevue does not attempt cleanup; there is no API remediation.

Existing timeline cards on long-lived PRs may accumulate; there is no API remediation. Mitigations: resolve threads so inlines collapse; sticky comment remains the canonical summary.

### ⚠️ Tight budgets can skip unclassified files

Files are packed by risk priority (label rules + skill `applies-to`) **before** the LLM classification fallback runs. Under a tight `max_input_tokens`, a file that matches **no** deterministic rule or skill is packed last and may be **budget-skipped entirely** — so the LLM fallback never sees it and it is **not reviewed**. The check can still conclude neutral/pass with zero findings while those paths went unreviewed; the sticky comment's **Coverage** section lists exactly which files were skipped.

To avoid silently dropping risk-bearing paths: add an explicit `labels` glob for sensitive patterns (e.g. `**/auth/**`, `**/*secret*`) so they pack ahead of generic files, or raise `review.max_input_tokens`. Always read the Coverage section on partial reviews — the verdict reads **"⚠️ Partial review — some files not reviewed"** when files were skipped with no findings.

The `/prevue review` path installs the engine only when the comment verb is `review` (status/help skip the install).

### Upgrading from v0.6.x (breaking)

**v0.7 requires `contents: write`.** Phase 8 LIFE-04 (`resolveReviewThread`) fails with GraphQL **403** when callers still grant `contents: read`. Update your caller workflow permissions before upgrading:

```yaml
permissions:
  contents: write   # was: read — required for LIFE-04 thread resolve
  pull-requests: write
  checks: write
```

Alternative: stay on `contents: read` and set `review.resolve_outdated: false` in `.github/prevue.yml` (carry-forward and incremental scoping still work; stale threads are not auto-resolved).

## Required permissions

The caller workflow must grant these scopes to the reusable workflow:

| Permission | Scope | Why |
|------------|-------|-----|
| `contents` | `write` | Checkout consumer base ref **and** GraphQL `resolveReviewThread` (LIFE-04). Read-only `contents: read` is insufficient — live verification returned 403 Forbidden on thread resolve. Prevue does not commit to your repository. |
| `pull-requests` | `write` | Post review comments, sticky summary, and check metadata |
| `checks` | `write` | Create pass/fail check run |

Do **not** use `secrets: inherit`. Pass only the named secret for your chosen engine.

## Consumer config/skills require a base-ref checkout

The bundled reusable workflow sets **`PREVUE_CONSUMER_ROOT`** automatically (to a base-ref checkout), so your `.github/prevue.yml` and `.github/prevue/skills/` are loaded. If you integrate the Python entrypoint into your **own** workflow and do **not** set `PREVUE_CONSUMER_ROOT`, Prevue runs with **framework defaults**: consumer config is ignored and consumer skills are skipped (a SKIL-04 base-ref safeguard — `GITHUB_WORKSPACE` may point to the PR merge ref, so it is never used as the trust root). The skip is logged to stderr in the Action log. To activate your custom thresholds and skills, set `PREVUE_CONSUMER_ROOT` to a checkout of the trusted base ref.

## Branch protection

Require the **`prevue/review`** check (posted by Prevue Python), not the **`prevue / review`** workflow job check. On skip, Prevue posts `prevue/review` as **neutral**; the Actions job still exits 0 and its job check shows **success** — that is expected and must not be the required gate.

**Partial reviews are neutral by design.** When a PR exceeds the token budget, Prevue reviews the highest-priority files and reports the rest in the sticky comment's Coverage section; with no threshold-triggering findings the check concludes **neutral**, not failure. If your branch protection treats neutral as success, a PR with budget-skipped files can merge — read the Coverage section, or raise `review.max_input_tokens` so more files fit. (If the sticky comment itself fails to post, the skipped-file count is surfaced in the check summary instead.)

## Engine tool-posture check before merge gates (D-08)

Before you make `prevue/review` a **required** check, run a live tool-posture verification of each engine you enable. Prevue's adapters pass **no `--allow-tool` flags** (statically tested), but a headless engine CLI's default tool access (network, GitHub API, shell) is **vendor-controlled** and cannot be proven by source scan alone — see the D-08 row in [SECURITY.md](../SECURITY.md).

**Required once per engine, in a sandbox repo:**

1. Open a throwaway PR that the engine reviews.
2. Confirm in the Action logs that the engine made **no unexpected tool calls** (no outbound network beyond the model API, no GitHub writes outside Prevue's own check/comment calls).
3. Only then enable `prevue/review` as a required gate on protected branches.

Treat this as **mandatory, not optional**, when enabling merge gates.

## Per-engine named secrets

| Engine | Secret name | Maps to |
|--------|-------------|---------|
| `copilot-cli` | `copilot-github-token` | `COPILOT_GITHUB_TOKEN` |
| `claude-code-cli` | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
| `cursor-cli` | `cursor-api-key` | `CURSOR_API_KEY` |

### Cursor CLI supply-chain note

The `cursor-cli` engine installs via Cursor's official shell installer (`https://cursor.com/install`). Unlike `copilot-cli` and `claude-code-cli` (pinned npm versions), Cursor publishes **no versioned npm package or installer checksum**, so this step cannot be version-pinned today. The workflow downloads the installer to a file before executing it (rather than piping straight to `bash`), but the residual supply-chain risk remains: a compromise of the install endpoint would run on the runner with access to `CURSOR_API_KEY`. Prefer `copilot-cli` or `claude-code-cli` where pinning matters.

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

### Bot review policy (`skip.review_bots`)

`skip.review_bots` is an **allowlist of bot logins to review**, not a blocklist to skip. By default it is empty, so **every bot-authored PR is skipped**. To review a specific bot (e.g. a release bot), add its login:

```yaml
# .github/prevue.yml
skip:
  review_bots:
    - release-please[bot]   # only listed bots are reviewed; all other bots skipped
```
