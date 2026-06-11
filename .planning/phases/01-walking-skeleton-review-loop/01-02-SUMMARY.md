---
phase: 01-walking-skeleton-review-loop
plan: 02
subsystem: testing
tags: [uv, pytest, ruff, responses, actionlint, zizmor, pygithub, pydantic]

requires: []
provides:
  - uv-managed prevue package skeleton with github/ and engines/ namespaces
  - pytest/ruff/responses test infrastructure with recorded GitHub fixtures
  - CI gate running pytest, ruff, actionlint, and zizmor on every push/PR
affects: [01-03, 01-04, 01-05, 01-06, 01-07]

tech-stack:
  added: [uv 0.11.20, PyGithub 2.9.1, pydantic 2.13.4, pytest 9.0.3, pytest-cov 7.1.0, responses 0.26.1, ruff 0.15.17]
  patterns: [src-layout package, SHA-pinned GitHub Actions, contents:read CI permissions, recorded REST fixtures]

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - src/prevue/__init__.py
    - src/prevue/cli.py
    - src/prevue/github/__init__.py
    - src/prevue/engines/__init__.py
    - tests/conftest.py
    - tests/test_smoke.py
    - tests/fixtures/pulls_files.json
    - tests/fixtures/event_pull_request.json
    - .github/workflows/ci.yml
    - .gitignore
  modified: []

key-decisions:
  - "pytest smoke test added because pytest 9 exits 5 when zero tests collected"
  - "conftest defines stub ReviewResult/EngineAdapter types until Plan 03 models land"
  - "CI uses zizmor-action (SHA-pinned) scanning .github/workflows for SECR-01 posture"

patterns-established:
  - "P5: uv-managed src/prevue layout with committed uv.lock"
  - "P4: thin CI workflow — setup-uv, sync, test/lint only; no business logic"
  - "Recorded GitHub REST + event JSON fixtures under tests/fixtures/"

requirements-completed: [SECR-01]

duration: 14min
completed: 2026-06-11
---

# Phase 01 Plan 02: Project Scaffold + Test Infrastructure + CI Summary

**uv-managed prevue package with pytest/ruff fixtures and a CI gate enforcing SECR-01 via actionlint and zizmor**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-11T19:15:00Z
- **Completed:** 2026-06-11T19:29:22Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments

- Greenfield `prevue` package installs via `uv sync --locked` with PyGithub and pydantic runtime deps
- Shared test fixtures (`responses_activated`, `fake_engine`, `event_json`) plus recorded GitHub API payloads
- CI workflow runs pytest with coverage, ruff check/format, actionlint, and zizmor on push/PR

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold the uv package and dependency/tooling config** - `56cf212` (feat)
2. **Task 2: Add shared test fixtures and recorded GitHub REST payloads** - `2db3bfb` (feat)
3. **Task 3: Add the CI workflow (pytest + ruff + actionlint + zizmor)** - `c1aea12` (feat)

## Files Created/Modified

- `pyproject.toml` - Package metadata, scripts entrypoint, pytest/ruff config, pinned deps
- `uv.lock` - Reproducible dependency lockfile
- `src/prevue/` - Package root with `github/` and `engines/` namespaces
- `tests/conftest.py` - Shared pytest fixtures for API mocking and fake engine
- `tests/fixtures/pulls_files.json` - Recorded GET /pulls/{n}/files payload
- `tests/fixtures/event_pull_request.json` - Sample GITHUB_EVENT_PATH payload
- `.github/workflows/ci.yml` - Test, lint, and workflow-security gate
- `.gitignore` - Python/venv/test cache ignores

## Decisions Made

- Added `tests/test_smoke.py` so pytest exits 0 (pytest 9 returns exit code 5 with zero collected tests)
- Stub contract types in `conftest.py` until Plan 03 creates `prevue.models`
- Used zizmor-action with `advanced-security: false` for repos without GitHub Advanced Security

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv init nested subdirectory**
- **Found during:** Task 1
- **Issue:** `uv init --package prevue` created `prevue/prevue/` instead of repo root
- **Fix:** Moved pyproject.toml, src/, and .python-version to repository root
- **Files modified:** pyproject.toml, src/prevue/*
- **Committed in:** 56cf212

**2. [Rule 3 - Blocking] Missing README.md broke uv build**
- **Found during:** Task 1
- **Issue:** pyproject.toml references readme = "README.md" but file absent after scaffold move
- **Fix:** Created minimal README.md
- **Files modified:** README.md
- **Committed in:** 56cf212

**3. [Rule 2 - Missing Critical] CLI entrypoint stub**
- **Found during:** Task 1
- **Issue:** `[project.scripts]` points to `prevue.cli:main` which did not exist
- **Fix:** Added `src/prevue/cli.py` with placeholder `main()`
- **Files modified:** src/prevue/cli.py
- **Committed in:** 56cf212

**4. [Rule 1 - Bug] pytest exit code 5 with no tests**
- **Found during:** Task 1 verification
- **Issue:** `uv run pytest -q` exited 5 when no tests collected (pytest 9 default)
- **Fix:** Added `tests/test_smoke.py` asserting package imports
- **Files modified:** tests/test_smoke.py, tests/__init__.py
- **Committed in:** 56cf212

---

**Total deviations:** 4 auto-fixed (1 bug, 2 blocking, 1 missing critical)
**Impact on plan:** All fixes required for verification and install correctness. No scope creep.

## Issues Encountered

None beyond deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 foundation complete; Plan 03 (pydantic models) can import-test against installed package
- Downstream TDD plans can use `responses_activated`, `fake_engine`, and fixture JSON files
- CI will enforce SECR-01 posture on future workflow YAML additions
- SECR-01 fork documentation and `review.yml` wrapper remain for Plans 06–07

## Self-Check: PASSED

- FOUND: pyproject.toml
- FOUND: uv.lock
- FOUND: src/prevue/__init__.py
- FOUND: tests/conftest.py
- FOUND: tests/fixtures/pulls_files.json
- FOUND: tests/fixtures/event_pull_request.json
- FOUND: .github/workflows/ci.yml
- FOUND: 56cf212
- FOUND: 2db3bfb
- FOUND: c1aea12

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-11*
