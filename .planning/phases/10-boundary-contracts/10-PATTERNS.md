# Phase 10: Boundary Contracts - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 14 new/modified
**Analogs found:** 13 / 14 (the vendored pricing JSON is data, not code)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/prevue/engines/spec.py` (NEW) | model | transform | `src/prevue/config.py` pydantic config models (SkipConfig/FallbackConfig) | role-match (pydantic frozen model) |
| `src/prevue/engines/cli_adapter.py` (NEW) | service | request-response (subprocess) | `src/prevue/engines/copilot_cli.py` (+ cursor/claude) | exact (collapses all 4) |
| `src/prevue/engines/registry.py` (MOD) | config | transform | self (current manual dict + SKELETON_ENGINES) | self-refactor |
| `src/prevue/engines/usage.py` (NEW) | utility | transform (parse) | `src/prevue/engines/tokens.py` + `flow._token_meta` | role-match (pure parse fn) |
| `src/prevue/engines/flow.py` (MOD) | service | request-response | self (`_token_meta`/`_retry_token_meta`) | self-refactor |
| `src/prevue/engines/tokens.py` (MOD) | utility | transform | self (demote to labeled fallback) | self-refactor |
| `src/prevue/engines/{copilot,cursor,claude_code}_cli.py` (SLIM) | config | — | self (keep `*AuthError` + `__all__`) | self-refactor |
| `src/prevue/engines/gemini_cli.py` → antigravity (REPLACE) | config | — | `cursor_cli.py` (argv prompt-delivery sibling) | role-match |
| `src/prevue/pricing.py` (NEW) | utility | transform (compute) | `src/prevue/engines/tokens.py` (pure compute) + config JSON load | partial (no exact pure-compute analog) |
| `src/prevue/pricing/model_prices.json` (NEW) | config (data) | — | — | no analog (vendored data) |
| `src/prevue/config.py` (MOD) | config | transform | self (`_resolve_engine`, `FallbackConfig`) | self-refactor |
| `src/prevue/models.py` (MOD) | model | transform | self (`ReviewResult`) | self-refactor |
| `src/prevue/multicall.py` (MOD) | service | batch | self (`execute_calls`) | self-refactor |
| `src/prevue/review.py` (MOD) | service | request-response | self (`_review_model` resolution :756; sticky render) | self-refactor |
| `src/prevue/github/comments.py` (MOD) | component | transform (render) | self (token_line :535-547) | self-refactor |
| `.github/workflows/prevue-review.yml` (MOD) | config | — | self (run-review step) | self-refactor |

## Pattern Assignments

### `src/prevue/engines/spec.py` (NEW — model)

**Analog:** `src/prevue/config.py` pydantic models (frozen/extra-forbid pattern).

**Frozen pydantic model pattern** (mirror `config.py:43-49` `FallbackConfig` + RESEARCH spec shape):
```python
from typing import Callable, Literal
from pydantic import BaseModel, ConfigDict

