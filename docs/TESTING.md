<!-- generated-by: gsd-doc-writer -->

# Testing

## Test framework and setup

Prevue uses **pytest 9.x** as the test runner, **pytest-cov 7.x** for coverage reporting, and **responses 0.26.x** to mock GitHub REST API calls made by PyGithub.

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | 9.* | Test discovery and execution |
| pytest-cov | 7.* | Coverage over `src/prevue/` |
| responses | 0.26.* | HTTP mocking (PyGithub uses `requests` internally) |

**Prerequisites:** Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/) installed.

Install all dev and test dependencies:

```bash
uv sync --locked
```

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

No extra plugins or setup files are required beyond `uv sync`.

## Running tests

### Full suite (matches CI)

```bash
uv run pytest --cov=prevue -q
```

### Without coverage (faster iteration)

```bash
uv run pytest -q
```

### Single file

```bash
uv run pytest tests/test_copilot_adapter.py -q
```

### Single test by name

```bash
uv run pytest tests/test_classify_classifier.py::test_classify_union_multi_domain -q
```

### Subset by keyword

```bash
uv run pytest -k "classify" -q          # all classifier tests
uv run pytest -k "workflow" -q          # workflow YAML guards
uv run pytest -k "injection" -q         # prompt injection adversarial
```

### With coverage report showing uncovered lines

```bash
uv run pytest --cov=prevue --cov-report=term-missing -q
```

### Local CI mirror

`scripts/ci-local.sh` reproduces all CI steps locally: locked install, pytest with coverage, Ruff lint, Ruff format, actionlint on workflow YAML, and zizmor security scan.

```bash
./scripts/ci-local.sh
```

## Test structure

```
tests/
├── conftest.py              # Shared pytest fixtures
├── engine_helpers.py        # Reusable builders for engine adapter tests
├── fixtures/
│   ├── *.json               # GitHub API / event payloads
│   └── skills/              # Skill file trees for loader tests
└── test_*.py                # One module per source area (41 files)
```

### Test modules by area

| Area | Test files | What they cover |
|------|------------|-----------------|
| Classification | `test_classify_classifier.py`, `test_classify_filter.py`, `test_classify_router.py`, `test_classify_rules.py`, `test_llm_fallback.py` | Deterministic glob rules, multi-label union, filter step, routing map, LLM fallback for unmatched files, skill-name escalation |
| Skills & packing | `test_skills_loader.py`, `test_skills_builtin.py`, `test_skills_merge.py`, `test_selection.py`, `test_pack.py`, `test_tokens.py` | Skill loading from disk, consumer override, hybrid keyword selection, file packing against token budget |
| Engines | `test_copilot_adapter.py`, `test_engine_contract.py`, `test_engine_flow.py`, `test_findings_parsing.py`, `test_prompt.py`, `test_multicall.py` | Copilot CLI adapter, parametrized contract tests across all registered engines, retry/degrade flow, finding parsing, prompt construction, multi-call split/merge |
| GitHub integration | `test_client.py`, `test_diff.py`, `test_comments.py`, `test_checks.py`, `test_graphql.py`, `test_fork_guard.py`, `test_dismiss.py`, `test_positions.py`, `test_fingerprint.py` | REST/GraphQL clients, diff fetch, sticky comment upsert, inline review posting, check runs, thread resolution |
| Review orchestration | `test_review_flow.py`, `test_preflight.py`, `test_gate.py`, `test_gate_validate.py`, `test_skip.py` | End-to-end `run_review` happy path and fail-closed, preflight noop, gate policy (pass/fail), skip evaluation |
| Config & models | `test_config.py`, `test_models.py`, `test_registry.py` | `prevue.yml` parsing, Pydantic model validation, engine registry |
| CLI & commands | `test_cli.py`, `test_commands.py` | Entry points, `/prevue` command dispatch |
| Security | `test_injection_adversarial.py`, `test_fork_guard.py` | Prompt injection guards, fork PR early exit |
| Workflow YAML | `test_workflow_yaml.py`, `test_reusable_workflow_yaml.py` | Static invariants on `.github/workflows/*.yml` |
| Smoke | `test_smoke.py` | Package importability and `__version__` |

