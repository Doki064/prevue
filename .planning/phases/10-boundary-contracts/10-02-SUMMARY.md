---
phase: 10-boundary-contracts
plan: "02"
subsystem: engines
tags: [engn-10, adapter-consolidation, spec-driven, registry, antigravity]
dependency_graph:
  requires: [10-01]
  provides: [cli-engine-spec, cli-engine-adapter, auto-populated-registry]
  affects: [registry, copilot-cli, claude-code-cli, cursor-cli, antigravity-cli]
tech_stack:
  added: []
  patterns:
    - spec-driven generic adapter (CliEngineAdapter + CliEngineSpec, D-01)
    - per-engine AuthError subclasses in errors.py (no circular imports)
    - registry auto-population from CLI_ENGINE_SPECS iteration (D-01/D-03)
    - functional flag replaces SKELETON_ENGINES (D-03)
key_files:
  created:
    - src/prevue/engines/spec.py
    - src/prevue/engines/cli_adapter.py
  modified:
    - src/prevue/engines/errors.py
    - src/prevue/engines/registry.py
    - src/prevue/engines/copilot_cli.py
    - src/prevue/engines/cursor_cli.py
    - src/prevue/engines/claude_code_cli.py
    - src/prevue/engines/gemini_cli.py
    - tests/test_engine_contract.py
    - tests/test_registry.py
    - tests/test_copilot_adapter.py
decisions:
  - "AuthError subclasses moved to errors.py to break circular import (spec.py←per-engine←spec.py)"
  - "CopilotCliAdapter backward-compat alias kept in copilot_cli.py as CliEngineAdapter subclass"
  - "argv order for tempfile-arg: base_argv → tempfile_flag+path → model_argv_flag+model (preserves test assertions)"
  - "test_copilot_adapter.py MAX_PROMPT_BYTES patch updated to also patch prompt_module to reach CliEngineAdapter"
  - "pre-existing ruff lint errors in Plan 01 RED scaffold files fixed as part of cleanup"
metrics:
  duration: 15min
  completed: "2026-06-29"
  tasks: 3
  files: 11
---

# Phase 10 Plan 02: CLI Engine Adapter Consolidation (ENGN-10) Summary

Collapsed four near-identical CLI adapters into one concrete `CliEngineAdapter` driven by a declarative `CliEngineSpec` — adding a CLI engine is now one data entry with no duplicated methods, and the registry auto-populates from `CLI_ENGINE_SPECS`.

## What Was Built

### Task 1: CliEngineSpec + CLI_ENGINE_SPECS

Created `src/prevue/engines/spec.py` with a frozen pydantic `CliEngineSpec` model and a 4-entry `CLI_ENGINE_SPECS` tuple. Each spec captures per-engine variation on ~7 axes: `secret_env`, `auth_error`, `validate_secret`, `base_argv`, `prompt_delivery` (stdin/tempfile-arg/argv), `model_flag` (env/argv/none), `usage_capture` (otel-jsonl/stdout-json/none), `functional`. Copilot's exact `github_pat_` prefix validation and error message are preserved. Antigravity replaces the Gemini skeleton (D-12) as a fully functional spec with `ANTIGRAVITY_API_KEY` env.

`*AuthError` subclasses were moved to `errors.py` to avoid a circular import (`spec.py` imports `AuthError` subclasses; per-engine modules now re-export from `errors.py`).

### Task 2: CliEngineAdapter generic + slimmed per-engine modules

Created `src/prevue/engines/cli_adapter.py` with `class CliEngineAdapter(EngineAdapter)` that:
- Reads `spec.secret_env`, calls `spec.validate_secret()` (raises `spec.auth_error` on failure)
- Assembles argv from `spec.base_argv` + model flag (env or argv order) + prompt delivery (stdin/tempfile-arg/argv)
- For cursor/tempfile-arg: order is `base_argv → -f tmp_path → -m model` (byte-identical to old cursor_cli)
- For antigravity/argv: prompt is the final argv element after base_argv + model flag
- Passes `secret=token` to `invoke_subprocess_text` for stderr sanitization (T-10-02)
- Delegates `review` to `flow.review_with_retry`, `classify`/`classify_skills` to prompt module

Per-engine modules slimmed to re-export their `*AuthError` classes only. `copilot_cli.py` retains `__all__` re-exports and `_sanitize_stderr` alias for test compatibility, plus a `CopilotCliAdapter` backward-compat alias. `gemini_cli.py` → `AntigravityAuthError` re-export.

### Task 3: Auto-populated registry + updated tests