class CliEngineSpec(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    name: str
    secret_env: str
    auth_error: type            # CopilotAuthError | ... (test compat — Pitfall 5)
    validate_secret: Callable[[str], str]
    base_argv: tuple[str, ...]
    prompt_delivery: Literal["stdin", "tempfile-arg", "argv"]
    model_flag: Literal["env", "argv", "none"]
    usage_capture: Literal["stdout-json", "otel-jsonl", "none"] = "none"
    functional: bool = True
```
The varying axes are the ground-truth Adapter Anatomy table in RESEARCH.md §315 — that table is the field list. `__all__` re-export discipline: copy from `copilot_cli.py:26-38`.

---

### `src/prevue/engines/cli_adapter.py` (NEW — service, the one generic)

**Analog:** `src/prevue/engines/copilot_cli.py` (the cleanest of the 4; cursor + claude supply the cwd/tempfile/argv-model variants).

**Auth + env build pattern** (collapse `copilot_cli.py:50-61` + `cursor_cli.py:62-66` + `claude_code_cli.py:49-53`): each adapter does the same `os.environ.get(SECRET_ENV)` → validate → `{**os.environ, SECRET_ENV: token}` (+ model env for copilot). Drive by `spec.secret_env` + `spec.validate_secret`, raise `spec.auth_error`:
```python
# copilot_cli.py:52-61 — the validator that becomes spec.validate_secret for copilot
token = os.environ.get("COPILOT_GITHUB_TOKEN", "")
if not token.startswith("github_pat_"):
    raise CopilotAuthError("COPILOT_GITHUB_TOKEN must be a fine-grained ... PAT")
env = {**os.environ, "COPILOT_GITHUB_TOKEN": token}
if model:
    env["COPILOT_MODEL"] = model   # model_flag=="env"
```

**argv assembly pattern** (per `prompt_delivery` / `model_flag`):
- stdin: copilot `["copilot","-s","--no-ask-user"]` + `input_text=prompt` (`copilot_cli.py:71-77`)
- argv-model: claude `["claude","--bare","-p","--output-format","text"]` + `["--model", model]` (`claude_code_cli.py:36-46`)
- tempfile-arg + cwd: cursor `NamedTemporaryFile` → `["cursor-agent","-p","--output-format","text","-f",tmp]` + `["-m", model]` + `cwd=PREVUE_CONSUMER_ROOT` (`cursor_cli.py:37-59`). Keep the `try/finally os.unlink` cleanup verbatim.

**review() body** (identical across all 4 — `copilot_cli.py:79-88`): build env, `flow.review_with_retry(req, invoke=lambda p: ..., secret=token, build_prompt=build_prompt, max_prompt_bytes=MAX_PROMPT_BYTES, model_label=req.model or "default")`.

**classify / classify_skills** (copy `copilot_cli.py:90-117`): note classify_skills currently exists only on copilot — moving to the generic gives it to every engine for free (RESEARCH §256 caveat).

**Hard constraint:** static scan `test_adapter_cli_commands_contain_no_allow_tool_flags` (`test_engine_contract.py:275-290`) greps every `src/prevue/engines/*.py` for `--allow-tool`. The generic + spec entries must keep that string absent.

---

### `src/prevue/engines/registry.py` (MOD — auto-populate)

**Analog:** self. Replace manual dict (lines 14-19) + `SKELETON_ENGINES` (line 12) with iteration over `CLI_ENGINE_SPECS`.

**Current shape to generalize:**
```python
# registry.py:14-21
ENGINES: dict[str, type[EngineAdapter]] = { CopilotCliAdapter.name: CopilotCliAdapter, ... }
FUNCTIONAL_ENGINES = frozenset(name for name in ENGINES if name not in SKELETON_ENGINES)
```
Target: build `ENGINES = {spec.name: spec for spec in CLI_ENGINE_SPECS}`; `get_adapter` returns `CliEngineAdapter(spec)`; `require_functional_adapter` checks `spec.functional` instead of `SKELETON_ENGINES` (D-03). Keep `UnknownEngineError`/`NonFunctionalEngineError` (lines 24-29) and the fail-closed `valid = ", ".join(sorted(...))` message (lines 36-37) unchanged. Registry must hold API siblings uniformly (D-02) — key on name, store an adapter factory, not a fixed class.

**Test impact:** `test_registry.py`, `test_engine_contract.py` (FUNCTIONAL list at :22, AUTH_ENV at :24-28, `test_vendor_argv` :117-142, `test_gemini_classify_raises_not_implemented` :269-272 — this last must change since gemini→antigravity becomes functional).

---

### `src/prevue/engines/usage.py` (NEW — utility, per-strategy parse)

**Analog:** `src/prevue/engines/tokens.py` (tiny pure module) + `flow._token_meta` (the dict shape it feeds).

**Shape it must emit** (extend `flow._token_meta` at `flow.py:15-19`):
```python
# current carrier — usage.py output extends this with input/output/cache + estimated:bool
{"review": <int>, "estimated": True}
```
Strategy dispatch keyed on `spec.usage_capture`: `stdout-json` (Claude envelope: `usage.input_tokens/output_tokens/cache_read_input_tokens` + `total_cost_usd`), `otel-jsonl` (Copilot `COPILOT_OTEL_FILE_EXPORTER_PATH` sum), else `None` → caller falls back to `estimate_tokens` with `estimated=True`. See RESEARCH §258-275 + token matrix §330.

---

### `src/prevue/engines/flow.py` (MOD — real-token capture seam)

**Analog:** self. The two token-meta builders are the only change points.

**Current fallback to demote** (`flow.py:15-34`): `_token_meta` and `_retry_token_meta` hardcode `"estimated": True`. They must accept a captured-usage dict (from `usage.capture_usage`) and set `estimated` per-engine; fall through to `estimate_tokens` only when capture returns `None`.

**Parse-path caveat (Pitfall 3, RESEARCH §410):** for `usage_capture=="stdout-json"`, `extract_json_fence(stdout)` at `flow.py:90` must run on the envelope's `result` field, not raw stdout — else every Claude review degrades. The `engine_meta["tokens"]` dict is assembled at lines 132-135 and embedded at 144-149 / 157-162; extend there, do not change the `ReviewResult` construction shape.

---

### `src/prevue/pricing.py` (NEW — pure compute)

**Analog:** `src/prevue/engines/tokens.py` (closest pure-compute module; no exact analog — listed under No Analog rationale). JSON load mirrors `config.py` `path.read_text` + parse (config.py:164) but uses stdlib `json`.

**Cost formula** (RESEARCH §349-355): `input*input_cost_per_token + output*output_cost_per_token + cache_read*cache_read_input_token_cost + cache_creation*cache_creation_input_token_cost`. Read vendored JSON from package path (never fetch — D-06a). `engine.pricing` override map takes precedence (D-06c). When Claude returns `total_cost_usd`, prefer it. Unknown model → no cost, labeled.

---

### `src/prevue/config.py` (MOD — precedence + new engine.* knobs)

**Analog:** self. Generalize `_resolve_engine` (the ONE existing precedence impl).

**The precedence pattern to mirror per knob** (`config.py:141-151`):
```python
def _resolve_engine(raw: dict) -> str:
    """PREVUE_ENGINE env > prevue.yml engine.name > DEFAULT."""
    env_engine = os.environ.get("PREVUE_ENGINE")
    if env_engine:
        return env_engine
    engine_block = raw.get("engine")
    if isinstance(engine_block, dict):
        name = engine_block.get("name")
        if name:
            return str(name)
    return DEFAULT_ENGINE
```
WKFL-05 (D-07): formalize this ladder for `model` (+ optionally fallback model) — only ~3 knobs need a caller override (RESEARCH §360). Do NOT build a generic resolver.

**New `EngineConfig` pydantic model** (mirror `FallbackConfig` :43-49 / `SkipConfig` :23-40 with `ConfigDict(extra="forbid")` + `@field_validator`): fields `name`, `model`, `models: {classify, review, consolidate}` (D-11), `raw_args: list[str]` (D-10), `pricing: dict` (D-06c). Add to `PrevueConfig` (:69-77). Loader slots into the single `yaml.safe_load` at `load_config` :164-186.

**Trust (SKIL-04):** raw_args + pricing are read through the existing base-ref-only `resolve_consumer_config_path` sentinel path (`config.py:80-126`, `NO_CONSUMER_CONFIG_SENTINEL` :20). Pitfall 4 — add a test that PR-head raw_args/pricing is ignored.

---

### `src/prevue/models.py` (MOD — versioned output)

**Analog:** self (`ReviewResult` :45-50). pydantic v2 `model_dump(mode="json")` gives the JSON for free; just add `schema_version: str = "1.0"` to the serialized OUTP-05 shape (D-09). `ReviewRequest.model` (:30) already carries per-call model — no change needed for ENGN-09 mechanism.

---

### `src/prevue/multicall.py` + `src/prevue/review.py` (MOD — per-role model)

**Analog:** self. Per-role model is "which model string is set on which `ReviewRequest`", not an adapter change (RESEARCH §374).

**review.py resolution site to extend** (`review.py:756`):
```python
_review_model = os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))
```
Resolve `models.review` here; classify call-sites use `models.classify` (classify already takes `model=` — `base.py:24`/`copilot_cli.py:95`). Consolidate slot resolves but is unused (D-13). `multicall.execute_calls` (:167-210) runs each request as-is — merge stays deterministic via `merge_findings` (:213+, fingerprint). Do NOT change the merge.

---

### `src/prevue/github/comments.py` (MOD — cost line in sticky)

**Analog:** self. The token render block (`comments.py:535-547`) already handles `review_estimated`/`classify_estimated` per-metric flags — the carrier anticipated PERF-03. Add a cost line beside `token_line` (:544), reading cost from `engine_meta["tokens"]` (extended by usage.py/pricing.py). Keep the `~est` labeling convention (:542-543).

---

### `.github/workflows/prevue-review.yml` (MOD — outputs + artifact)

**Analog:** self. The "Run review" step (`prevue-review.yml:117-128`) is where to add: a job-level `outputs:` map (compact: conclusion/counts/tokens/cost via `$GITHUB_OUTPUT`) and an `actions/upload-artifact` step for the full `prevue-result.json` (D-08, 1 MB job-output limit). New env: `COPILOT_OTEL_FILE_EXPORTER_PATH` for otel capture; Antigravity secret (`GEMINI_API_KEY`/`ANTIGRAVITY_API_KEY`) added to the secrets block (:30-36) + per-engine env (:126-128). Static test `test_reusable_workflow_yaml.py` must be extended.

---

## Shared Patterns

### Authentication / secret validation
**Source:** `src/prevue/engines/copilot_cli.py:50-61` (validator), `errors.py:6` (`AuthError` base), per-engine subclasses (`copilot_cli.py:43`, `cursor_cli.py:22`, `claude_code_cli.py:21`).
**Apply to:** `cli_adapter.py` via `spec.validate_secret` + `spec.auth_error`. **Preserve every `*AuthError` subclass** — tests `pytest.raises(AuthError)`/per-engine (Pitfall 5).

### Error handling / secret sanitization
**Source:** `src/prevue/engines/errors.py` (`AuthError`, `EngineFailure`, `sanitize_stderr`), threaded through `subprocess_invoke.invoke_subprocess_text(secret=...)`.
**Apply to:** generic adapter must keep passing `secret=` to `invoke_subprocess_text` (every current adapter does — `copilot_cli.py:74`, `cursor_cli.py:50`, `claude_code_cli.py:42`).

### Config validation (pydantic boundary)
**Source:** `src/prevue/config.py:23-49` (`SkipConfig`/`FallbackConfig`: `ConfigDict(extra="forbid")` + `@field_validator`).
**Apply to:** new `EngineConfig` and `CliEngineSpec`; emitted `ReviewResult` versioning.

### Precedence ladder
**Source:** `src/prevue/config.py:141-151` (`_resolve_engine`: env > yml > default).
**Apply to:** all WKFL-05 override knobs (engine, model, fallback model).

### Shared review/retry flow
**Source:** `src/prevue/engines/flow.py:64-163` (`review_with_retry`).
**Apply to:** the generic's `review()` — already the de-facto contract all 4 adapters call identically.

### Contract test parametrization
**Source:** `tests/test_engine_contract.py:22-49` (FUNCTIONAL list, AUTH_ENV map, fixtures).
**Apply to:** must stay green across the generic; extend params for antigravity; update `test_vendor_argv` (:117-142) and remove/replace `test_gemini_classify_raises_not_implemented` (:269-272).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/prevue/pricing/model_prices.json` | config (data) | — | Vendored LiteLLM snapshot — external data file, no in-repo precedent. Ship under `src/prevue/` so uv_build includes it in the wheel (verify A5). |
| `.github/workflows/update-pricing.yml` (NEW, D-06b) | config | scheduled | No scheduled-PR-bump workflow exists; closest structural reference is the existing reusable workflow YAML conventions in `.github/workflows/`. |
| `src/prevue/pricing.py` (compute) | utility | transform | No exact pure-cost-compute analog; `tokens.py` is the nearest pure-module pattern. Listed in assignments above with that caveat. |

## Metadata

**Analog search scope:** `src/prevue/engines/`, `src/prevue/{config,models,multicall,review}.py`, `src/prevue/github/comments.py`, `.github/workflows/`, `tests/`.
**Files scanned:** 14 source files + contract/registry/workflow tests read directly this session.
**Pattern extraction date:** 2026-06-28