### RED scaffold tests

Some test files were initially written as **RED scaffolds** (failing) before the corresponding implementation existed. As of the current codebase, all previously scaffolded modules (`prevue.skills.selection`, `prevue.importscan`, `prevue.multicall`) are implemented and their tests run normally. Do not add `@pytest.mark.skip` to any of these tests.

## Shared fixtures

### `conftest.py`

| Fixture | Type | Purpose |
|---------|------|---------|
| `sample_request` | `ReviewRequest` | Two-file diff (`.py` + `.md`) via `make_sample_request()` |
| `set_all_engine_keys` | `None` | Sets `COPILOT_GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `CURSOR_API_KEY` via `monkeypatch` |
| `responses_activated` | `responses.RequestsMock` | Active HTTP mock context for GitHub REST tests |
| `fake_engine` | `FakeEngine` | Stub adapter returning a canned `ReviewResult` with no findings |
| `skills_fixture_root` | `Path` | `tests/fixtures/skills/` — used by loader tests |
| `event_json` | `dict` | Parsed `event_pull_request.json` — standard PR event payload |
| `gap_shape_skill` | `Skill` | A skill whose `applies_to` misses a path but whose bundle is routed (tests D-12 gap shape) |

### `engine_helpers.py`

Shared builders used by engine adapter tests. Import directly when `conftest.py` fixtures are not granular enough:

```python
from tests.engine_helpers import (
    VALID_TOKEN,        # valid github_pat_* format token
    VALID_FINDING,      # minimal dict matching Finding model
    PROSE_REVIEW,       # sample markdown prose from a canned engine response
    make_sample_request,  # builds a ReviewRequest with a two-file diff
    stdout_with_fence,    # builds engine stdout: prose + JSON fence
)
```

`stdout_with_fence(payload=[VALID_FINDING])` produces the two-section output format the Copilot adapter expects: markdown prose followed by a fenced JSON array.

### JSON fixtures (`tests/fixtures/`)

Static payloads loaded by tests using `Path(__file__).parent / "fixtures" / name`:

| File | Used for |
|------|----------|
| `event_pull_request.json` | Standard `pull_request` event payload |
| `event_pull_request_fork.json` | Fork PR event for fork guard tests |
| `issue_comment_event.json` | Issue comment command context |
| `pulls_files.json` | `GET /repos/.../pulls/.../files` response |
| `compare_ahead.json`, `compare_diverged.json`, `compare_identical.json` | Compare API responses |
| `graphql_review_threads.json` | GraphQL review thread list (one open, one resolved) |
| `graphql_resolve_ok.json` | Successful thread resolve mutation response |
| `graphql_forbidden.json` | 403 error from GraphQL resolve (non-fatal path) |

### Skill fixtures (`tests/fixtures/skills/`)

Skill trees used by loader unit tests. Each subdirectory is a bundle:

| Directory | Contents |
|-----------|----------|
| `skills/security/` | `committed-secrets.md`, `input-validation.md` |
| `skills/frontend/` | `accessibility.md` |
| `skills/backend/` | `error-handling.md` |
| `skills/consumer/security/` | Consumer overrides and consumer-only rules, including an oversized skill |
| `skills/consumer/payments/` | Domain-specific consumer skill |
| `skills/consumer-malformed/malformed/` | Skill missing `applies_to` — triggers `ValidationError` in `test_missing_applies_to_raises` |

## Mocking strategy

### GitHub REST API — `responses` library

PyGithub sends HTTP requests via `requests`. Tests intercept these with the **responses** library. Two patterns are used:

**Decorator pattern** — simplest, most common:

```python
import responses