Rewrote `registry.py` to build `ENGINES = {spec.name: spec for spec in CLI_ENGINE_SPECS}`. `get_adapter(name)` returns `CliEngineAdapter(spec)`. `require_functional_adapter` checks `spec.functional` instead of `SKELETON_ENGINES` (D-03). `SKELETON_ENGINES` removed entirely. `DEFAULT_ENGINE = "copilot-cli"` preserved.

Updated test suites:
- `test_engine_contract.py`: FUNCTIONAL = all 4 engines; AUTH_ENV + antigravity-cli; test_vendor_argv handles antigravity; test_gemini_classify_raises_not_implemented removed
- `test_registry.py`: Full rewrite — checks CliEngineAdapter type, all 4 names registered, antigravity functional, SKELETON_ENGINES absent, gemini-cli not in ENGINES

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved AuthError subclasses to errors.py**
- **Found during:** Task 1 — `spec.py` importing from `copilot_cli.py` which would import from `cli_adapter.py` which imports `spec.py` (circular)
- **Fix:** Define all 4 `*AuthError` subclasses in `errors.py`; per-engine modules re-export via `from prevue.engines.errors import XxxAuthError`
- **Files modified:** `errors.py`, `copilot_cli.py`, `cursor_cli.py`, `claude_code_cli.py`, `gemini_cli.py`, `spec.py`
- **Commit:** ae1fa64 + 19f8a13

**2. [Rule 1 - Bug] MAX_PROMPT_BYTES monkeypatch no longer reached CliEngineAdapter**
- **Found during:** Task 2 — `test_retry_skipped_when_retry_prompt_exceeds_limit` patches `copilot_cli.MAX_PROMPT_BYTES` but the generic uses `prevue.engines.prompt.MAX_PROMPT_BYTES`
- **Fix:** Updated test to also patch `prompt_module.MAX_PROMPT_BYTES`; changed `cli_adapter.py` to use `_prompt_module.MAX_PROMPT_BYTES` (module reference lookup, patchable)
- **Files modified:** `tests/test_copilot_adapter.py`, `src/prevue/engines/cli_adapter.py`
- **Commit:** 19f8a13

**3. [Rule 1 - Bug] argv order for cursor model flag was wrong**
- **Found during:** Task 2 — original cursor_cli.py appends `-f tmp_path` THEN `-m model`; generic was adding model flag before tempfile
- **Fix:** Moved model argv assembly to after tempfile-arg append for `prompt_delivery=="tempfile-arg"` branch
- **Files modified:** `src/prevue/engines/cli_adapter.py`
- **Commit:** 19f8a13

**4. [Rule 1 - Bug] Pre-existing ruff errors in Plan 01 RED scaffold files**
- **Found during:** Final ci-local.sh check
- **Fix:** Removed unused imports (`re`, `ReviewConfig`, `os`, `NO_CONSUMER_CONFIG_SENTINEL`), fixed import ordering, fixed line length
- **Files modified:** `tests/test_config_precedence.py`, `tests/test_output_contract.py`, `tests/test_raw_args.py`
- **Commit:** f1fdf18

## Commits

| Hash | Description |
|------|-------------|
| ae1fa64 | feat(10-02): define CliEngineSpec + CLI_ENGINE_SPECS for all 4 CLI engines |
| 19f8a13 | feat(10-02): implement CliEngineAdapter generic + slim per-engine modules |
| f1fdf18 | feat(10-02): auto-populate registry from CLI_ENGINE_SPECS; functional flag; update tests |

## Verification Results

- `uv run pytest tests/test_engine_contract.py tests/test_registry.py -x -q` — 46 passed
- `uv run pytest tests/test_copilot_adapter.py -x -q` — 34 passed
- `uv run pytest -q` — 746 passed, 37 failed (all pre-existing RED scaffolds from Plan 01)
- `grep -rF -- '--allow-tool' src/prevue/engines/` — CLEAN (T-10-03)
- `uv run ruff check . && uv run ruff format --check .` — CLEAN

## Threat Flags

No new threat surface introduced. The generic adapter preserves all existing mitigations:
- T-10-02: `secret=token` passed to `invoke_subprocess_text` → `sanitize_stderr` on failure
- T-10-03: `--allow-tool` absent (static scan green)
- T-10-04: `spec.validate_secret` raises `spec.auth_error` before subprocess (copilot prefix check preserved)
- T-10-05: Registry still fail-closed; antigravity-cli is the public name, no alias for gemini-cli

## Self-Check: PASSED

- spec.py: FOUND
- cli_adapter.py: FOUND
- SUMMARY.md: FOUND
- Commit ae1fa64: FOUND
- Commit 19f8a13: FOUND
- Commit f1fdf18: FOUND
