<!-- generated-by: gsd-doc-writer -->

# Development

Guide for contributing to the Prevue framework — local setup, tooling, project layout, and how to extend engines, skills, and workflows.

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

   Use `--locked` so installs match `uv.lock`. CI and the local CI mirror both require it.

4. **Verify the install**

   ```bash
   uv run pytest -q
   uv run prevue review --help
   ```

No `.env` file is required for unit tests — GitHub API and engine boundaries are mocked. Live engine runs need the appropriate API token and a PR event context (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`).

## Build commands

Prevue is a Python package with a CLI entry point (`prevue = prevue.cli:main`). There is no separate build step for local development — `uv sync` installs the package in editable mode.

| Command | Description |
|---------|-------------|
| `uv sync --locked` | Install runtime + dev dependencies from `uv.lock` |
| `uv run prevue <subcommand>` | Run the CLI (`review`, `command`, `preflight`, `gate-revalidate`, …) |
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

CI enforces both `ruff check` and `ruff format --check` on every push and pull request (`.github/workflows/ci.yml`).

Keep imports at module top level (no inline imports unless a documented circular-dependency exception exists).

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
│   └── scripts/
│       └── install-engine-cli.sh   # Engine CLI install (npm/curl) — pinned versions
├── docs/                       # Project documentation
├── scripts/
│   └── ci-local.sh             # Local CI mirror
├── src/prevue/
│   ├── cli.py                  # CLI entry: review, command, preflight, gate-revalidate
│   ├── review.py               # End-to-end review orchestration
│   ├── config.py               # Consumer prevue.yml loader
│   ├── models.py               # ReviewRequest, ReviewResult, Finding, DiffBundle
│   ├── classify/               # Deterministic classifier, router, LLM fallback, default_rules.yml
│   ├── skills/                 # Built-in SKILL.md bundles + loader
│   ├── engines/                # Pluggable engine adapters + registry
│   ├── github/                 # REST/GraphQL client, diff fetch, comments, checks
│   ├── gate.py                 # Severity thresholds, inline placement, check conclusion
│   └── pack.py                 # Token-budget file packing
├── tests/                      # pytest suite + fixtures
├── pyproject.toml              # Package metadata, ruff, pytest config, dev deps
└── uv.lock                     # Locked dependency graph (commit with dep changes)
```

**Runtime requirements:** Python `>=3.12` (`requires-python` in `pyproject.toml`).

## Adding an engine adapter

Engines implement the `EngineAdapter` port in `src/prevue/engines/base.py`:

```python
class EngineAdapter(ABC):
  name: str

  @abstractmethod
  def review(self, req: ReviewRequest) -> ReviewResult: ...

  def classify(self, paths, allowed_labels, *, model=None) -> dict[str, str]:
      ...
```

### Steps

1. **Create the adapter** — e.g. `src/prevue/engines/my_engine_cli.py`. Subclass `EngineAdapter`, set `name`, implement `review()`. Reuse `engines/flow.py`, `engines/prompt.py`, and `engines/subprocess_invoke.py` where appropriate (see `copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`).

2. **Register in `registry.py`** — add the class to `ENGINES`:

   ```python
   ENGINES: dict[str, type[EngineAdapter]] = {
       ...
       MyEngineAdapter.name: MyEngineAdapter,
   }
   ```

   If the adapter is not yet functional, add its name to `SKELETON_ENGINES` (like `gemini-cli`) so `require_functional_adapter()` rejects it at review time.

3. **Wire CLI install** — add a `case` branch in `.github/scripts/install-engine-cli.sh` with a **pinned** package version.

4. **Expose workflow secrets** — in `.github/workflows/prevue-review.yml`:
   - Add the secret under `on.workflow_call.secrets`
   - Map it in the review step `env` block (engine-conditional expression, same pattern as `COPILOT_GITHUB_TOKEN`)
   - Pass it from caller workflows (`review.yml`, consumer examples) — never `secrets: inherit`

5. **Add tests** — adapter contract (`tests/test_engine_contract.py`), registry (`tests/test_registry.py`), workflow YAML guards if env/secrets change (`tests/test_workflow_yaml.py`).

`DEFAULT_ENGINE` in `registry.py` is `copilot-cli`.

## Adding built-in skills

Built-in review skills live under `src/prevue/skills/<bundle>/`. Each skill is a markdown file with YAML frontmatter (Agent Skills format).

### File structure

```
src/prevue/skills/
├── security/
│   ├── committed-secrets.md
│   └── authn-authz.md
├── frontend/
│   └── accessibility.md
└── ...
```

### Frontmatter (required)

```yaml
---
name: Human-readable skill name
description: One-line purpose for routing/debug
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
---
```

Validated by `Skill` in `src/prevue/skills/models.py` — `name`, `description`, and `applies-to` (glob list) are required.

### Bundle ↔ classification routing

- Bundle directory name (e.g. `security`) is the skill bundle id.
- `select_skills()` matches each skill's `applies-to` path globs against packed file paths — this gates which skill bodies reach the prompt.
- `classify/router.py` maps classification **labels** to bundle ids via `routing` in `prevue.yml` for sticky metadata only (`route()` does not load skills).

### Tests

Add or extend tests in `tests/test_skills_*.py`. Use fixtures under `tests/fixtures/skills/` for loader edge cases.

Consumer overrides (not built-ins) belong in `.github/prevue/skills/` on the consumer repo — see [skills.md](./skills.md).

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
- **Least-privilege `permissions`** — caller jobs declare only what they need; reusable workflow needs `contents: write`, `pull-requests: write`, `checks: write` for lifecycle GraphQL.
- **Trusted checkout only** — consumer repo checked out at **base ref**, never PR head, for config/skills (`path: consumer`).
- **Engine secrets** — map workflow secrets to env vars in the review step; keep `GITHUB_TOKEN` (`github.token`) separate from engine tokens.
- **Pin engine CLIs** — versions in `.github/scripts/install-engine-cli.sh` (e.g. `@github/copilot@1.0.61`, `@anthropic-ai/claude-code@2.1.177`).
- **Single review invocation** — one `uv run prevue review` in the reusable workflow.
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

When adding or editing workflows, update `scripts/ci-local.sh` `WORKFLOW_FILES` if the new file should be linted locally, and extend `ci.yml` actionlint list to match.

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
- Tests for new behavior — especially engine adapters, skills loader, and workflow invariants.

## Next steps

| Doc | Purpose |
|-----|---------|
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Prerequisites, install, first run |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Pipeline, components, data flow |
| [configuration.md](./configuration.md) | `prevue.yml` reference |
| [skills.md](./skills.md) | Consumer skill overrides |
| [security.md](./security.md) | Threat model and trust boundaries |