@responses.activate
def test_load_pr_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/prevue")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/prevue/pulls/42",
        json={"number": 42, "base": {"sha": "abc"}, "head": {"sha": "def"}},
        status=200,
    )
    ctx = load_pr_context()
    assert ctx.pr_number == 42
```

**Fixture pattern** — when you need to inspect calls or register multiple routes before the test runs:

```python
def test_with_mock(responses_activated: responses.RequestsMock) -> None:
    responses_activated.add(responses.GET, url, json=payload)
    # call code under test
```

**Regex URL matching** — used where PyGithub may append `:443`:

```python
responses.add(
    responses.GET,
    re.compile(r"https://api\.github\.com(?::443)?/repos/owner/prevue/?$"),
    json=repo_payload,
)
```

Fixture JSON payloads from `tests/fixtures/` are loaded and registered in helper functions. See the `_register_graphql` pattern in `test_comments.py` for GraphQL POST mocking.

### Engine subprocess — `monkeypatch`

Engine adapters invoke CLI tools via `subprocess.run`. Tests patch this directly:

```python
def test_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = CopilotCliAdapter().review(make_sample_request())
    assert result.degraded is False
```

Never mock `subprocess.run` at module level — always use `monkeypatch` so the patch is scoped to a single test.

### PyGithub objects — `unittest.mock.MagicMock`

For tests that need a PyGithub `PullRequest` or `Repository` object but do not need real HTTP:

```python
from unittest.mock import MagicMock

pr = MagicMock()
pr.get_issue_comments.return_value = []
pr.create_issue_comment.return_value = MagicMock()

upsert_sticky(pr, result)

