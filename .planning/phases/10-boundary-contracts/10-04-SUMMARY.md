---
phase: 10-boundary-contracts
plan: "04"
subsystem: config
tags: [wkfl-05, engn-08, engn-09, tdd, config-precedence, raw-args, model-roles, engine-config]
dependency_graph:
  requires:
    - "10-01: RED scaffold test files (test_config_precedence, test_raw_args, test_model_roles)"
    - "10-02: CliEngineAdapter generic (raw_args appended into _invoke)"
  provides:
    - "prevue.config.EngineConfig (name, model, models, raw_args: list[str], pricing, extra=forbid)"
    - "prevue.config.EngineModels (classify/review/consolidate sub-model, extra=forbid)"
    - "prevue.config._resolve_model (PREVUE_MODEL > COPILOT_MODEL > yml > None)"
    - "prevue.config._resolve_engine_models (per-role dict: classify/review/consolidate)"
    - "prevue.config.CONFIG_PRECEDENCE (declared precedence constant, WKFL-05/D-07)"
    - "cli_adapter raw_args append LAST (ENGN-08/D-10, list form, no shell=True)"
    - "review.py per-role model resolution at classify + review call-sites (ENGN-09/D-11)"
  affects:
    - "PrevueConfig: new engine_config field (back-compat: engine string preserved)"
    - "CliEngineAdapter: _raw_args instance var injected from engine_config"
    - "review.py: _review_model + _classify_model resolved via _resolve_engine_models"
tech_stack:
  added: []
  patterns:
    - "EngineModels sub-model with ConfigDict(extra=forbid) for per-role model fields"
    - "EngineConfig @field_validator rejecting str raw_args (D-10 command injection guard)"
    - "_resolve_engine_models(raw) -> dict[str, str|None] — per-role with single fallback"
    - "raw_args injected post-get_adapter in review.py (base-ref-only gating preserved)"
    - "Consolidate slot reserved (D-13): resolves in config, unused until Phase 13 QUAL-01"
key_files:
  created: []
  modified:
    - src/prevue/config.py
    - src/prevue/engines/cli_adapter.py
    - src/prevue/review.py
key_decisions:
  - "CONFIG_PRECEDENCE constant + module docstring declare workflow input > .github/prevue.yml > built-in defaults (WKFL-05/D-07) — both machine-readable constant and human-readable doc"
  - "raw_args injected into adapter._raw_args in review.py post-get_adapter (not in registry.get_adapter) so the raw_args always comes from the single load_config read (base-ref gating preserved)"
  - "raw_args not passed to classify/classify_skills — extra engine flags are review-only (D-10: classify is a low-cost controlled call; raw_args are consumer escape hatch for review engine tuning)"
  - "consolidate slot resolves in _resolve_engine_models but nothing consumes it (D-13: merge_findings stays deterministic fingerprint-dedup; Phase 13 QUAL-01 will wire it)"
  - "_review_model_str unified to _review_model at the whole-run-cap and ReviewRequest build sites — single resolution point (no duplicate env reads)"
metrics:
  duration: 6min
  completed: "2026-06-29"
  tasks: 2
  files: 3
requirements_completed: [WKFL-05, ENGN-08, ENGN-09]
---

# Phase 10 Plan 04: Config Precedence + raw_args + Per-Role Model Tiering Summary

Locked three contract additions: declared+tested config precedence (WKFL-05/D-07), raw-args passthrough as list form (ENGN-08/D-10, base-ref-only), and per-role model tiering (ENGN-09/D-11, classify/review/consolidate with single-model fallback). Consolidate slot reserved for Phase 13 QUAL-01 (D-13); merge determinism unchanged.

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-29T10:53:12Z
- **Completed:** 2026-06-29T11:00:02Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

### Task 1: EngineConfig + declared precedence + raw_args/pricing base-ref-only

- Added `CONFIG_PRECEDENCE = "workflow input > .github/prevue.yml > built-in defaults"` constant and matching module docstring to `config.py` (WKFL-05/D-07)
- Added `EngineModels` pydantic sub-model (`classify`/`review`/`consolidate`, all `str | None`, `extra="forbid"`) for per-role model fields
- Added `EngineConfig` pydantic model (`name`, `model`, `models`, `raw_args: list[str]`, `pricing`, `extra="forbid"`) with a `@field_validator` that rejects string `raw_args` with a clear error (D-10: command injection guard)
- Added `_resolve_model(raw) -> str | None`: `PREVUE_MODEL` env > `COPILOT_MODEL` env > `engine.model` in yml > None
- Added `_resolve_engine_models(raw) -> dict[str, str|None]`: per-role dict with `models.<role>` or `engine.model` fallback for `classify`/`review`/`consolidate`
- Added `_build_engine_config(raw)` helper; wired `engine_config: EngineConfig` into `PrevueConfig` and `load_config()` (back-compat: `engine` string field preserved)
- All 40 tests in `test_config_precedence.py` + `test_raw_args.py` + `test_config.py` GREEN

