<!-- generated-by: gsd-doc-writer -->

# Testing

## Test framework and setup

Prevue uses **pytest** (9.x) as the test runner, **pytest-cov** (7.x) for coverage reporting, and **responses** (0.26.x) to mock GitHub REST API calls made by PyGithub.

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | 9.* | Test discovery and execution |
| pytest-cov | 7.* | Coverage over `src/prevue/` |
| responses | 0.26.* | HTTP mocking for GitHub API tests |

**Prerequisites:** Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/) for dependency management.

Install dev dependencies (including test tools):

```bash
uv sync --locked
```

Pytest is configured in `pyproject.toml` with `testpaths = ["tests"]`. All tests live under `tests/`; no extra setup files or plugins are required beyond `uv sync`.

## Running tests

### Full suite (matches CI)

```bash
uv run pytest --cov=prevue -q
```

### Without coverage (faster local iteration)

```bash
uv run pytest -q
```

### Single file

```bash
uv run pytest tests/test_client.py -q
```

### Single test by name

```bash
uv run pytest tests/test_client.py::test_load_pr_context -q
```

### Subset by keyword

```bash
uv run pytest -k "workflow" -q          # workflow YAML guards
uv run pytest -k "classify" -q          # classifier and routing
uv run pytest -k "responses" -q         # tests whose names mention responses
```

### Verbose output

```bash
uv run pytest -v
```

### Local CI mirror

`scripts/ci-local.sh` runs the same checks as `.github/workflows/ci.yml`: locked install, pytest with coverage, Ruff lint/format, actionlint on workflow YAML, and zizmor security scan.

```bash
./scripts/ci-local.sh
```

## Test layout

```
tests/
├── conftest.py              # Shared pytest fixtures
├── engine_helpers.py        # Engine adapter test builders
├── test_*.py                  # One module per source area (41 files)
└── fixtures/
    ├── *.json                 # GitHub API / event payloads
    └── skills/                # Skill trees for loader tests
```

### Module tests (`test_*.py`)

Each `test_<area>.py` file targets a corresponding package under `src/prevue/`:

| Area | Test files | What they cover |
|------|------------|-----------------|
| CLI & orchestration | `test_cli.py`, `test_review_flow.py`, `test_preflight.py`, `test_commands.py` | Entry points, review pipeline, preflight noop, `/prevue` commands |
| GitHub integration | `test_client.py`, `test_diff.py`, `test_comments.py`, `test_checks.py`, `test_graphql.py`, `test_fork_guard.py`, `test_dismiss.py` | REST/GraphQL clients, diff fetch, comment posting, check runs |
| Classification | `test_classify_*.py`, `test_llm_fallback.py` | Deterministic rules, router, LLM fallback |
| Skills & packing | `test_skills_*.py`, `test_pack.py`, `test_tokens.py` | Skill loader, merge, token budget |
| Engines | `test_engine_*.py`, `test_copilot_adapter.py`, `test_findings_parsing.py`, `test_prompt.py` | Adapter contract, Copilot CLI, finding parse |
| Config & models | `test_config.py`, `test_models.py`, `test_registry.py` | `prevue.yml` parsing, Pydantic models |
| Gate & security | `test_gate.py`, `test_gate_validate.py`, `test_injection_adversarial.py` | Pass/fail gate, prompt injection guards |
| Workflow YAML | `test_workflow_yaml.py`, `test_reusable_workflow_yaml.py` | Static guards on `.github/workflows/*.yml` |
| Smoke | `test_smoke.py` | Package imports and version |

### Shared fixtures (`conftest.py`)

| Fixture | Purpose |
|---------|---------|
| `sample_request` | `ReviewRequest` with a two-file diff via `make_sample_request()` |
| `set_all_engine_keys` | Sets `COPILOT_GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `CURSOR_API_KEY` env vars |
| `responses_activated` | Yields a `responses.RequestsMock` context for GitHub REST mocking |
| `fake_engine` | `FakeEngine` adapter returning a canned `ReviewResult` |
| `skills_fixture_root` | Path to `tests/fixtures/skills/` |
| `event_json` | Parsed `event_pull_request.json` payload |

### Engine helpers (`engine_helpers.py`)

Reusable builders for engine adapter tests:

- `make_sample_request()` — constructs a `ReviewRequest` with sample diff files
- `stdout_with_fence()` — simulates engine stdout with a JSON findings fence
- `VALID_TOKEN`, `VALID_FINDING` — constants for token validation and finding shape tests

### JSON fixtures (`tests/fixtures/`)

Static payloads loaded by tests — not discovered by pytest:

| Fixture | Used for |
|---------|----------|
| `event_pull_request.json`, `event_pull_request_fork.json` | `GITHUB_EVENT_PATH` simulation |
| `issue_comment_event.json` | Issue-comment command context |
| `pulls_files.json` | Changed-files API response |
| `compare_*.json` | Compare API (ahead, diverged, identical) |
| `graphql_*.json` | GraphQL review-thread responses |
| `fixtures/skills/` | Built-in and consumer skill trees for loader unit tests |

## Mocking GitHub API with responses

PyGithub uses `requests` under the hood. Tests intercept outbound HTTP with the **responses** library.

**Decorator pattern** (most common):

```python
import responses