pr.create_issue_comment.assert_called_once()
```

This pattern dominates `test_comments.py` and avoids the overhead of wiring up full REST fixtures for pure logic tests.

## Writing new tests

### File naming

Create `tests/test_<module>.py` to match the source module path. Examples:

- `src/prevue/github/diff.py` → `tests/test_diff.py`
- `src/prevue/classify/filter.py` → `tests/test_classify_filter.py`

Pytest discovers functions prefixed `test_` and classes prefixed `Test`.

### Patterns to follow

1. **Test at the public API boundary.** Import from `prevue.*`, not from `prevue._internal` or test-private helpers, unless testing a specific edge case that requires access to a private function (e.g. `_sanitize_stderr` in `test_copilot_adapter.py`).

2. **Prefer fixtures over inline setup.** Use `sample_request`, `fake_engine`, and `responses_activated` from `conftest.py` before writing equivalent setup inline.

3. **Use `monkeypatch` for environment variables.** Never `os.environ[...] = ...` in tests — it leaks across tests. Use `monkeypatch.setenv` / `monkeypatch.delenv`.

4. **Put reusable payloads in `tests/fixtures/`** as JSON files and load them with `Path(__file__).parent / "fixtures" / "name.json"`.

5. **Parametrize table-driven cases** with `@pytest.mark.parametrize`. See `test_classify_classifier.py::test_classify_matched_glob_provenance` and `test_classify_rules.py::test_ruleset_rejects_malformed_mapping` for examples.

6. **For workflow changes**, add assertions in `test_workflow_yaml.py` or `test_reusable_workflow_yaml.py` whenever a key in `.github/workflows/*.yml` changes (permissions, pinned SHAs, secret names).

7. **For RED scaffold modules**, do not bypass `_require_module()`. Implement the source module until the test passes green.

### Example: new unit test with responses mock

```python
"""Tests for a new GitHub client helper."""
from __future__ import annotations

import responses
import pytest
from prevue.github.client import load_pr_context

@responses.activate
def test_load_pr_context_reads_head_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/prevue")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/prevue/pulls/1",
        json={
            "number": 1,
            "state": "open",
            "title": "feat: new thing",
            "body": "",
            "base": {"sha": "base000", "repo": {"full_name": "owner/prevue"}},
            "head": {"sha": "head111", "repo": {"full_name": "owner/prevue"}},
        },
        status=200,
    )
    ctx = load_pr_context()
    assert ctx.pr_number == 1
```

### Example: engine adapter test with subprocess mock

```python
"""Test a new engine adapter behaviour."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
import pytest
from prevue.engines.copilot_cli import CopilotCliAdapter
from tests.engine_helpers import VALID_TOKEN, make_sample_request, stdout_with_fence

def test_passes_model_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
    captured_env: dict = {}

    def _capture(_cmd, env=None, **_kwargs):
        captured_env.update(env or {})
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    req = make_sample_request()
    req = req.model_copy(update={"model": "gpt-4.1"})
    CopilotCliAdapter().review(req)
    assert captured_env.get("COPILOT_MODEL") == "gpt-4.1"
```

## Workflow YAML tests

`test_workflow_yaml.py` and `test_reusable_workflow_yaml.py` enforce security and structural invariants on all workflow files by loading YAML and asserting on keys, permission scopes, secret names, and shell snippets. No mocking required — these tests read files off disk.

Invariants verified include:

- No `pull_request_target` trigger or `secrets: inherit` (critical security gates)
- `actions/checkout` and `astral-sh/setup-uv` pinned to SHA (not tag aliases)
- Job permissions scoped to `contents: read` (CI) or `write` only for required scopes
- Named secret pass-through to reusable workflow (`copilot-token:`, `anthropic-api-key:`, etc.)
- Fork PR guard and draft PR guard conditions present
- Engine CLI version pins in `install-engine-cli.sh` match the constants in `test_workflow_yaml.py`
- CI-wait polling job exists in `prevue-review.yml` before Prevue review dispatch

Run workflow guards in isolation:

```bash
uv run pytest tests/test_workflow_yaml.py tests/test_reusable_workflow_yaml.py -v
```

When changing a workflow file, update the corresponding version constant or assertion in the test file. The constants `COPILOT_CLI_VERSION`, `CLAUDE_CODE_CLI_VERSION`, `SETUP_UV_SHA`, and `CHECKOUT_SHA` at the top of `test_workflow_yaml.py` are the source of truth for the test.

## Coverage requirements

Coverage is collected in CI with `--cov=prevue` but **no minimum threshold is configured** — there is no `fail_under` in `pyproject.toml` or a coverage config file.

Coverage data goes to `.coverage` (gitignored). To see a line-level report locally:

```bash
uv run pytest --cov=prevue --cov-report=term-missing -q
```

HTML report:

```bash
uv run pytest --cov=prevue --cov-report=html -q
# open htmlcov/index.html
```

## CI integration

The `CI` workflow (`.github/workflows/ci.yml`) runs on every push and PR to any branch.

| Step | Command | Purpose |
|------|---------|---------|
| Checkout | `actions/checkout` (SHA-pinned) | Clean workspace |
| Install uv | `astral-sh/setup-uv@v8` (SHA-pinned, uv 0.11.21) | Reproducible toolchain |
| Install deps | `uv sync --locked` | Dev + test dependencies |
| Tests | `uv run pytest --cov=prevue -q` | Full suite with coverage |
| Lint | `uv run ruff check .` | Python style (E, F, I, UP rule sets) |
| Format | `uv run ruff format --check .` | Formatting enforcement |
| actionlint | `actionlint` on 5 workflow files | Workflow YAML syntax and expression types |
| zizmor | `zizmorcore/zizmor-action` on `.github/workflows` | Actions security smell detection |

All steps must pass before a PR can merge. The dogfood `review.yml` waits for the CI job to pass on the PR head SHA before invoking Prevue review, so the test suite and CI form the trust boundary consumers rely on.

## Next steps

- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline components exercised by the test suite
- [configuration.md](configuration.md) — `prevue.yml` options validated in `test_config.py`
- [DEVELOPMENT.md](DEVELOPMENT.md) — local setup, build commands, and linting
