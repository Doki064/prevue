<!-- generated-by: gsd-doc-writer -->

# Development

Guide for contributing to the Prevue framework — local setup, tooling, project layout, and how to extend engines, skills, and classification rules.

For prerequisites and first-run setup, see [GETTING-STARTED.md](./GETTING-STARTED.md). For consumer-facing configuration, see [configuration.md](./configuration.md).

## Local setup

1. **Clone and enter the repo**

   ```bash
   git clone https://github.com/Doki064/prevue.git
   cd prevue
   ```

2. **Install [uv](https://docs.astral.sh/uv/)** (0.11.x; CI pins `0.11.21`).

3. **Install dependencies** (runtime + dev group from `pyproject.toml`):

   ```bash
   uv sync --locked
   ```

   Use `--locked` so installs match `uv.lock`. CI and the local CI mirror both require it. Python 3.13 is the runtime (`.python-version`); the package floor is `>=3.12`.

4. **Verify the install**

   ```bash
   uv run pytest -q
   uv run prevue --help
   ```

No `.env` file is required for unit tests — GitHub API and engine boundaries are mocked via `responses`. Live engine runs need the appropriate API token and a PR event context (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, `GITHUB_TOKEN`).

## Build commands

Prevue is a Python package with a CLI entry point (`prevue = prevue.cli:main`). There is no separate build step for local development — `uv sync` installs the package in editable mode.

| Command | Description |
|---------|-------------|
| `uv sync --locked` | Install runtime + dev dependencies from `uv.lock` |
| `uv run prevue <subcommand>` | Run the CLI (`review`, `command`, `preflight`, `gate-revalidate`, `materialize-comment-event`) |
| `uv run pytest` | Run the full test suite (`testpaths = ["tests"]`) |
| `uv run pytest --cov=prevue -q` | Run tests with coverage (same as CI) |
| `uv run pytest tests/test_foo.py -q` | Run a single test file |
| `uv run ruff check .` | Lint (rules: E, F, I, UP; line length 100; target Python 3.12) |
| `uv run ruff format .` | Format Python sources |
| `uv run ruff format --check .` | Check formatting without writing (CI gate) |
| `./scripts/ci-local.sh` | Mirror the CI `test-and-lint` job locally (see below) |

Dev dependencies (from `[dependency-groups] dev` in `pyproject.toml`): `pytest`, `pytest-cov`, `responses`, `ruff`.

## Code style

**Ruff** handles linting and formatting. Configuration lives in `pyproject.toml`:

- `[tool.ruff]` — `line-length = 100`, `target-version = "py312"`
- `[tool.ruff.lint]` — `select = ["E", "F", "I", "UP"]`

Run before committing:

```bash
uv run ruff check .
uv run ruff format .
```

CI enforces both `ruff check` and `ruff format --check` on every push and pull request (`.github/workflows/ci.yml`). Keep imports at module top level; no inline imports unless a documented circular-dependency exception exists.

## CI local mirror

`scripts/ci-local.sh` runs the same checks as the CI `test-and-lint` job, in order:

1. `uv sync --locked`
2. `uv run pytest --cov=prevue -q`
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. **actionlint** on workflow files (installs via `go install` if missing; version `v1.7.12`)
6. **zizmor** security scan via `uvx zizmor==1.25.2 .github/workflows`

```bash
./scripts/ci-local.sh
```

**Prerequisites for the workflow linters:**

- **actionlint** — either on `PATH`, or **Go** installed so the script can `go install` actionlint
- **uv** — for `uvx` (zizmor)

Workflow files linted locally: `ci.yml`, `review.yml`, `prevue-review.yml`, `prevue-command.yml`. CI also lints `prevue-command-run.yml`.

Run this script before opening a PR to catch CI failures early.

## Running tests

Framework: **pytest** 9.x with **pytest-cov** 7.x and **responses** 0.26.x for mocking GitHub REST calls.

```bash
# Full suite
uv run pytest

# With coverage (CI)
uv run pytest --cov=prevue -q

# Single file or test
uv run pytest tests/test_skills_loader.py -q
uv run pytest tests/test_registry.py::test_unknown_engine_raises_with_valid_names -q
```

**Test layout:**

- `tests/` — unit and integration tests; naming `test_<area>.py`
- `tests/fixtures/` — JSON event payloads, GraphQL responses, sample skills
- `tests/conftest.py`, `tests/engine_helpers.py` — shared fixtures and fake engine helpers

Workflow YAML conventions are guarded by `tests/test_workflow_yaml.py` and `tests/test_reusable_workflow_yaml.py` — extend these when changing `.github/workflows/`.

**Coverage:** No minimum threshold is configured in `pyproject.toml`; CI runs `--cov=prevue` for reporting only.

## Project layout

```
prevue/
├── .github/
│   ├── workflows/              # CI, dogfood review, reusable workflow_call, /prevue commands
│   │   ├── ci.yml              # Test + lint on push/PR
│   │   ├── review.yml          # Dogfood: wait for CI then call reusable workflow
│   │   ├── prevue-review.yml   # Reusable workflow_call — consumer entry point
│   │   ├── prevue-command.yml  # /prevue comment dispatcher
│   │   └── prevue-command-run.yml  # Command execution job
│   └── scripts/
│       └── install-engine-cli.sh   # Engine CLI install (npm/curl) — pinned versions
├── docs/                       # Project documentation
├── scripts/
│   └── ci-local.sh             # Local CI mirror
├── src/prevue/
│   ├── cli.py                  # CLI entry: review, command, preflight, gate-revalidate
│   ├── review.py               # End-to-end review orchestration
│   ├── config.py               # Consumer prevue.yml loader (PrevueConfig, SkillsConfig, …)
│   ├── models.py               # ReviewRequest, ReviewResult, Finding, DiffBundle
│   ├── gate.py                 # Severity thresholds, inline placement, check conclusion
│   ├── pack.py                 # Token-budget file packing (skill/risk-weighted)
│   ├── multicall.py            # Multi-call split, execute, and merge (ENGN-05/06/07)
│   ├── importscan.py           # Parse-only import extraction for file co-location
│   ├── fingerprint.py          # Stable finding fingerprints (path + title hash)
│   ├── skip.py                 # Skip policy (bot/label/title) before engine spend
│   ├── dismiss.py              # /prevue dismiss inline suppression
│   ├── preflight.py            # Same-SHA noop detection
│   ├── classify/
│   │   ├── classifier.py       # Deterministic multi-label classify via pathspec globs
│   │   ├── filter.py           # Ignore-glob filtering (diff noise removal)
│   │   ├── llm_fallback.py     # LLM fallback for unmatched paths + skill selection
│   │   ├── models.py           # RuleSet, ClassificationResult, CANONICAL_LABEL_ORDER
│   │   ├── router.py           # Label → bundle routing
│   │   ├── rules.py            # Built-in rule loader + consumer merge
│   │   └── default_rules.yml   # Bundled classification rules (ignore / labels / routing)
│   ├── skills/
│   │   ├── loader.py           # load_skills(), select_skills(), assemble_instructions()
│   │   ├── selection.py        # Hybrid keyword-floor + LLM-escalation skill selection
│   │   ├── models.py           # Skill pydantic model (name, description, applies-to)
│   │   ├── security/           # Built-in security skill bundle
│   │   ├── frontend/           # Built-in frontend skill bundle
│   │   ├── backend/            # Built-in backend skill bundle
│   │   ├── data/               # Built-in data skill bundle
│   │   └── infra/              # Built-in infra skill bundle
│   ├── engines/
│   │   ├── base.py             # EngineAdapter ABC (review, classify, classify_skills)
│   │   ├── registry.py         # Engine name → adapter registry
│   │   ├── flow.py             # Shared retry-then-degrade review loop
│   │   ├── prompt.py           # Prompt assembly, output contract, classify prompts
│   │   ├── parsing.py          # JSON fence extraction and findings validation
│   │   ├── subprocess_invoke.py # Shared headless subprocess helper
│   │   ├── tokens.py           # Token estimation (bytes / 4)
│   │   ├── errors.py           # EngineFailure, AuthError, stderr sanitisation
│   │   ├── copilot_cli.py      # Copilot CLI adapter (default)
│   │   ├── claude_code_cli.py  # Claude Code CLI adapter
│   │   ├── cursor_cli.py       # Cursor CLI adapter
│   │   └── gemini_cli.py       # Gemini skeleton (not yet functional)
│   └── github/
│       ├── client.py           # PrContext, PR + repo auth helpers
│       ├── diff.py             # Diff fetch, scope decision (full/incremental/noop)
│       ├── comments.py         # Sticky comment upsert, inline review posting
│       ├── checks.py           # Check run creation and conclusion
│       ├── positions.py        # Diff annotation, valid-line mapping, finding reconciliation
│       └── graphql.py          # GraphQL: review thread resolve (LIFE-04)
├── tests/                      # pytest suite + fixtures
├── pyproject.toml              # Package metadata, ruff, pytest config, dev deps
└── uv.lock                     # Locked dependency graph (commit with dep changes)
```

**Runtime requirements:** Python `>=3.12` (`requires-python` in `pyproject.toml`); Python 3.13 is the pinned runtime (`.python-version`).

## Key source modules

### `review.py` — orchestration entry point

`run_review()` drives the full pipeline: load config → fetch diff → filter ignored paths → classify → LLM fallback classify → pack files (token-budget) → load skills → hybrid skill selection → assemble prompt → split into call groups → execute → merge findings → apply gate → post inline review → upsert sticky comment → conclude check run.

### `classify/classifier.py` — deterministic classification

`classify(files, label_rules)` runs each changed file against pathspec globs for all label rules (gitignore semantics). Returns `ClassificationResult` with `labels` (label → matched glob), `unmatched` paths (no rule matched), and `bundles` (after routing). The canonical label priority order is `security → frontend → backend → data → infra → general`.

### `classify/llm_fallback.py` — hybrid classification and skill selection

Two public functions:

- `llm_classify(unmatched_paths, adapter, ...)` — sends paths not matched by deterministic rules to the engine adapter's `classify()` method for label assignment. Degrades gracefully (partial or full failure returns a `general` label with a disclosure note).
- `llm_select_skills(candidate_skills, adapter, ...)` — sends routed-but-below-threshold skills to `adapter.classify_skills()` for relevance arbitration (`relevant`/`irrelevant`). Returns a set of skill names to include.

Both are called from `review.py` when `classification.fallback.enabled = true` (default). An adapter that does not override `classify()` / `classify_skills()` raises `NotImplementedError` which both functions catch and degrade silently.

### `skills/selection.py` — hybrid skill selection

`select_skills_hybrid(skills, paths, diff_text, bundles, ...)` is the main selection entry point. It applies a keyword-score floor (`KEYWORD_THRESHOLD = 0.15`): skills scoring above the threshold are included immediately; below-threshold skills in routed bundles are escalated to `llm_select_skills`. When the adapter lacks `classify_skills()`, below-threshold routed skills are all included as a conservative fallback.

`keyword_score(skill, paths, diff_text)` is a deterministic Jaccard-like score: 70% from token overlap between (name + description) and diff content, 30% from path glob matching against `applies-to`.

### `engines/base.py` — adapter contract

```python
class EngineAdapter(ABC):
    name: str

    @abstractmethod
    def review(self, req: ReviewRequest) -> ReviewResult: ...

    def classify(self, paths, allowed_labels, *, model=None) -> dict[str, str]:
        """Optional: LLM fallback classify — {path: label}."""
        raise NotImplementedError(...)

    def classify_skills(self, skills, allowed_labels, *, model=None) -> dict[str, str]:
        """Optional: skill relevance arbitration — {skill_name: 'relevant'|'irrelevant'}."""
        raise NotImplementedError(...)
```

`review()` is required. `classify()` and `classify_skills()` are optional — adapters that implement them enable the hybrid classification and skill-selection fallbacks.

### `multicall.py` — multi-call split and merge

When `review.max_review_calls > 1`, `split_into_calls()` partitions packed files into `CallGroup` objects by bundle label, with import-graph co-location via `importscan.py`. `execute_calls()` runs groups sequentially or in parallel (bounded by `review_concurrency`). `merge_findings()` deduplicates findings across calls by `fingerprint(path, title)`, keeping higher-severity on ties.

### `pack.py` — token-budget file packing

`pack_files(files, weight=..., budget_tokens=...)` sorts files by skill-match priority, then classification label priority (`security` first), then churn (additions + deletions descending), then fills until the token budget is exhausted. `readmit_files()` recovers budget freed when actual matched-skill overhead is smaller than the conservative first-pass estimate.

### `gate.py` — conclusion and placement

`ReviewConfig` holds consumer thresholds (`min_severity_to_comment`, `min_severity_to_fail`, `max_inline_comments`, `guardrail_skills`, multi-call caps, etc.). `apply_gate()` computes the check conclusion (`success`/`failure`/`neutral`) and classifies each finding as `inline` or `summary-only`.

## Adding an engine adapter

Engines implement the `EngineAdapter` port in `src/prevue/engines/base.py`. The three functional adapters — `CopilotCliAdapter`, `ClaudeCodeAdapter`, `CursorAdapter` — are the reference implementations.

### Steps

1. **Create the adapter** — e.g. `src/prevue/engines/my_engine_cli.py`. Subclass `EngineAdapter`, set a unique `name`, implement `review()`. Reuse `engines/flow.py` (`review_with_retry`), `engines/prompt.py` (`build_prompt`), and `engines/subprocess_invoke.py` (`invoke_subprocess_text`).

   ```python
   class MyEngineAdapter(EngineAdapter):
       name = "my-engine"

       def review(self, req: ReviewRequest) -> ReviewResult:
           key = os.environ.get("MY_ENGINE_API_KEY", "")
           if not key:
               raise AuthError("MY_ENGINE_API_KEY is not set.")
           env = {**os.environ, "MY_ENGINE_API_KEY": key}
           return flow.review_with_retry(
               req,
               invoke=lambda p: invoke_subprocess_text(
                   ["my-engine-cli", "--prompt-stdin"],
                   env=env, secret=key,
                   budget_seconds=req.budget_seconds,
                   cli_label="My Engine",
                   input_text=p,
               ),
               secret=key,
               build_prompt=build_prompt,
               max_prompt_bytes=MAX_PROMPT_BYTES,
               model_label=req.model or "default",
           )

       def classify(self, paths, allowed_labels, *, model=None) -> dict[str, str]:
           """Implement for hybrid classification fallback support."""
           ...

       def classify_skills(self, skills, allowed_labels, *, model=None) -> dict[str, str]:
           """Implement for hybrid skill-selection support."""
           ...
   ```

2. **Register in `registry.py`** — add the class to `ENGINES`:

   ```python
   from prevue.engines.my_engine_cli import MyEngineAdapter

   ENGINES: dict[str, type[EngineAdapter]] = {
       ...
       MyEngineAdapter.name: MyEngineAdapter,
   }
   ```

   If the adapter is not yet functional, set `functional=False` on its `CliEngineSpec` (same as `antigravity-cli`) so `require_functional_adapter()` rejects it at review time with a clear error.

3. **Wire CLI install** — add a `case` branch in `.github/scripts/install-engine-cli.sh` with a **pinned** package version:

   ```bash
   my-engine)
     npm install -g @my-org/engine-cli@x.y.z
     command -v my-engine-cli
     ;;
   ```

4. **Expose workflow secrets** — in `.github/workflows/prevue-review.yml`:
   - Add the secret under `on.workflow_call.secrets`
   - Map it in the review step `env` block (engine-conditional expression, same pattern as `COPILOT_GITHUB_TOKEN`):
     ```yaml
     MY_ENGINE_API_KEY: ${{ inputs.engine == 'my-engine' && secrets.my-engine-api-key || '' }}
     ```
   - Pass it from caller workflows (`review.yml`, consumer examples) — never `secrets: inherit`.

5. **Add tests** — adapter contract (`tests/test_engine_contract.py`), registry (`tests/test_registry.py`), workflow YAML guards if env/secrets change (`tests/test_workflow_yaml.py`).

`DEFAULT_ENGINE` in `registry.py` is `copilot-cli`.

## Adding or modifying classification rules

Classification rules live in `src/prevue/classify/default_rules.yml`. They are loaded via `importlib.resources` (never `__file__`).

### Rule file structure

```yaml
ignore:
  - "**/*.lock"          # Paths matched here are dropped before classification
  - "**/dist/**"

labels:
  security:              # Label name
    - "**/auth/**"       # pathspec gitignore-style globs (** semantics)
    - "**/.env*"
  frontend:
    - "**/*.tsx"
    - "**/*.jsx"
  backend:
    - "**/*.py"
    - "**/*.go"
  # ... infra, data

routing: {}              # label → bundle override (default: label == bundle)
```

### How rules are applied

1. `filter_diff()` in `classify/filter.py` drops files matching any `ignore` glob.
2. `classify()` in `classify/classifier.py` runs each remaining file against every label's glob list; a file can match multiple labels (union).
3. Files matching no label end up in `result.unmatched`; when `classification.fallback.enabled = true`, `llm_classify()` in `classify/llm_fallback.py` classifies those via the engine adapter.
4. `route()` in `classify/router.py` maps label names to skill bundle ids using the `routing` map; unrouted labels map to themselves.

### Consumer overrides

Consumers extend rules in `.github/prevue.yml`:

- `ignore:` — appended to built-in noise filters.
- `labels:` — override-by-label: a consumer `frontend:` list **replaces** the built-in `frontend:` globs.
- `routing:` — consumer entries override 1:1.

Consumer config is loaded from the **base ref** checkout (not PR head) via `PREVUE_CONSUMER_ROOT`. See [configuration.md](./configuration.md) for the full schema.

## Writing a skill file

Built-in skills live under `src/prevue/skills/<bundle>/`. Each is a `.md` file with YAML frontmatter (Agent Skills format, validated by `Skill` in `src/prevue/skills/models.py`).

### Frontmatter (all fields required)

```yaml
---
name: Authentication & Authorization
description: Review changes to auth flows, session handling, and access control for privilege and bypass risks.
applies-to:
  - "**/auth/**"
  - "**/*auth*"
  - "**/middleware/**"
---
```

- `name` — human-readable; used for routing disclosure and keyword scoring.
- `description` — one-line purpose; also used in keyword scoring against the diff.
- `applies-to` — list of pathspec gitignore globs; the skill loads when any packed file's path matches.

### Body (markdown, after the frontmatter `---`)

Review checklist items. `assemble_instructions()` in `skills/loader.py` appends the body verbatim under a `## Skill: {name}` heading. Keep it focused: each bullet should be a clear, actionable check. Skill bodies count against the token budget.

### Bundle directory = skill bundle id

The directory name (`security`, `frontend`, `backend`, `data`, `infra`) is the bundle id. `select_skills_hybrid()` includes a skill when either:

1. Its keyword score against the diff and changed paths is `>= 0.15` (`KEYWORD_THRESHOLD`), **or**
2. Its bundle is routed for this PR and the engine's `classify_skills()` rates it `relevant`.

### Guardrail skills

To force a skill to load on every call regardless of routing or scoring, add its key (`bundle/filename`) to `review.guardrail_skills` in `prevue.yml`:

```yaml
review:
  guardrail_skills:
    - "security/committed-secrets.md"
```

### Consumer skills

Consumers place skills in `.github/prevue/skills/<bundle>/` on their repo. Consumer skills are merged over built-ins by key (`bundle/filename`); a same-key consumer file replaces the built-in. See [skills.md](./skills.md).

### Tests

Add or extend tests in `tests/test_skills_*.py`. Use fixtures under `tests/fixtures/skills/` for loader edge cases. The `tests/test_skills_builtin.py` suite validates all built-in frontmatter against the `Skill` schema.

## Running the framework locally against a real PR

There is no local CLI shortcut that replaces the full Actions environment. To run `prevue review` locally against an actual PR:

1. Set the required environment variables:

   ```bash
   export GITHUB_TOKEN="github_pat_..."     # read PR data + post comments
   export COPILOT_GITHUB_TOKEN="github_pat_..."  # or CLAUDE_CODE_OAUTH_TOKEN / CURSOR_API_KEY
   export PREVUE_ENGINE="copilot-cli"        # or claude-code-cli, cursor-cli
   export GITHUB_REPOSITORY="owner/repo"
   export GITHUB_EVENT_PATH="/path/to/event.json"   # pull_request event payload
   ```

2. Provide a `pull_request` event JSON at `GITHUB_EVENT_PATH`. The fixture at `tests/fixtures/event_pull_request.json` shows the required shape (`pull_request.number`, `pull_request.head.sha`, etc.).

3. Run from the repo root:

   ```bash
   uv run prevue review
   ```

The sandbox repo at `.demo-sandbox/` is a dogfood consumer repo used for live integration testing.

## Workflow YAML conventions

Prevue workflows are security-sensitive. CI enforces static checks; `tests/test_workflow_yaml.py` encodes many invariants.

### Files

| Workflow | Role |
|----------|------|
| `ci.yml` | Test, ruff, actionlint, zizmor on push/PR |
| `review.yml` | Dogfood: wait for CI, call reusable workflow on same-repo PRs |
| `prevue-review.yml` | **Reusable** `workflow_call` — consumer entry point |
| `prevue-command.yml` | `/prevue` issue-comment dispatcher |
| `prevue-command-run.yml` | Command execution job (called by dispatcher) |

### Required patterns

- **SHA-pin third-party actions** — e.g. `actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10`, `astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39` (uv `0.11.21`). Tests assert these SHAs.
- **`persist-credentials: false`** on every `actions/checkout` step.
- **No `pull_request_target`** — use `pull_request` only.
- **No `secrets: inherit`** — pass named secrets explicitly through `workflow_call`.
- **Least-privilege `permissions`** — caller jobs declare only what they need; the reusable workflow needs `contents: write`, `pull-requests: write`, `checks: write` for lifecycle GraphQL.
- **Trusted checkout only** — consumer repo checked out at **base ref**, never PR head, for config/skills (`path: consumer`).
- **Engine secrets** — map workflow secrets to env vars with an engine-conditional expression; keep `GITHUB_TOKEN` separate from engine tokens.
- **Pin engine CLIs** — versions in `.github/scripts/install-engine-cli.sh` (e.g. `@github/copilot@1.0.61`, `@anthropic-ai/claude-code@2.1.177`).
- **Fork/draft guards** — job `if:` blocks skip fork PRs and drafts before spending runner time.

### Linting workflows

```bash
# After installing actionlint (or via ci-local.sh)
actionlint -color -shellcheck= -pyflakes= \
  .github/workflows/ci.yml \
  .github/workflows/review.yml \
  .github/workflows/prevue-review.yml \
  .github/workflows/prevue-command.yml

uvx zizmor==1.25.2 .github/workflows
```

When adding or editing workflows, update `scripts/ci-local.sh` `WORKFLOW_FILES` if the new file should be linted locally, and extend the actionlint list in `ci.yml` to match.

### Static tests

Run workflow guards after YAML changes:

```bash
uv run pytest tests/test_workflow_yaml.py tests/test_reusable_workflow_yaml.py -q
```

## Branch conventions

No branch naming convention is documented in this repository.

Default branch: `main` (used by dogfood `review.yml`).

## PR process

Before opening a pull request:

1. Run `./scripts/ci-local.sh` (or at minimum `uv sync --locked`, `uv run pytest --cov=prevue -q`, and both ruff commands).
2. If you changed `.github/workflows/`, ensure actionlint and zizmor pass and workflow YAML tests are green.
3. If you changed dependencies, commit updated `uv.lock`.

CI (`.github/workflows/ci.yml`) runs on all branches for `push` and `pull_request` with `permissions: contents: read` only.

Reviewers expect:

- Focused diffs aligned with Prevue's trust model (no PR-head checkout for config, no broad token scopes).
- Pinned versions for actions, uv, and engine CLIs when touching workflows or install scripts.
- Tests for new behavior — especially engine adapters, skill loading, classification rules, and workflow invariants.

## Next steps

| Doc | Purpose |
|-----|---------|
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Prerequisites, install, first run |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Pipeline, components, data flow |
| [configuration.md](./configuration.md) | `prevue.yml` reference |
| [skills.md](./skills.md) | Consumer skill overrides |
| [security.md](./security.md) | Threat model and trust boundaries |
