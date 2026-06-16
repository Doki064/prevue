<!-- generated-by: gsd-doc-writer -->
# Contributing to Prevue

Thank you for helping improve Prevue. This guide covers setup, code style, commit conventions, and how to open a pull request.

## Development setup

See [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) for prerequisites, clone/install steps, and first run.

For day-to-day development workflow — local setup, build commands, and branch conventions — see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

For running and writing tests, see [docs/TESTING.md](docs/TESTING.md).

## Coding standards

Prevue uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration lives in `pyproject.toml` (`line-length = 100`, `target-version = "py312"`, rules `E`, `F`, `I`, `UP`).

Run checks locally:

```bash
uv run ruff check .
uv run ruff format --check .
```

Auto-fix lint and format issues:

```bash
uv run ruff check --fix .
uv run ruff format .
```

CI enforces both commands on every push and pull request (`.github/workflows/ci.yml`).

## Run CI locally before you push

Mirror the CI `test-and-lint` job with:

```bash
./scripts/ci-local.sh
```

The script runs, in order:

1. `uv sync --locked`
2. `uv run pytest --cov=prevue -q`
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. `actionlint` on workflow YAML files
6. `zizmor` security scan on `.github/workflows/`

`actionlint` is installed via `go install` if missing. Ensure [uv](https://docs.astral.sh/uv/) and optionally [Go](https://go.dev/) are installed before running the script.

Run this before opening or updating a PR so CI failures are caught early.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

Common types in this repo:

| Type | Use for |
|------|---------|
| `feat` | New behavior or capability |
| `fix` | Bug fixes |
| `test` | Tests only |
| `docs` | Documentation |
| `chore` | Tooling, CI, deps, housekeeping |
| `style` | Formatting / lint fixes with no logic change |

Scope is optional but encouraged when it clarifies the area (`fix(dogfood):`, `chore(ci):`, `feat(08):`).

Examples from recent history:

```
feat(dogfood): run Prevue review after CI via workflow_run
fix(review): annotate diffs and reconcile finding lines
chore(dev): add local CI mirror script
test(08): orchestration and integration tests
```

Keep the subject line concise. Add a body only when the *why* is not obvious from the subject.

## Pull request guidelines

1. **Branch from `main`** — use a descriptive branch name (e.g. `feat/incremental-review`, `fix/fork-skip-message`). No formal naming scheme is documented; match existing PR branch style.
2. **One logical change per PR** — keep diffs focused and reviewable.
3. **Run `./scripts/ci-local.sh`** — all steps must pass before you request review.
4. **Add or update tests** — behavior changes should include pytest coverage in `tests/`. See [docs/TESTING.md](docs/TESTING.md).
5. **Update docs when needed** — user-facing config, setup, or workflow changes should update the relevant file under `docs/`.
6. **Open against `main`** — CI runs on every pull request via the [CI workflow](.github/workflows/ci.yml).

Reviewers look for: correct behavior, test coverage, ruff-clean code, workflow YAML lint/security checks, and clear commit/PR descriptions.

## Issue reporting

Report bugs and feature requests via [GitHub Issues](https://github.com/Doki064/prevue/issues).

Include:

- **Bug reports** — steps to reproduce, expected vs actual behavior, Prevue version or workflow pin, and relevant `prevue.yml` or workflow snippets (redact secrets).
- **Feature requests** — the problem you are solving and any constraints (token budget, engine choice, fork support, etc.).

No issue templates are configured yet; the above fields help us triage faster.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
