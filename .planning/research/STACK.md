# Stack Research

**Domain:** AI PR review framework delivered as a GitHub reusable workflow (Python)
**Researched:** 2026-06-12
**Confidence:** HIGH (all versions verified against PyPI / npm / GitHub releases on research date)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 (floor), run on 3.13 | Framework implementation language | User constraint. 3.12 floor keeps compatibility with all chosen deps (highest floor among them is python-frontmatter's >=3.10) while matching the default Python on `ubuntu-latest` runners. Confidence: HIGH |
| PyGithub | 2.9.1 | GitHub REST API: PR data, changed files, review comments, check runs | The battle-tested standard (7.7k stars, active — v2.9.1 released 2026-04). Covers everything the pipeline needs: `pull.get_files()` for changed-file metadata, `pull.create_review(comments=[...])` for batched inline comments, `repo.create_check_run()` for the pass/fail check. Stable API matters because this framework is consumed by other repos. Confidence: HIGH |
| GitHub reusable workflow (`workflow_call`) | n/a (platform) | Delivery mechanism | Fixed by project constraint. Correct choice vs composite action: the review is a whole job with its own runner, its own `permissions:` block (least-privilege boundary consumers can audit), and explicit named-secret pass-through (`COPILOT_GITHUB_TOKEN`). Composite actions inherit caller permissions and can't declare their own — wrong trust model for an AI tool consumers must trust. Confidence: HIGH |
| GitHub Copilot CLI (`@github/copilot`, npm) | 1.0.60 (1.0.x line, GA since 2026-02-25) | First review-engine adapter | Runs headless on Actions runners: `copilot -p "<prompt>" --no-ask-user --allow-tool=...`, auth via `COPILOT_GITHUB_TOKEN` env var, model via `COPILOT_MODEL`/`--model`. Verified against official GitHub docs. Install in-workflow with `npm install -g @github/copilot` (Node 22+ is preinstalled on runners). Invoke from Python via stdlib `subprocess` — no wrapper library exists or is needed. Confidence: HIGH |
| pydantic | 2.13.4 | Typed models: classification rules, routing config, engine adapter I/O, review findings | The 2026 standard for validated data models. The engine adapter boundary (prompt in → structured findings out) and the consumer-facing rules/skills config are exactly where validation at system boundaries pays off. Confidence: HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unidiff | 0.7.5 | Parse unified diffs into `PatchSet` → files → hunks → lines | Mapping review findings to inline-comment positions (`path` + `line` + `side`). Last release 2023 but the unified diff format is frozen; this is the de-facto standard used by review bots. Use `pull.get_files()[].patch` per-file or the full PR diff (`Accept: application/vnd.github.v3.diff`) as input. Confidence: HIGH |
| pathspec | 1.1.1 | Gitignore-style glob matching for the deterministic classifier | `GitIgnoreSpec.from_lines([...]).match_file(path)` gives Git-exact `**` semantics for rules like `**/*.tsx → frontend`, `terraform/** → infra`, `**/package-lock.json → deps`. Note: 1.x (2026) renamed the pattern factory from "gitwildmatch" to "gitignore" vs the older 0.12 API. Confidence: HIGH |
| python-frontmatter | 1.3.0 | Parse SKILL.md YAML frontmatter + markdown body | Skill loader. One call (`frontmatter.load(path)`) returns metadata dict + content; supports the Agent Skills frontmatter format directly. Active (1.3.0 released 2026-05). Confidence: HIGH |
| PyYAML | 6.0.3 | Parse consumer-facing routing/rules config (`prevue.yml`) | Already a transitive dep of python-frontmatter; don't add a second YAML library. Confidence: HIGH |

**Skill bundle format:** follow the **Agent Skills open spec** (agentskills.io, originated by Anthropic, Apache-2.0). Each bundle = directory with `SKILL.md` (required frontmatter: `name` matching dir name, `description`; optional `metadata` map — put Prevue routing labels there, e.g. `metadata: {prevue-labels: [security]}`) plus optional `references/`. Adopting the open standard instead of inventing a format means consumer repos can reuse skills they already have and Prevue skills stay portable. Confidence: HIGH (spec verified at agentskills.io/specification).

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv 0.11.20 + `astral-sh/setup-uv@v8` | Dependency management + CI install | `uv sync --locked` gives fast, reproducible installs inside the reusable workflow — install speed is consumer-facing latency on every PR. Pin uv version in the workflow. |
| ruff 0.15.16 | Lint + format | Single tool replaces flake8/isort/black. |
| pytest 9.0.3 + pytest-cov 7.1.0 | Test runner | Standard. |
| responses 0.26.1 | Mock GitHub REST API in unit tests | PyGithub uses `requests` under the hood → `responses` intercepts cleanly. Record realistic payloads as JSON fixtures. (If you ever switch to githubkit/httpx, swap to respx 0.23.1.) |
| act v0.2.89 (nektos/act) | Local smoke-test of workflow YAML | **Limited usefulness here** — `workflow_call` support in act is buggy (inputs dropped, booleans stringified; maintainers mark it not-planned). Workaround: keep a `push`-triggered wrapper workflow in this repo that `uses: ./.github/workflows/review.yml` and run `act push`. Treat act as YAML smoke test only; real verification = unit tests + a live test PR in a sandbox repo. Confidence: MEDIUM |

## Architecture-Relevant Packaging Facts (verified, drives repo layout)

1. **A reusable workflow only ships its YAML.** When a consumer calls `your-org/prevue/.github/workflows/review.yml@v1`, GitHub fetches *only the workflow file* — not the Python code or skill bundles. The workflow's first step must therefore `actions/checkout` the prevue repo itself at the matching ref (`repository: your-org/prevue`, `ref: <same tag>`) into a subdirectory, then run the Python CLI from there. Pass the ref through carefully — version skew between workflow YAML and framework code is the classic bug here. Confidence: HIGH
2. **Permissions:** caller grants the job `permissions: { contents: read, pull-requests: write, checks: write }`. The default Actions `GITHUB_TOKEN` is a GitHub App installation token, so the Checks API (`create_check_run`) works with it — no app or PAT needed for output. Only `COPILOT_GITHUB_TOKEN` (a PAT of a Copilot-licensed user) must be passed as an explicit named secret (never `secrets: inherit`). Confidence: HIGH
3. **Trigger:** consumers call it from `on: pull_request`. Do **not** document/encourage `pull_request_target` — secrets + fork code is the top Actions security foot-gun. Fork PRs simply won't get AI review in v1 (no `COPILOT_GITHUB_TOKEN` available); that's the safe default. Confidence: HIGH
4. **Inline comments:** one `POST /repos/{o}/{r}/pulls/{n}/reviews` call with a `comments[]` array (`path`, `line`, `side: RIGHT`, `body`) batches the summary + all inline comments into a single review — one notification, atomic, and avoids secondary-rate-limit issues vs posting comments one-by-one. PyGithub: `pull.create_review(body=summary, event="COMMENT", comments=[...])`. Confidence: HIGH

## Installation

```bash
# Project init (managed by uv; commit uv.lock)
uv init --package prevue
uv add PyGithub==2.9.* pydantic==2.13.* unidiff==0.7.* pathspec==1.1.* python-frontmatter==1.3.* PyYAML==6.0.*

# Dev dependencies
uv add --dev pytest==9.* pytest-cov==7.* responses==0.26.* ruff==0.15.*
```

```yaml
# Inside the reusable workflow job (engine adapter prereq)
- run: npm install -g @github/copilot   # Copilot CLI 1.0.x; Node 22 preinstalled on ubuntu-latest
- uses: astral-sh/setup-uv@v8
  with: { enable-cache: true }
```

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| GitHub API | PyGithub 2.9.1 | githubkit 0.15.5 | If you need async or full Pydantic-typed responses. Rejected for v1: githubkit's own docs say it's "not stable" with breaking changes on minor versions (models regenerated from GitHub's OpenAPI schema) — bad fit for a framework other repos depend on. Revisit if review parallelism ever needs asyncio. |
| Diff parsing | unidiff | Raw `pull.get_files()` metadata only | If v1 inline comments only target whole files/first-line, the REST `files` endpoint (filename, status, additions, patch) may suffice and you can defer unidiff. You'll need unidiff as soon as findings map to specific changed lines. |
| Delivery | Reusable workflow | Composite action (`action.yml`) | If consumers demand embedding review as a *step* inside their existing job (shared runner/filesystem). Could be offered later as a thin wrapper; the workflow remains the primary interface because of its permissions/secrets boundary. |
| Glob matching | pathspec | `fnmatch`/`pathlib.match` (stdlib) | Never for this use case — stdlib doesn't implement `**` gitignore semantics correctly and edge cases will misclassify PRs silently. |
| LLM fallback classifier | Same engine adapter (Copilot CLI, cheap model via `--model`) | Direct API SDK (openai/anthropic) | Only if adapter latency/cost for the tiny classification call proves unacceptable. Starting point: route the fallback through the existing adapter interface — zero new dependencies, vendor-neutral by construction. |
| Workflow YAML testing | act (smoke) + unit tests | actionlint + zizmor (static checkers) | Use *in addition*: actionlint catches workflow syntax/typing errors, zizmor catches Actions security smells. Cheap to add to CI. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| ghapi (fastai) | Effectively unmaintained; auto-generated API lags GitHub's | PyGithub |
| github3.py | Maintenance-mode; smaller community than PyGithub | PyGithub |
| whatthepatch / patch-ng | patch-*application* focused or less adopted; weaker hunk/line iteration API for comment positioning | unidiff |
| LangChain / agent frameworks | Massive dependency surface for what is a subprocess call + prompt assembly; engine adapter is ~100 lines of Python | pydantic models + `subprocess` |
| `pull_request_target` trigger in docs/examples | Exposes secrets to fork code; the #1 Actions security foot-gun | `pull_request`; forks skip AI review in v1 |
| `secrets: inherit` in consumer examples | Defeats the security boundary that makes the framework trustworthy | Explicit named secret: `secrets: { copilot-token: ... }` |
| Posting inline comments individually (`create_review_comment` per finding) | N notifications, N API calls, secondary rate limits | Single `create_review` with `comments[]` array |
| Custom skill-file format | Agent Skills (SKILL.md) is now an open multi-vendor standard; inventing one loses portability | agentskills.io spec + python-frontmatter |
| act as the primary test strategy | `workflow_call` support is explicitly broken/not-planned in act | Unit tests w/ responses fixtures + sandbox-repo live PRs |

## Stack Patterns by Variant

**If a second engine adapter (e.g. Claude Code CLI, OpenAI) is added:**
- Keep the adapter contract as a pydantic model pair (`ReviewRequest` → `ReviewResult` with findings list); each adapter is a class implementing one `review()` method that shells out or calls an SDK.
- Because PyGithub is sync, adapters stay sync; don't introduce asyncio until two+ engines must run concurrently.

**If consumers need fork-PR review later:**
- That's the point to evaluate a GitHub App installation token flow instead of PAT — do not solve it in v1.

**If diff sizes blow context windows:**
- unidiff's `metadata_only=True` parse + per-file chunking is the escape hatch; the classifier already has per-file granularity.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PyGithub 2.9.x | Python >=3.9 | Uses `requests`; pairs with `responses` for tests |
| pathspec 1.1.x | Python >=3.9 | **1.x renamed pattern factory** ("gitwildmatch" → "gitignore"); don't copy 0.12-era snippets |
| python-frontmatter 1.3.x | Python >=3.10, PyYAML 6.x | PyYAML is its dependency — versions align |
| pydantic 2.13.x | Python >=3.9 | v2 API only; never mix v1-style validators |
| @github/copilot 1.0.x | Node >=22 | Preinstalled on `ubuntu-latest`; CLI auto-updates by default — pin version in workflow for reproducibility (`npm i -g @github/copilot@1.0.60`) |
| setup-uv v8 | uv 0.11.x | Pin both action SHA and uv version |

## Sources

- https://pypi.org/pypi/{PyGithub,pydantic,pytest,ruff,responses,unidiff,pathspec,python-frontmatter,PyYAML,pytest-cov}/json — versions fetched live 2026-06-12 (HIGH)
- https://docs.github.com/copilot (run-cli-programmatically, automate-with-actions, authenticate-copilot-cli) — Copilot CLI programmatic mode, `--no-ask-user`, `COPILOT_GITHUB_TOKEN` (HIGH, official)
- https://registry.npmjs.org/@github/copilot — v1.0.60, 2026-06-05; GA announcement github.blog 2026-02-25 (HIGH, official)
- https://docs.github.com/actions (reusing-workflow-configurations, reuse-workflows, authenticate-with-github_token) — reusable workflow vs composite action, GITHUB_TOKEN permission scopes incl. `checks: write` (HIGH, official)
- https://agentskills.io/specification — SKILL.md frontmatter schema (name/description required, optional metadata map) (HIGH, official spec)
- https://github.com/nektos/act — v0.2.89 (2026-06-01); issues #826, #2046, #2047, #2464 documenting `workflow_call` limitations (HIGH for limitations — maintainer statements)
- https://docs.astral.sh/uv/guides/integration/github/ — setup-uv@v8, uv 0.11.20 (HIGH, official)
- Opsio / Earthly / github.blog posts on reusable-workflow vs composite-action patterns — cross-checked against official docs (MEDIUM, community; consistent with HIGH sources)

---
*Stack research for: AI PR review framework as GitHub reusable workflow*
*Researched: 2026-06-12*