### Task 2: raw_args argv append + per-role model resolution

- `CliEngineAdapter.__init__` accepts optional `raw_args: list[str] | None` (default `[]`) stored as `self._raw_args`
- `_invoke(raw_args=...)` appends extra flags LAST after all framework-generated argv (base_argv + prompt-delivery flags + model flag + `raw_args`). Never shell-joined, never `shell=True`
- `review()` passes `self._raw_args` to `_invoke`; `classify()`/`classify_skills()` exempt (raw_args are review-engine tuning, not classify)
- `review.py` imports `_resolve_engine_models` and resolves `_classify_model` + `_review_model_from_config` from `config.engine_config` right after getting the engine adapter
- `engine._raw_args` injected from `config.engine_config.raw_args` in `review.py` (post-`get_adapter`, so raw_args always sourced from the gated `load_config` read — SKIL-04/Pitfall 4 preserved)
- `llm_classify` call-site uses `_classify_model or fallback_cfg.model` (models.classify > fallback.model)
- `llm_select_skills` call-site uses `_skill_select_model` (classify model chain)
- `_review_model_str` unified to `_review_model` (no duplicate env reads)
- `multicall.py` `merge_findings` UNCHANGED — D-13 fingerprint-dedup preserved
- All 64 tests in `test_model_roles.py` + `test_engine_contract.py` + `test_multicall.py` GREEN

## Task Commits

1. **Task 1: EngineConfig + _resolve_model/_resolve_engine_models + declared precedence** - `ae64e17` (feat)
2. **Task 2: raw_args argv append (generic) + per-role model resolution at review sites** - `a327b70` (feat)

## Files Created/Modified

- `src/prevue/config.py` — `CONFIG_PRECEDENCE` constant, module docstring, `EngineModels`, `EngineConfig`, `_resolve_model`, `_resolve_engine_models`, `_build_engine_config`, `PrevueConfig.engine_config` field wired in `load_config`
- `src/prevue/engines/cli_adapter.py` — `__init__(raw_args=)`, `_invoke(raw_args=)` appends LAST, `review()` passes `self._raw_args`
- `src/prevue/review.py` — imports `_resolve_engine_models`; resolves `_classify_model`/`_review_model_from_config`; injects `engine._raw_args`; `_review_model_str` unified

## Verification Results

- `uv run pytest tests/test_config_precedence.py tests/test_raw_args.py tests/test_model_roles.py tests/test_config.py tests/test_engine_contract.py tests/test_multicall.py -x -q` — 104 passed
- `uv run pytest -q` — 776 passed, 8 failed (all pre-existing Plan 01 RED scaffolds for Plan 05 OUTP-05)
- `grep -qi 'workflow input > .*prevue.yml > .*default' src/prevue/config.py` — FOUND (precedence statement present)
- `grep -q 'NO_CONSUMER_CONFIG_SENTINEL\|GITHUB_ACTIONS' tests/test_raw_args.py` — FOUND (Pitfall 4 base-ref-only assertion)
- `grep -rn 'shell=True' src/prevue/engines/cli_adapter.py` — CLEAN (only in comment, no actual shell=True)
- `git diff --stat src/prevue/multicall.py` — no changes (merge_findings D-13 preserved)
- `uv run ruff check . && uv run ruff format --check .` — CLEAN

## Deviations from Plan

None — plan executed exactly as written. Two minor implementation decisions:

1. **raw_args injection location**: Injected into `engine._raw_args` post-`get_adapter()` in `review.py` rather than rebuilding the adapter — this is the simpler approach that keeps `get_adapter()` stateless and preserves the existing test_engine_contract.py adapter fixture behavior.
2. **_review_model_str unification**: The second `_review_model_str = os.environ.get(...)` assignment was replaced with `_review_model_str = _review_model` (pointing to the already-resolved model), eliminating a duplicate env read while keeping the variable name for the ReviewRequest build site.

## Known Stubs

None — all three contracts fully wired: precedence documented and tested, raw_args appended in generic, per-role models resolved at call-sites. The consolidate slot is intentionally unused (D-13 — reserved for Phase 13); this is a documented design decision, not a stub.

## Threat Flags

No new threat surface beyond what the plan's threat model covers:

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-10-09 | src/prevue/review.py | raw_args from engine_config (load_config read, gated by sentinel); PR-head raw_args is ignored |
| mitigated: T-10-10 | src/prevue/engines/cli_adapter.py | List form only; appended to argv list; no shell=True; @field_validator rejects string raw_args |
| mitigated: T-10-11 | src/prevue/config.py | pricing parsed from same base-ref-only gated read; extra=forbid on EngineConfig |

## Self-Check

Files exist:
- src/prevue/config.py: FOUND (modified)
- src/prevue/engines/cli_adapter.py: FOUND (modified)
- src/prevue/review.py: FOUND (modified)

Commits exist: ae64e17, a327b70

## Self-Check: PASSED

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-29*