@responses.activate
def test_load_pr_context(comment_github_env: None) -> None:
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/prevue/pulls/42",
        json={...},
        status=200,
    )
    # call code under test
```

**Fixture pattern** (when you need the mock object):

```python
def test_something(responses_activated: responses.RequestsMock) -> None:
    responses_activated.add(responses.GET, url, json=payload)
```

Tests that need env vars (e.g. `GITHUB_TOKEN`, `GITHUB_EVENT_PATH`) typically define local `@pytest.fixture` helpers or use `monkeypatch` — see `test_client.py` for the `comment_github_env` pattern.

Regex URL matching is used where PyGithub may append `:443` to hostnames:

```python
responses.add(
    responses.GET,
    re.compile(r"https://api\.github\.com(?::443)?/repos/owner/prevue/?$"),
    json=repo_payload,
)
```

## Workflow YAML tests

Two test modules enforce security and structural invariants on GitHub Actions workflows by loading YAML with PyYAML and asserting on keys, permissions, secret pass-through, and shell snippets.

| File | Workflows under test |
|------|---------------------|
| `test_workflow_yaml.py` | `review.yml`, `prevue-review.yml`, `prevue-command.yml`, `prevue-command-run.yml`, `install-engine-cli.sh` |
| `test_reusable_workflow_yaml.py` | `prevue-review.yml` (WKFL-01/02/04 reusable-workflow contract) |

These tests guard requirements such as:

- No `pull_request_target` or `secrets: inherit`
- SHA-pinned `actions/checkout` and `astral-sh/setup-uv`
- Minimal job permissions (`contents: write`, `pull-requests: write`, `checks: write`)
- Named secret pass-through from caller to reusable workflow
- Fork PR guards, draft guards, CI-wait polling behavior
- Engine CLI install ordering and version pins
- Command workflow write-access check before privileged dispatch

Run only workflow guards:

```bash
uv run pytest tests/test_workflow_yaml.py tests/test_reusable_workflow_yaml.py -q
```

CI also runs **actionlint** and **zizmor** on workflow files outside pytest — see [CI integration](#ci-integration).

## Writing new tests

### File naming

Place new tests in `tests/test_<module>.py`. Pytest discovers functions named `test_*` and methods on classes named `Test*`.

### Patterns to follow

1. **Import from `prevue.*`** — test the public package API, not private internals unless testing a specific edge case.
2. **Use `conftest.py` fixtures** — prefer `sample_request`, `fake_engine`, and `responses_activated` over duplicating setup.
3. **Add JSON fixtures** — put reusable API payloads in `tests/fixtures/`; load with `Path(__file__).parent / "fixtures" / "..."`.
4. **Parametrize table-driven cases** — use `@pytest.mark.parametrize` for severity enums, label rules, and conclusion mappings (see `test_classify_rules.py`, `test_models.py`).
5. **Workflow changes** — add or extend assertions in `test_workflow_yaml.py` / `test_reusable_workflow_yaml.py` when modifying `.github/workflows/`.

### Example: new unit test with responses

```python
import responses
from prevue.github.client import load_pr_context

@responses.activate
def test_my_new_client_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/prevue")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/prevue/pulls/1",
        json={"number": 1, "base": {"sha": "abc"}, "head": {"sha": "def"}},
    )
    ctx = load_pr_context(pr_number=1)
    assert ctx.head_sha == "def"
```

## Coverage requirements

Coverage is collected in CI with `--cov=prevue` but **no minimum threshold is configured** — there is no `fail_under` in `pyproject.toml` or a separate coverage config file.

Coverage data is written to `.coverage` (gitignored). To view a report locally:

```bash
uv run pytest --cov=prevue --cov-report=term-missing -q
```

## CI integration

The **CI** workflow (`.github/workflows/ci.yml`) runs on every push and pull request.

| Step | Command | Purpose |
|------|---------|---------|
| Install | `uv sync --locked` | Reproducible dev + test deps |
| Tests | `uv run pytest --cov=prevue -q` | Full pytest suite with coverage |
| Lint | `uv run ruff check .` | Python style and import order |
| Format | `uv run ruff format --check .` | Formatting enforcement |
| actionlint | `actionlint` on 5 workflow YAML files | Workflow syntax and expression checks |
| zizmor | `zizmorcore/zizmor-action` on `.github/workflows` | Actions security smells |

The dogfood `review.yml` workflow waits for this CI job to pass on the PR head SHA before invoking Prevue review — workflow YAML tests and CI together protect the trust boundary consumers rely on.

**PR expectation:** All CI steps must pass before merge. Run `./scripts/ci-local.sh` before pushing to catch failures early.

## Next steps

- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline components exercised by tests
- [configuration.md](configuration.md) — `prevue.yml` options validated in `test_config.py`
