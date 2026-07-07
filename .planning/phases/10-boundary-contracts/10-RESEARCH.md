# Phase 10: Boundary Contracts - Research

**Researched:** 2026-06-28
**Domain:** Adapter-layer refactor (spec-driven generic) + config-precedence contract + real cross-CLI token/cost accounting + versioned machine-readable output. Pure Python framework; GitHub Actions reusable workflow.
**Confidence:** HIGH (codebase + config), MEDIUM (per-engine token reporting — varies sharply by CLI), LOW (Antigravity CLI token reporting — unconfirmed)

## Summary

This is a contract-locking phase, not a feature phase. The bulk of it is internal refactor with no behavior change: collapse four near-identical CLI adapters (`copilot_cli.py`, `cursor_cli.py`, `claude_code_cli.py`, `gemini_cli.py`) into one concrete `CliEngineAdapter` driven by a declarative `CliEngineSpec` (ENGN-10, lands FIRST per hard sequencing). The shared review/retry/subprocess machinery (`flow.review_with_retry`, `subprocess_invoke.invoke_subprocess_text`) already exists from Phase 5 — the per-adapter files are pure boilerplate shells that vary on ~4 axes (auth env + validator, argv, prompt delivery {stdin | tempfile-arg}, model-flag form {env | argv}, cwd, functional flag). Spec-as-data is the right call (D-01): adding a CLI engine becomes one data entry, the registry auto-populates by iterating the spec list, and `SKELETON_ENGINES` collapses to a `functional` field (D-03).

The hard part of this phase is **real per-engine token capture (PERF-03)** — and the research surfaces a critical, plan-shaping finding: **the four CLIs do NOT expose usage uniformly.** Claude Code's `--output-format json` returns `usage` + `total_cost_usd` per invocation on stdout (clean). Cursor's `--output-format json` returns a result envelope with **no token fields** (open feature request — must fall back to estimation). Copilot CLI prints **no usage to stdout at all** — it only emits OpenTelemetry JSONL to a log path (`COPILOT_OTEL_FILE_EXPORTER_PATH`), requiring a post-invocation file read. Antigravity (`agy`) has an **unstable `--output-format json` and a non-TTY stdout-dropping bug in CI** — token reporting cannot be confirmed and is a live risk. This means PERF-03 must be designed around per-spec capability variance with the `bytes/4` fallback (`tokens.py`) labeled honestly, exactly as D-04 anticipates. The `estimated` flag in `engine_meta["tokens"]` is already the carrier for this.

The remaining requirements are small, well-scoped contract additions made **once** against the generic: raw-args passthrough (ENGN-08, base-ref-only list-form, D-10), per-role model tiering (ENGN-09, reserve consolidate slot only, D-11/D-13), declared config precedence (WKFL-05, formalize-existing-per-field, D-07), and versioned machine-readable output (OUTP-05, compact job output + full JSON artifact, D-08/D-09). The GitHub Actions 1 MB job-output limit confirms the both-form output design.

**Primary recommendation:** Land ENGN-10 (spec-driven `CliEngineAdapter` + `CliEngineSpec` + auto-populated registry) as the first wave, preserving the existing parametrized contract suite and per-engine `AuthError` subclasses unchanged. Then add PERF-03/ENGN-08/ENGN-09 as per-spec capability fields once against the generic. Design PERF-03 around a per-engine `usage_capture` strategy (stdout-json | otel-jsonl | none→estimate), compute cost from a **vendored LiteLLM `model_prices_and_context_window.json` snapshot** (no runtime fetch, D-06a). Replace the Gemini skeleton with an Antigravity spec marked `functional` but flag its token-reporting and non-TTY stdout risk for a `checkpoint:human-verify` live test.

## Project Constraints (from CLAUDE.md)

- **Language/runtime:** Python 3.12 floor, run on 3.13; matches `ubuntu-latest`. No new runtime deps without legitimacy check.
- **Stack is locked:** pydantic 2.13.x (v2 API only, `ConfigDict(extra="forbid")` pattern), PyYAML 6.0.x (single `yaml.safe_load`), uv + `uv sync --locked`, ruff 0.15.x (`E,F,I,UP`, line-length 100, py312 target), pytest 9.x + responses 0.26.x.
- **Delivery is fixed:** GitHub reusable workflow (`workflow_call`), minimal token scopes, explicit named-secret pass-through. Do not weaken the permissions/trust boundary.
- **Trust posture (SKIL-04 fail-closed):** consumer config read ONLY from trusted base-ref via `resolve_consumer_config_path` sentinel fallback. **raw_args (D-10) and pricing override (D-06c) MUST inherit this — never read from PR-head, no runtime pricing fetch.**
- **No agent frameworks:** engine adapter is a subprocess call + prompt assembly. Keep it pydantic models + `subprocess`.
- **Adapters stay sync** (PyGithub is sync); don't introduce asyncio. Multi-call concurrency already uses `ThreadPoolExecutor`.
- **No `--allow-tool` flags in any adapter** (enforced by `test_adapter_cli_commands_contain_no_allow_tool_flags`). The spec-driven generic must keep this true — the static scan greps all `src/prevue/engines/*.py`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**ENGN-10 — Adapter consolidation (lands FIRST)**
- **D-01:** Spec-driven generic adapter, not template-method. One concrete `CliEngineAdapter` implements `review`/`classify`/`classify_skills` once; each engine is a declarative `CliEngineSpec` (secret env + validator, argv, prompt delivery `{stdin | tempfile-arg}`, model flag `{env | argv}`, cwd, functional bool). Registry **auto-populates** by iterating the spec list — adding a CLI engine = ~1 data entry, no duplicated methods, no manual registry import+dict edit.
- **D-02:** Keep `EngineAdapter` ABC as the **top boundary**. `CliEngineAdapter(spec)` is the CLI-family-only generic. A future `ApiEngineAdapter` is a **sibling**, NOT forced through `CliEngineSpec`. Registry holds both kinds uniformly. Do NOT build Bedrock/Vertex/Azure this phase — just don't block them.
- **D-03:** Drop the `SKELETON_ENGINES` special-case; `functional` becomes a spec field.

**PERF-03 — Real token accounting + cost**
- **D-04:** Capture **real input/output/cache tokens for all engines**; estimation is NOT the primary path. `bytes/4` (`tokens.py`) demoted to a **labeled fallback** used only when an engine genuinely cannot report usage.
- **D-05:** **Surface dollar cost now.** Compute estimated cost per review from a pricing table; add a cost line to the OUTP-04 sticky summary.
- **D-06:** Pricing source of truth = LiteLLM's `model_prices_and_context_window.json`.
  - **D-06a:** Vendor a **pinned snapshot** in-repo. NO runtime fetch during a review (SKIL-04 trust).
  - **D-06b:** **Auto-update via a scheduled CI workflow** that pulls latest LiteLLM JSON and opens a PR to bump the pinned snapshot.
  - **D-06c:** **Consumer override:** an `engine.pricing` map in `prevue.yml` takes precedence over the bundled snapshot.

**WKFL-05 — Config precedence**
- **D-07:** Declared order is **workflow input > `.github/prevue.yml` > built-in defaults**. Declare + test the order. (Mechanism is Claude discretion — see below.)

**OUTP-05 — Machine-readable output**
- **D-08:** Emit **both** forms: a **compact job output** (conclusion, severity counts, tokens, cost) AND the **full `ReviewResult` JSON as a build artifact**. Both-form sidesteps Actions job-output size limits.
- **D-09:** Emitted JSON is a **versioned contract**: include `schema_version` (start `"1.0"`) + documented field shape. Applies to both compact output and full artifact.

**ENGN-08 — Raw-args passthrough**
- **D-10:** `engine.raw_args: [...]` read **only from the trusted base-ref `prevue.yml`** (never PR-head). **List form** (no shell string), appended after the framework's argv.

**ENGN-09 — Per-role model tiering**
- **D-11:** Add per-role model concept (cheap classify / strong review / cheap consolidate) + a single-model fallback. (Config shape is Claude discretion — see below.)
- **D-13 (consolidate-role scope):** **Reserve the role wiring only** this phase — the consolidate role + model slot must *resolve* in config/contract, but multicall merge stays **deterministic (fingerprint)**. The actual LLM consolidate/dedup pass lands in **Phase 13 (QUAL-01)**.

**Engine roster**
- **D-12:** **Gemini CLI is replaced by Antigravity CLI.** Make this engine a **functional** spec now, targeting Google's Antigravity CLI (`agy`), not the old `gemini` binary. Researcher MUST verify Antigravity specifics (done below — see Open Questions / risk).

### Claude's Discretion

- **WKFL-05 mechanism (D-07):** Leaning formalize-existing per-field reads + a precedence **test matrix** for the knobs that actually have an input override (engine, model, fallback enable/model), rather than a generic layered resolver. Planner confirms by counting how many knobs realistically need a caller-side override. (Research finding below: **only ~3 knobs** realistically need it → formalize-existing wins.)
- **ENGN-09 config shape (D-11):** Leaning a per-role `engine.models: { classify, review, consolidate }` block with a single `model:` fallback for any unset role; adapter selects per call-site by role. Planner confirms against the spec-driven adapter + multicall wiring for least churn.

### Deferred Ideas (OUT OF SCOPE)

- **LLM consolidate/dedup pass** → Phase 13 (QUAL-01). Phase 10 only reserves the role wiring (D-13).
- **API engines (Bedrock / Vertex / Azure)** — `ApiEngineAdapter` sibling left *possible* by D-02 but **not built**. Future research target: litellm as provider-unification layer + pr-agent's no-engine-field ergonomic (provider from model-string prefix + `*_API_KEY`). NO API/litellm-router code this phase.
- **Generic layered config resolver** — only if planner finds enough knobs justify it (D-07); otherwise deferred indefinitely.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENGN-10 | Consolidate 4 CLI adapters into spec-driven generic `CliEngineAdapter` + `CliEngineSpec`; auto-populated registry; `functional` flag drops `SKELETON_ENGINES`. **Lands FIRST.** | Adapter-anatomy table below maps the exact varying axes across all 4 adapters; contract-suite-preservation list documents which assertions must stay green; shared-flow reuse confirmed (`flow.review_with_retry`, `subprocess_invoke`). |
| WKFL-05 | Declared + tested config precedence: input > prevue.yml > defaults. | Override-knob inventory below (3 knobs realistically need input override) → formalize-existing pattern from `_resolve_engine` (config.py:141) generalized + a precedence test matrix. |
| PERF-03 | Real input/output/cache tokens per engine; bytes/4 = labeled fallback; cost from pricing DB. | Per-engine usage-capability matrix (the central finding): Claude=stdout-json, Cursor=none, Copilot=otel-jsonl, Antigravity=unconfirmed. LiteLLM JSON field structure + cost formula documented. `engine_meta["tokens"]` shape extension path mapped. |
| ENGN-08 | Raw-args passthrough escape hatch, no typed-input change. | List-form `engine.raw_args` slot in `CliEngineSpec` argv assembly; SKIL-04 base-ref-only read confirmed via existing `resolve_consumer_config_path`. |
| ENGN-09 | Per-role model tiering (classify/review/consolidate) + single-model fallback. | `engine.models` config shape vs existing single-read loader + multicall per-call model wiring (review.py model resolution sites mapped); consolidate slot reserved, merge stays deterministic. |
| OUTP-05 | `ReviewResult` as versioned job output + JSON artifact. | GitHub Actions 1 MB job-output limit verified (drives both-form); `schema_version` field; `ReviewResult.model_dump()` already serializable via pydantic v2. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Adapter consolidation (ENGN-10) | Engine adapter layer (`src/prevue/engines/`) | — | Pure internal port refactor; nothing else moves. The ABC boundary (`base.py`) stays; only the concrete CLI implementations collapse. |
| Real token capture (PERF-03) | Engine adapter layer (per-spec capture) | Output/render (`github/comments.py`) | Capture belongs in the adapter (only it sees the CLI's stdout/log); rendering belongs in the sticky summary. `flow.py` token-meta is the seam between them. |
| Cost computation (PERF-03) | Pure compute module (new `pricing.py` reading vendored JSON) | Config (`engine.pricing` override) | Cost is a deterministic function of (engine, model, usage) × pricing table; no I/O, testable in isolation. Config supplies the override map. |
| Config precedence (WKFL-05) | Config layer (`config.py`) | — | Precedence is owned by `load_config` / `_resolve_engine`; this phase declares + tests, generalizes the existing one-knob pattern. |
| Raw-args passthrough (ENGN-08) | Config layer (read) + adapter (apply) | — | Config reads the base-ref-only list; the spec's argv builder appends it. Two-tier: read trust in config, application in adapter. |
| Per-role model tiering (ENGN-09) | Config layer (`engine.models`) + orchestration (`review.py`/`multicall.py` per-call-site resolution) | Adapter (`model` already on `ReviewRequest`) | Role→model resolution is an orchestration concern (which model for classify vs review); the adapter already accepts `model` per request — no adapter change needed for the mechanism. |
| Machine-readable output (OUTP-05) | Orchestration (`review.py` emit) + workflow YAML (job output + artifact upload) | Models (`schema_version` on serialized shape) | The Python side writes `$GITHUB_OUTPUT` + a JSON file; the workflow declares the `outputs:` and the `upload-artifact` step. |

## Standard Stack

This phase adds **zero new runtime Python packages.** The pricing data is vendored as a JSON file (data, not a dependency). The LiteLLM *package* is NOT installed — only its public `model_prices_and_context_window.json` snapshot is committed.

### Core (existing, unchanged — already locked in CLAUDE.md)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.13.* | `CliEngineSpec`, `ReviewResult` serialization, new config models | Already the boundary-validation standard for this repo. `model_dump(mode="json")` gives the OUTP-05 JSON for free. `[VERIFIED: pyproject.toml]` |
| PyYAML | 6.0.* | Parse new `engine.raw_args`, `engine.models`, `engine.pricing` blocks | Single `yaml.safe_load` already in `load_config`; new blocks slot in. `[VERIFIED: pyproject.toml]` |
| Python stdlib `json` | 3.12 | Read vendored pricing JSON; parse Claude/Cursor `--output-format json`; emit OUTP-05 | No dep needed. `[VERIFIED: codebase]` |
| Python stdlib `subprocess` | 3.12 | Already the adapter invocation primitive (`subprocess_invoke.py`) | `[VERIFIED: codebase]` |

### Supporting (existing test tooling, unchanged)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.* | Contract suite, precedence matrix, pricing/cost unit tests | All new tests. `[VERIFIED: pyproject.toml]` |
| responses | 0.26.* | Mock GitHub REST in `test_review_flow` | Unchanged; no new API calls in this phase. `[VERIFIED: pyproject.toml]` |
| ruff | 0.15.* | Lint/format gate (CI) | `scripts/ci-local.sh` must pass before push (project memory). `[VERIFIED: pyproject.toml]` |

### Vendored data (NOT a package)
| Artifact | Source | Purpose |
|----------|--------|---------|
| `model_prices_and_context_window.json` (pinned snapshot) | `BerriAI/litellm` raw GitHub | Pricing source of truth (D-06/D-06a). ~500+ KB, 300+ model entries. Commit a pinned copy; never fetch at review time. `[CITED: raw.githubusercontent.com/BerriAI/litellm]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vendored LiteLLM JSON snapshot | `pip install litellm` + `litellm.model_cost` | Rejected: massive dep surface (CLAUDE.md "no agent frameworks" spirit), and a runtime import path is harder to pin for trust. Vendoring one JSON is the tokscale-proven approach and keeps SKIL-04 posture. |
| Spec-driven generic (D-01, locked) | Template-method base class | D-01 locks spec-driven. Template-method is the documented low-risk fallback in ENGN-10 if spec-as-data hits an unforeseen wall — but it costs more per future engine. Don't switch without cause. |
| Compact job output only | Full `ReviewResult` in job output | Rejected: 1 MB job-output limit (verified) — a large review's full findings JSON can exceed it. Hence D-08 both-form. |

**Installation:** No `uv add` needed for runtime. The pricing JSON is committed under `src/prevue/` (e.g. `src/prevue/pricing/model_prices.json`) so it ships in the wheel.

**Version verification:** All existing packages already pinned and verified in `pyproject.toml` (read this session). No new package to verify.

## Package Legitimacy Audit

> This phase installs **no new external packages.** The only external artifact is a vendored JSON data file from a well-known repo.

| Package / Artifact | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|--------------------|----------|-----|-----------|-------------|---------|-------------|
| (none — no new pip packages) | — | — | — | — | — | — |
| `model_prices_and_context_window.json` (data, not a package) | n/a (raw file) | mature | n/a | github.com/BerriAI/litellm (24k+ stars, the de-facto LLM-pricing DB; tokscale uses it) | OK (data file, reviewed-on-bump per D-06b) | Vendored, pinned |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Note: `litellm` the npm/PyPI package is NOT installed. Only its public pricing JSON is vendored. The D-06b auto-update workflow opens a PR to bump the pinned snapshot, keeping every change human-reviewed (trust-safe).*

## Architecture Patterns

### System Architecture Diagram

```
                          .github/prevue.yml (BASE REF ONLY — SKIL-04)
                                   │
                                   ▼
                     ┌─────────────────────────────┐
   workflow input ──►│  config.load_config          │  WKFL-05 precedence:
   (PREVUE_ENGINE,   │  + _resolve_* (per-field)    │  input > yml > defaults
    PREVUE_MODEL)    │  engine.raw_args (D-10)      │
                     │  engine.models  (D-11)       │
                     │  engine.pricing (D-06c)      │
                     └──────────────┬──────────────┘
                                    │ PrevueConfig (typed)
                                    ▼
                     ┌─────────────────────────────┐
                     │  registry (auto-populated    │  ENGN-10:
                     │  from CLI_ENGINE_SPECS list) │  iterate specs → register
                     └──────────────┬──────────────┘
                                    │ CliEngineAdapter(spec) | ApiEngineAdapter (future sibling)
                                    ▼
   ReviewRequest ───►┌─────────────────────────────┐
   (per-call,        │  CliEngineAdapter.review     │  ONE impl for all CLIs.
    model per role   │   ├ build env (spec.secret)  │  Per-role model from
    via ENGN-09)     │   ├ argv = spec.argv         │  ReviewRequest.model.
                     │   │   + model flag (env|argv)│
                     │   │   + raw_args (appended)  │  ENGN-08
                     │   ├ prompt (stdin|tempfile)  │  spec.prompt_delivery
                     │   └ flow.review_with_retry ──┼──► subprocess_invoke
                     └──────────────┬──────────────┘
                                    │ stdout (+ maybe OTEL JSONL log)
                                    ▼
                     ┌─────────────────────────────┐
                     │  usage capture (per spec)    │  PERF-03 (the variance):
                     │   stdout-json | otel-jsonl   │   Claude=stdout-json
                     │   | none → bytes/4 fallback  │   Cursor=none(estimate)
                     │   → engine_meta["tokens"]    │   Copilot=otel-jsonl
                     │     {input,output,cache,     │   Antigravity=??? (risk)
                     │      estimated:bool}         │
                     └──────────────┬──────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │  pricing.compute_cost        │  reads vendored JSON
                     │  (engine,model,usage)→$      │  + engine.pricing override
                     └──────────────┬──────────────┘
                                    ▼
        ┌──────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
┌─────────────────────┐                          ┌──────────────────────────┐
│ sticky summary       │ OUTP-04+cost (D-05)      │ OUTP-05 emit:            │
│ (github/comments.py) │                          │  ① $GITHUB_OUTPUT compact│
│  Tokens + Cost line  │                          │     (conclusion,counts,  │
└─────────────────────┘                          │      tokens,cost)        │
                                                  │  ② full ReviewResult.json│
                                                  │     artifact (schema_ver)│
                                                  └──────────────────────────┘
```

### Recommended Project Structure (deltas only)
```
src/prevue/engines/
├── base.py              # EngineAdapter ABC — UNCHANGED (top boundary, D-02)
├── spec.py              # NEW: CliEngineSpec (pydantic), CLI_ENGINE_SPECS list
├── cli_adapter.py       # NEW: CliEngineAdapter(spec) — the one generic impl
├── registry.py          # CHANGED: auto-populate from CLI_ENGINE_SPECS; drop SKELETON_ENGINES
├── flow.py              # CHANGED: token-meta carries real usage when available
├── subprocess_invoke.py # CHANGED (maybe): return (stdout, otel_log_path?) for capture
├── tokens.py            # UNCHANGED logic; now explicitly the labeled fallback
├── usage.py             # NEW: per-strategy usage parsers (stdout-json | otel-jsonl)
├── copilot_cli.py       # SLIMMED → spec entry + CopilotAuthError kept (test compat)
├── cursor_cli.py        # SLIMMED → spec entry + CursorAuthError kept
├── claude_code_cli.py   # SLIMMED → spec entry + ClaudeAuthError kept
├── gemini_cli.py        # REPLACED → antigravity spec (functional=True), AntigravityAuthError
src/prevue/
├── pricing/
│   └── model_prices.json # NEW: vendored LiteLLM snapshot (D-06a)
├── pricing.py           # NEW: compute_cost(engine, model, usage, override) — pure
├── config.py            # CHANGED: EngineConfig model (raw_args, models, pricing); precedence
├── models.py            # CHANGED: schema_version on serialized output (OUTP-05/D-09)
.github/workflows/
├── prevue-review.yml    # CHANGED: add outputs: + upload-artifact step (OUTP-05)
└── update-pricing.yml   # NEW: scheduled LiteLLM JSON bump → PR (D-06b)
```

### Pattern 1: Spec-driven generic adapter (ENGN-10, D-01)
**What:** A single `CliEngineAdapter` whose behavior is parameterized by an immutable `CliEngineSpec`. The registry is built by mapping over a module-level list of specs.
**When to use:** The CLI family. API engines get a separate `ApiEngineAdapter` sibling (D-02).
**Example (shape — derived from the 4 existing adapters, not copied from external docs):**
```python
# src/prevue/engines/spec.py
from typing import Literal, Callable
from pydantic import BaseModel, ConfigDict

class CliEngineSpec(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    name: str
    secret_env: str                       # "COPILOT_GITHUB_TOKEN" | "ANTHROPIC_API_KEY" | ...
    auth_error: type                       # CopilotAuthError | ClaudeAuthError | ...  (test compat)
    validate_secret: Callable[[str], str]  # returns secret or raises auth_error
    base_argv: tuple[str, ...]             # ("copilot","-s","--no-ask-user") | ("claude","--bare",...)
    prompt_delivery: Literal["stdin", "tempfile-arg"]
    tempfile_flag: str | None = None       # "-f" for cursor
    model_flag: Literal["env", "argv", "none"]
    model_env: str | None = None           # "COPILOT_MODEL"
    model_argv_flag: str | None = None     # "--model" | "-m"
    cli_label: str
    use_consumer_cwd: bool = False         # cursor uses PREVUE_CONSUMER_ROOT
    usage_capture: Literal["stdout-json", "otel-jsonl", "none"] = "none"  # PERF-03
    functional: bool = True                # D-03 (antigravity True, replaces skeleton)
```
> **Caveat (from ENGN-10 spec):** preserve per-engine `AuthError` subclasses (tests assert on `type`), repoint `copilot_cli.__all__` re-exports that tests rely on, and note `classify_skills` becomes available to every engine for free.

### Pattern 2: Per-engine usage capture strategy (PERF-03, the central finding)
**What:** A `usage_capture` field on the spec selects how real tokens are obtained; the generic dispatches to a parser; all roads end in `engine_meta["tokens"]` with an honest `estimated` flag.
**When to use:** Every adapter, but the strategy differs per CLI (see matrix).
**Example (shape):**
```python
# src/prevue/engines/usage.py
def capture_usage(spec, stdout, otel_path=None):
    if spec.usage_capture == "stdout-json":
        obj = json.loads(stdout)                  # Claude Code: usage + total_cost_usd
        u = obj.get("usage", {})
        return {"input": u.get("input_tokens",0), "output": u.get("output_tokens",0),
                "cache_read": u.get("cache_read_input_tokens",0),
                "cost_usd": obj.get("total_cost_usd"), "estimated": False}
    if spec.usage_capture == "otel-jsonl":
        return _parse_copilot_otel(otel_path)     # read COPILOT_OTEL_FILE_EXPORTER_PATH lines
    return None                                    # caller falls back to bytes/4 (estimated=True)
```
> Note: when `usage_capture == "stdout-json"`, the diff/findings text the engine returns is now wrapped in a JSON envelope — `extract_json_fence` in `flow.py` consumes the `result` field, not raw stdout. This is a behavior-touching change to the parse path; cover it explicitly in tests.

### Pattern 3: Formalize-existing config precedence (WKFL-05, D-07)
**What:** Generalize the existing `_resolve_engine` pattern (env/input > yml.engine.name > default) into a documented, tested ladder for exactly the knobs that have a caller override.
**When to use:** WKFL-05. Do NOT build a generic layered resolver — the override-knob inventory shows it doesn't earn its cost.
**Example:** mirror `config.py:141` per knob; add a `tests/test_config_precedence.py` matrix asserting each of the 3 override-able knobs resolves input > yml > default.

### Pattern 4: Versioned both-form output (OUTP-05, D-08/D-09)
**What:** Write a compact summary to `$GITHUB_OUTPUT` (well under 1 MB) and the full `ReviewResult` (with `schema_version`) to a JSON file uploaded as an artifact.
**Example:**
```python
compact = {"schema_version": "1.0", "conclusion": gate.conclusion,
           "error_count": n_err, "warning_count": n_warn, "info_count": n_info,
           "tokens": total, "cost_usd": cost}
# write each as key=value to $GITHUB_OUTPUT (escape newlines / use heredoc syntax)
full = {"schema_version": "1.0", **result.model_dump(mode="json")}
Path("prevue-result.json").write_text(json.dumps(full))
```

### Anti-Patterns to Avoid
- **Per-engine subclasses for the new contract features.** That's the 4× cost ENGN-10 exists to kill. Add raw_args/models/usage_capture as spec fields, once.
- **Treating all CLIs as if they report usage on stdout.** They don't (see matrix). A uniform stdout-json assumption silently produces zeros for Cursor/Copilot/Antigravity.
- **Runtime pricing fetch.** Violates SKIL-04 (D-06a). Vendor + scheduled-PR bump only.
- **Reading `engine.raw_args` / `engine.pricing` from PR-head config.** A malicious PR could inject CLI flags into its own review or fake pricing. Must go through `resolve_consumer_config_path` base-ref-only path.
- **Putting the full `ReviewResult` in `$GITHUB_OUTPUT`.** 1 MB limit; large reviews overflow. Artifact for the full form.
- **Shell-string raw_args.** D-10 mandates list form — no shell parsing, no injection surface.
- **Building the LLM consolidate pass.** D-13: reserve the role slot only; merge stays fingerprint-deterministic. Behavior change is Phase 13.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM model pricing table | A hand-curated price map | Vendored LiteLLM `model_prices_and_context_window.json` (D-06) | 300+ models, cache + tiered pricing, community-maintained; tokscale-proven. Hand-curation rots instantly. |
| Token counting / tokenization | A tokenizer (tiktoken etc.) | Engine's own reported usage; `bytes/4` only as labeled fallback | D-04: real counts beat any local tokenizer; you can't tokenize for an opaque CLI's model anyway. tokscale's whole thesis: "no tokenization, no estimation." |
| Config precedence resolver | A generic layered-config engine | Formalize existing per-field reads (D-07) | Only ~3 knobs need a caller override (inventory below). A generic resolver is over-engineering here. |
| JSON serialization of `ReviewResult` | Manual dict assembly | `result.model_dump(mode="json")` | pydantic v2 already produces stable JSON; just add `schema_version`. |
| Spec/registry wiring | Manual `ENGINES` dict edits per engine | Auto-populate from `CLI_ENGINE_SPECS` (D-01) | That manual edit is exactly the per-engine cost ENGN-10 removes. |

**Key insight:** Almost everything in this phase is *removing* hand-rolled per-engine code and *pinning* an external data source, not writing new logic. The genuinely new code is small: one generic adapter, per-strategy usage parsers, a pure cost function.

## Adapter Anatomy — Axes That Vary (drives `CliEngineSpec` fields)

> This table is the ground truth from reading all four adapters this session. It is the input the planner needs to define `CliEngineSpec`.

| Axis | copilot-cli | claude-code-cli | cursor-cli | antigravity (was gemini) |
|------|-------------|-----------------|------------|--------------------------|
| Secret env | `COPILOT_GITHUB_TOKEN` (must start `github_pat_`) | `ANTHROPIC_API_KEY` | `CURSOR_API_KEY` | `GEMINI_API_KEY` or `ANTIGRAVITY_API_KEY` `[CITED: antigravitylab.net]` |
| AuthError subclass | `CopilotAuthError` | `ClaudeAuthError` | `CursorAuthError` | `AntigravityAuthError` (new) |
| Base argv | `["copilot","-s","--no-ask-user"]` | `["claude","--bare","-p","--output-format","text"]` | `["cursor-agent","-p","--output-format","text","-f",<tmp>]` | `["agy","-p", ...]` (see risk) `[CITED: antigravity docs]` |
| Prompt delivery | stdin (`input_text`) | stdin (`input_text`) | tempfile-arg (`-f <path>`) | argv (prompt as `-p` value) — **stdin not supported** `[CITED: antigravitylab.net]` |
| Model flag form | env (`COPILOT_MODEL`) | argv (`--model <m>`) | argv (`-m <m>`) | argv (`--model <m>`, since v1.0.5) `[CITED: search]` |
| cwd | none | none | consumer root (`PREVUE_CONSUMER_ROOT`) | TBD (likely none) |
| Usage capture (PERF-03) | **otel-jsonl** (no stdout usage) | **stdout-json** (`usage` + `total_cost_usd`) | **none** (no token fields in JSON → estimate) | **unconfirmed → estimate fallback** (risk) |
| functional | true | true | true | true (D-12; replaces skeleton) |

## Per-Engine Token Reporting Matrix (PERF-03 — the central design constraint)

| Engine | How to request usage | Where usage appears | Fields available | Strategy | Confidence |
|--------|---------------------|---------------------|------------------|----------|------------|
| **Claude Code** | `claude --bare -p --output-format json` | stdout JSON envelope | `usage` (input/output/cache_read/cache_creation tokens), `total_cost_usd`, per-model breakdown, `result` text | `stdout-json` — real tokens **and** real cost directly. **Best case.** | HIGH `[CITED: code.claude.com/docs/headless]` |
| **Cursor** | `cursor-agent -p --output-format json` | stdout JSON | `type, subtype, is_error, duration_ms, result, session_id` — **NO token fields** (open feature request) | `none` → `bytes/4` fallback, `estimated:true` | HIGH `[CITED: cursor.com/docs, forum.cursor.com]` |
| **Copilot CLI** | enable OTEL export before invocation (`COPILOT_OTEL_FILE_EXPORTER_PATH`) | OpenTelemetry JSONL log file (`~/.copilot/otel/*.jsonl`), **not stdout** | per-call input/output/cache-read/cache-creation/reasoning tokens, model, provider | `otel-jsonl` — set env, run, then read+sum the JSONL the run produced | MEDIUM `[CITED: ccusage.com/guide/copilot]` |
| **Antigravity (`agy`)** | `agy -p "..." --output-format json` is **reported rejected/unstable**; also a **non-TTY stdout-dropping bug** in CI | unconfirmed | unconfirmed | `none` → `bytes/4` fallback, `estimated:true`; flag for live verify | LOW `[CITED: antigravitylab.net]` |

**Plan implication:** PERF-03 cannot deliver real tokens for *all* engines this phase. It delivers real tokens for Claude Code (and cost), real tokens for Copilot via OTEL (with the extra env+log-read plumbing), and honest labeled estimates for Cursor and Antigravity. The `estimated` flag (already in the data shape) must be set per-engine, not globally. The OUTP-04 cost line should show real cost where available (Claude's `total_cost_usd` or computed from real tokens) and an estimate label otherwise.

## Cost Computation (PERF-03, D-05/D-06)

**Pricing source:** vendored `model_prices_and_context_window.json` (flat object keyed by model id). Relevant fields per entry:
- `input_cost_per_token`, `output_cost_per_token` (dollars per token, e.g. `5e-06`)
- `cache_read_input_token_cost`, `cache_creation_input_token_cost` (cache discounts)
- tiered: `input_cost_per_token_above_200k_tokens`, `output_cost_per_token_above_200k_tokens`
- `litellm_provider`, `max_input_tokens`, `mode`

**Formula (cache-aware):**
```
cost = input_tokens          * input_cost_per_token
     + output_tokens         * output_cost_per_token
     + cache_read_tokens     * cache_read_input_token_cost      (when present)
     + cache_creation_tokens * cache_creation_input_token_cost  (when present)
```
**Model→row mapping:** match the model string the adapter ran (e.g. `sonnet`, `gemini-3.5-flash`) to a JSON key. Names may not match 1:1 across CLIs — plan an alias/normalization map (CONTEXT D-06c `engine.pricing` override is the escape hatch for missing/renamed models). When Claude already returns `total_cost_usd`, prefer it over recomputation (it's authoritative for that vendor).

**Trust (D-06a):** the JSON is read from the bundled wheel path, never fetched. The D-06b workflow (`update-pricing.yml`, scheduled) curls the latest JSON and opens a PR — the only place the network touches pricing, and it's human-reviewed.

## Config Override-Knob Inventory (WKFL-05 D-07 decision input)

> The planner must decide formalize-existing vs generic resolver by counting knobs that realistically need a caller-side `with:` / env override. Here is the count from reading `config.py` + `prevue-review.yml`.

| Knob | Has input override today? | Realistically caller-overridable? |
|------|---------------------------|-----------------------------------|
| `engine` | YES (`PREVUE_ENGINE` env, workflow input `engine`) | YES — engine choice is per-caller |
| `model` (review) | partial (`PREVUE_MODEL` / `COPILOT_MODEL` env read in review.py) | YES — model is per-caller |
| `classification.fallback.enabled` / `.model` | NO (yml only) | Marginal — usually set once in yml |
| `engine.models` (new, D-11) | NO | Marginal — policy set in yml; env override for one role is niche |
| `skip.*`, `skills.*`, `review.*` (thresholds, budgets) | NO (yml only) | NO — these are repo policy, set once in prevue.yml |

**Finding:** only **engine** and **model** genuinely need a caller override today; fallback model is a possible third. Everything else is set-once policy in `prevue.yml`. This **supports the formalize-existing leaning** (D-07): document the input>yml>default ladder, generalize the `_resolve_engine` pattern for engine + model (+ optionally fallback model), and add a precedence test matrix. A generic per-knob `PREVUE_*` resolver does not earn its complexity. (Confidence: HIGH — grounded in the actual config surface.)

## ENGN-09 Config Shape (D-11 decision input)

Existing wiring (read this session):
- `ReviewRequest.model: str | None` already exists (`models.py:30`) — the adapter already selects a model per call.
- `review.py` resolves a single review model from `PREVUE_MODEL`/`COPILOT_MODEL` (lines 756, 870) and passes it to every per-call `ReviewRequest` (line 980).
- `classify` already takes a `model=` kwarg (`base.py`, all adapters); `FallbackConfig.model` (config.py:49) feeds classification's model (review.py:581).
- `multicall.execute_calls` runs each `ReviewRequest` (which carries its own `model`) — so per-role model is a matter of **which model string is set on which request at the call site**, not an adapter change.

**Recommended shape (confirms the D-11 leaning):** add an `EngineConfig` block:
```yaml
engine:
  name: copilot-cli
  model: gpt-5            # single fallback for any unset role
  models:
    classify: gpt-5-mini  # cheap
    review: gpt-5         # strong
    consolidate: gpt-5-mini  # RESERVED (D-13) — resolves but unused until Phase 13
  raw_args: ["--some-flag", "value"]   # ENGN-08, base-ref-only, list form
  pricing: { "gpt-5": { input_cost_per_token: 1.25e-06, output_cost_per_token: 1e-05 } }  # D-06c override
```
Resolution: `models.<role>` if set, else `model`, else engine default. Classify call-site uses `models.classify`; review call-sites use `models.review`; the consolidate slot resolves but nothing consumes it this phase (D-13). **Least churn**: the loader gains one `EngineConfig` model; review.py/multicall.py read `models.review`/`models.classify` at existing model-resolution sites. (Confidence: HIGH — grounded in existing wiring.)

## Common Pitfalls

### Pitfall 1: Assuming uniform stdout token reporting
**What goes wrong:** PERF-03 captures real tokens for Claude but silently records 0 (or crashes on `json.loads`) for Copilot/Cursor/Antigravity.
**Why it happens:** Only Claude Code returns usage on stdout JSON. Copilot uses OTEL files; Cursor omits tokens entirely; Antigravity's JSON mode is broken.
**How to avoid:** Per-spec `usage_capture` strategy; default to the labeled `bytes/4` fallback; set `estimated` per engine.
**Warning signs:** Cost line shows $0.00 or "0 tokens" for a non-Claude engine; `json.loads` fails on Copilot/Cursor plain output.

### Pitfall 2: Antigravity non-TTY stdout drop in CI
**What goes wrong:** `agy -p` returns empty/truncated stdout when run under GitHub Actions (non-TTY), so the review silently degrades.
**Why it happens:** `agy` checks `isatty` at startup and drops the final response under non-TTY in the current version.
**How to avoid:** Wrap in a pseudo-TTY: `script -qec 'agy -p "..."' /dev/null`, then strip ANSI (`sed -r 's/\x1B\[[0-9;]*[A-Za-z]//g' | tr -d '\r'`). This is engine-specific shell plumbing — encode it in the Antigravity spec/invocation, and **gate the Antigravity engine behind a `checkpoint:human-verify` live test** before declaring it functional in production. `[CITED: antigravitylab.net]`
**Warning signs:** Antigravity reviews return "empty output" `EngineFailure` despite a successful exit code.

### Pitfall 3: Breaking the parse path when switching Claude to JSON output
**What goes wrong:** `flow.extract_json_fence` operates on raw stdout; with `--output-format json` the review text moves into `result`/`structured_output`, so fence extraction fails and every Claude review degrades.
**Why it happens:** PERF-03's stdout-json capture changes what stdout *is* for that engine.
**How to avoid:** For `usage_capture == "stdout-json"`, parse the envelope first, extract `result`, then run fence extraction on that. Add a contract test for the Claude-JSON path.
**Warning signs:** Claude reviews suddenly all `degraded:true` with `parse_error`.

### Pitfall 4: PR-head config poisoning raw_args / pricing
**What goes wrong:** A malicious PR edits `prevue.yml` to inject CLI flags (raw_args) or fake low pricing, and the review reads the PR-head copy.
**Why it happens:** Forgetting that new `engine.*` knobs must go through the base-ref-only resolver.
**How to avoid:** All new config reads use the existing `resolve_consumer_config_path` sentinel path (SKIL-04). Add a test asserting raw_args/pricing are ignored when only PR-head differs.
**Warning signs:** raw_args take effect from a PR that modified prevue.yml; pricing changes appear from PR-head.

### Pitfall 5: Losing per-engine AuthError types or `__all__` re-exports during consolidation
**What goes wrong:** Tests assert `pytest.raises(CopilotAuthError)` / import names from `copilot_cli.__all__`; collapsing files into the generic breaks them.
**Why it happens:** The generic raises one error type unless the spec carries the subclass.
**How to avoid:** Keep each `*AuthError` subclass defined (in the slimmed per-engine module or a shared errors module) and reference it via `spec.auth_error`. Repoint `copilot_cli.__all__`. (Explicit ENGN-10 migration caveat.)
**Warning signs:** `test_copilot_adapter.py` / `test_engine_contract.py` import or `raises` failures.

### Pitfall 6: Job-output overflow on large reviews (OUTP-05)
**What goes wrong:** Emitting the full findings JSON to `$GITHUB_OUTPUT` exceeds the 1 MB job-output limit and the workflow errors/truncates.
**Why it happens:** Large reviews produce big `ReviewResult` JSON.
**How to avoid:** Compact form (counts + totals) to `$GITHUB_OUTPUT`; full form to an uploaded artifact (D-08). `[CITED: docs.github.com/actions/reference/limits]`
**Warning signs:** Workflow fails setting the output step on big PRs.

## Code Examples

> Patterns are derived from the existing codebase (read this session) and official CLI docs cited inline. No external pattern was copied verbatim.

### Claude Code usage capture (real tokens + cost)
```bash
# Source: code.claude.com/docs/en/headless
claude --bare -p "<prompt>" --output-format json | jq '{result, usage: .usage, cost: .total_cost_usd}'
# usage: { input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens }
```

### Antigravity headless in CI (pseudo-TTY workaround)
```bash
# Source: antigravitylab.net — non-TTY stdout drop workaround
script -qec 'agy -p "<prompt>" --model gemini-3.5-flash' /dev/null \
  | sed -r 's/\x1B\[[0-9;]*[A-Za-z]//g' | tr -d '\r'
# auth via GEMINI_API_KEY or ANTIGRAVITY_API_KEY env; --output-format json is unstable — parse text
```

### Copilot OTEL usage (env + post-run log read)
```bash
# Source: ccusage.com/guide/copilot — usage only via OTEL JSONL, not stdout
export COPILOT_OTEL_FILE_EXPORTER_PATH="$RUNNER_TEMP/copilot-otel"
copilot -s --no-ask-user   # run review (stdin prompt)
# then sum token attributes across "$COPILOT_OTEL_FILE_EXPORTER_PATH"/*.jsonl
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gemini` CLI as the Google engine | Google Antigravity CLI (`agy`), successor to Gemini CLI | 2026 | D-12: replace the gemini skeleton with an Antigravity spec. Install via `curl -fsSL https://antigravity.google/cli/install.sh \| bash` (no npm). `[CITED: search/antigravity docs]` |
| `bytes/4` estimation surfaced as "~est" | Engine-reported real usage where available; estimation labeled fallback | This phase (PERF-03) | Cross-engine accuracy varies (matrix); honest per-engine labeling. |
| 4 copy-pasted CLI adapters + manual registry dict | Spec-driven generic + auto-populated registry | This phase (ENGN-10) | Adding an engine = 1 spec entry. |
| `pip install litellm` for pricing | Vendor the pricing JSON only | tokscale-proven 2026 | Tiny footprint, trust-safe, no heavy dep. |

**Deprecated/outdated:**
- `gemini-cli` / `GeminiAdapter` skeleton → replaced by Antigravity spec (D-12).
- `SKELETON_ENGINES` frozenset + `require_functional_adapter` special-case → `functional` spec field (D-03).
- Global single `estimated` flag in token-meta → per-engine `estimated` (PERF-03).

## Runtime State Inventory

> Partial-trigger: ENGN-10 renames/removes `GeminiAdapter` and `gemini-cli` engine name. Most categories are N/A (this is a code refactor, not a data migration), but the engine-name change has consumer-facing surface.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Prevue is stateless across runs (sticky-comment marker only stores SHAs/findings, not engine names as keys). Verified: no datastore keyed on engine name. | none |
| Live service config | Consumers' `prevue.yml` / workflow `with: engine:` may name `gemini-cli`. Replacing it with `antigravity-cli` is a **breaking rename of a public config value**. | Decide: keep `gemini-cli` as an alias to the Antigravity spec, OR document the rename + fail-closed `UnknownEngineError` (current behavior names valid engines). Planner must pick; recommend alias for back-compat or explicit deprecation note. |
| OS-registered state | None — no Task Scheduler / launchd / pm2; runs ephemerally on `ubuntu-latest`. | none |
| Secrets/env vars | `install-engine-cli.sh` and `prevue-review.yml` reference engine-specific secrets (`COPILOT_GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `CURSOR_API_KEY`). Antigravity adds `GEMINI_API_KEY`/`ANTIGRAVITY_API_KEY`. The `gemini-cli` case is absent from `install-engine-cli.sh` today (skeleton). | Add Antigravity install + secret pass-through to `install-engine-cli.sh` and `prevue-review.yml`. New `usage_capture=otel-jsonl` needs `COPILOT_OTEL_FILE_EXPORTER_PATH` set in the review step env (code rename: none; env addition: yes). |
| Build artifacts / installed packages | The vendored pricing JSON ships in the wheel (`uv_build`). No stale egg-info concern (uv-managed). | Ensure `src/prevue/pricing/*.json` is included in the package (uv_build includes package data by default; verify). |

**Nothing found in category:** Stored data and OS-registered state — verified by codebase inspection (stateless reusable workflow; OOS "full codebase graph/indexing" confirms no persistent state).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Antigravity `agy` is the correct successor binary and `-p`/`--model` are its headless flags | Adapter Anatomy / D-12 | Wrong binary/flags → Antigravity engine non-functional; mitigated by required live `checkpoint:human-verify`. |
| A2 | Antigravity does NOT report usable tokens headlessly (so estimation fallback) | Token Matrix | If it does report usage, we under-deliver PERF-03 for that engine; low harm (estimate is honest). Verify in live test. |
| A3 | Copilot CLI OTEL JSONL is the only per-invocation usage source (no stdout usage) | Token Matrix | If a newer Copilot CLI prints usage on stdout, the OTEL plumbing is unnecessary complexity. Verify against installed `@github/copilot@1.0.61`. |
| A4 | LiteLLM pricing JSON model keys can be mapped to the model strings each CLI accepts (with an alias map) | Cost Computation | Name mismatches → missing prices for some models; mitigated by `engine.pricing` override (D-06c) and "unknown model → no cost, labeled" behavior. |
| A5 | `uv_build` includes `src/prevue/pricing/*.json` as package data in the wheel | Runtime State Inventory | If excluded, pricing JSON missing at runtime; verify with a built-wheel test or explicit package-data config. |
| A6 | GitHub Actions job-output limit is 1 MB (drives both-form) | OUTP-05 | If higher, compact-only might suffice — but both-form is still safer and D-08 locks it. Low risk. |
| A7 | Claude Code `--output-format json` envelope field names are `usage.{input_tokens,output_tokens,cache_read_input_tokens}` + `total_cost_usd` | Token Matrix / Pattern 2 | Field-name drift → capture returns 0; verify against installed `@anthropic-ai/claude-code@2.1.177` JSON output in a live/contract test. |

## Open Questions

1. **Antigravity CLI token reporting and CI stdout reliability**
   - What we know: `agy -p` exists, `--model` since v1.0.5, auth via `GEMINI_API_KEY`/`ANTIGRAVITY_API_KEY`, install via curl script. There is a documented non-TTY stdout-drop bug and an unstable `--output-format json`.
   - What's unclear: whether any reliable per-invocation token/usage output exists; whether the `script` pseudo-TTY wrapper is robust on `ubuntu-latest`.
   - Recommendation: implement the Antigravity spec with `usage_capture="none"` (estimate) and the pseudo-TTY invocation; **require a `checkpoint:human-verify` live sandbox run** before marking it production-functional. State the risk in the plan.

2. **gemini-cli → antigravity-cli engine-name migration**
   - What we know: `gemini-cli` is a public config value; current registry fails closed on unknown names.
   - What's unclear: whether any consumer already selects `gemini-cli` (it's a skeleton → likely no production use).
   - Recommendation: ship `antigravity-cli` as the new name; either alias `gemini-cli` → Antigravity spec or document the rename. Lean toward a clear rename since the skeleton was never functional.

3. **Copilot OTEL plumbing vs. accepting estimate for Copilot**
   - What we know: real Copilot usage needs OTEL env + post-run log read; meaningful added complexity.
   - What's unclear: whether the effort is worth it vs. labeling Copilot tokens as estimated this phase.
   - Recommendation: planner decides scope — OTEL capture is the "real" path (default engine is Copilot, so it matters), but it's the highest-effort capture. Acceptable to phase it: estimate first, OTEL as a follow-up task within the phase if budget allows.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Engine CLIs (copilot/claude/cursor/agy) | Live review (runtime, in-workflow) | n/a (installed in-workflow via `install-engine-cli.sh`) | pinned per engine | — |
| LiteLLM pricing JSON | Cost compute (PERF-03) | vendored in-repo (this phase creates it) | pinned snapshot | `engine.pricing` override; "unknown model → no cost" |
| `script` (util-linux) for Antigravity pseudo-TTY | Antigravity headless in CI | present on `ubuntu-latest` | system | none — required for Antigravity |
| uv / pytest / ruff (dev + CI) | Build, test, lint | yes (locked) | per pyproject | — |

**Missing dependencies with no fallback:** none blocking (all engine CLIs install in-workflow; pricing JSON is created this phase).
**Missing dependencies with fallback:** pricing rows for engine-specific model names — fall back to `engine.pricing` override or no-cost-labeled.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.* + pytest-cov 7.* (`[VERIFIED: pyproject.toml]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_engine_contract.py tests/test_config_precedence.py -x -q` |
| Full suite command | `uv run pytest -q` (then `bash scripts/ci-local.sh` before any push — project memory) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENGN-10 | Spec-driven generic passes the same contract suite as the 4 old adapters; registry auto-populates from specs | unit (parametrized) | `uv run pytest tests/test_engine_contract.py -x` | ✅ exists (must stay green; extend params) |
| ENGN-10 | Per-engine `AuthError` types + argv shapes preserved | unit | `uv run pytest tests/test_engine_contract.py::test_vendor_argv -x` | ✅ exists |
| ENGN-10 | `functional` flag replaces SKELETON_ENGINES; unknown engine fails closed | unit | `uv run pytest tests/test_registry.py -x` | ✅ exists (update) |
| WKFL-05 | input > yml > default for engine, model (+fallback model) | unit (matrix) | `uv run pytest tests/test_config_precedence.py -x` | ❌ Wave 0 |
| PERF-03 | Claude stdout-json usage captured (real tokens, cost); estimated:false | unit | `uv run pytest tests/test_usage_capture.py::test_claude_stdout_json -x` | ❌ Wave 0 |
| PERF-03 | Cursor/Antigravity → bytes/4 fallback, estimated:true | unit | `uv run pytest tests/test_usage_capture.py::test_fallback_estimated -x` | ❌ Wave 0 |
| PERF-03 | Copilot OTEL JSONL parsed + summed (if in scope) | unit | `uv run pytest tests/test_usage_capture.py::test_copilot_otel -x` | ❌ Wave 0 |
| PERF-03 | Cost = tokens × pricing (incl. cache discount); override precedence | unit | `uv run pytest tests/test_pricing.py -x` | ❌ Wave 0 |
| ENGN-08 | raw_args list appended after framework argv; ignored from PR-head | unit | `uv run pytest tests/test_raw_args.py -x` | ❌ Wave 0 |
| ENGN-09 | per-role model resolves (classify/review); consolidate slot resolves but merge stays deterministic | unit | `uv run pytest tests/test_model_roles.py -x` | ❌ Wave 0 |
| OUTP-05 | compact `$GITHUB_OUTPUT` + full artifact JSON, schema_version="1.0" | unit | `uv run pytest tests/test_output_contract.py -x` | ❌ Wave 0 |
| OUTP-05 | workflow YAML declares outputs + upload-artifact step | static | `uv run pytest tests/test_reusable_workflow_yaml.py -x` | ✅ exists (extend) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/<touched-area> -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** `bash scripts/ci-local.sh` green (full suite + ruff) before `/gsd-verify-work` and before any push.

### Wave 0 Gaps
- [ ] `tests/test_config_precedence.py` — WKFL-05 input>yml>default matrix
- [ ] `tests/test_usage_capture.py` — PERF-03 per-strategy capture (stdout-json / otel-jsonl / fallback)
- [ ] `tests/test_pricing.py` — PERF-03 cost compute + cache discount + override precedence
- [ ] `tests/test_raw_args.py` — ENGN-08 list-form append + base-ref-only
- [ ] `tests/test_model_roles.py` — ENGN-09 per-role resolution + deterministic merge preserved
- [ ] `tests/test_output_contract.py` — OUTP-05 compact + full + schema_version
- [ ] `tests/fixtures/pricing/` — small pricing-JSON fixture (don't load the full 500 KB snapshot in unit tests)
- [ ] `tests/fixtures/usage/` — sample Claude JSON envelope, Cursor JSON (no tokens), Copilot OTEL JSONL line, Antigravity text output
- [ ] Live `checkpoint:human-verify` for Antigravity (`agy`) headless review on a sandbox PR (not automatable — vendor-controlled binary + non-TTY risk)

## Security Domain

> `security_enforcement: true`, ASVS level 1. This phase touches config trust (raw_args, pricing) and external CLI invocation — security-relevant.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface; engine secrets are passed-through named secrets (existing pattern). |
| V3 Session Management | no | Stateless workflow. |
| V4 Access Control | yes | SKIL-04 fail-closed config trust: `engine.raw_args` and `engine.pricing` read ONLY from trusted base-ref `prevue.yml` (never PR-head). Enforced via `resolve_consumer_config_path` sentinel path. |
| V5 Input Validation | yes | `engine.raw_args` is **list form** (no shell parsing) → no command injection. `engine.pricing` validated into a pydantic model (`ConfigDict(extra="forbid")`). Config blocks validated, not `eval`'d. |
| V6 Cryptography | no | No new crypto. |

### Known Threat Patterns for {Python framework + CLI subprocess + GitHub Actions}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PR-head config injects CLI flags via raw_args | Tampering / Elevation | Base-ref-only read (SKIL-04); list-form args appended after framework argv; test that PR-head raw_args is ignored. |
| PR-head config fakes pricing to hide cost | Tampering | Pricing override read base-ref-only; no runtime fetch (D-06a). |
| Command injection through raw_args | Tampering | List form, no shell string, no `shell=True` (existing `subprocess.run` uses arg list). |
| Engine CLI exfiltrates secrets via tool use | Information Disclosure | Existing zero-tool posture (no `--allow-tool`); static scan `test_adapter_cli_commands_contain_no_allow_tool_flags` must stay green across the generic. SECURITY.md D-08 live verification unchanged. |
| Secret leakage in stderr on engine failure | Information Disclosure | Existing `sanitize_stderr(secret)` in `subprocess_invoke`; the generic must keep passing `secret=` through. |
| Supply-chain: malicious pricing JSON bump | Tampering | D-06b opens a PR (human-reviewed); pin the snapshot; never auto-merge the bump. |
| Antigravity install script (curl|bash) tampering | Tampering | Pin/verify the install (mirror the Cursor `PREVUE_CURSOR_INSTALL_SHA256` checksum pattern in `install-engine-cli.sh` if feasible). |

## Sources

### Primary (HIGH confidence)
- Prevue codebase (read this session): `engines/{base,registry,copilot_cli,cursor_cli,claude_code_cli,gemini_cli,flow,tokens,subprocess_invoke}.py`, `config.py`, `models.py`, `multicall.py`, `review.py` (model-resolution + token-aggregation sites), `github/comments.py` (token rendering), `tests/test_engine_contract.py`, `.github/workflows/prevue-review.yml`, `.github/scripts/install-engine-cli.sh`, `pyproject.toml` — ground truth for adapter axes, config surface, token-meta shape, and integration points.
- code.claude.com/docs/en/headless — Claude Code `-p --output-format json`, `total_cost_usd`, per-model cost, `--bare`, stdin piping (HIGH, official).
- cursor.com/docs/cli (headless, reference/output-format) + forum.cursor.com (token-usage feature requests) — Cursor JSON envelope has no token fields (HIGH, official + maintainer-confirmed gap).
- ccusage.com/guide/copilot — Copilot CLI usage only via OTEL JSONL (`COPILOT_OTEL_FILE_EXPORTER_PATH`), not stdout (MEDIUM-HIGH, tool docs cross-checked with github.blog agentic-workflows token-usage.jsonl).
- docs.github.com/en/actions/reference/limits — 1 MB job-output limit (HIGH, official).
- raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json — pricing JSON structure + fields (HIGH, source-of-truth file).

### Secondary (MEDIUM confidence)
- antigravitylab.net (agy headless / non-TTY stdout CI articles) — `agy -p` argv prompt, non-TTY stdout-drop bug + `script` workaround, `--output-format json` unstable, `GEMINI_API_KEY`/`ANTIGRAVITY_API_KEY` auth (MEDIUM, community-verified, consistent across two articles + DEV/codelabs).
- antigravity.google/docs (cli-using, cli-install) — JS-rendered; install via curl script, `agy` binary (MEDIUM — page content not statically extractable; corroborated by multiple secondary sources).
- search: Antigravity `--model` flag since v1.0.5, `models` subcommand, defaults to Gemini 3.5 Flash (MEDIUM).
- github.com/junhoyeo/tokscale — proven approach: read usage AI CLIs record (Claude JSONL `usage`, Codex `token_count`), price via LiteLLM, 1-hour cache (MEDIUM-HIGH, the explicit user reference).

### Tertiary (LOW confidence)
- Antigravity per-invocation token reporting format — unconfirmed; treated as estimate-fallback + live-verify checkpoint.

## Metadata

**Confidence breakdown:**
- Adapter consolidation (ENGN-10): HIGH — all four adapters + contract suite read directly; varying axes enumerated from source.
- Config precedence (WKFL-05): HIGH — override-knob inventory grounded in `config.py` + workflow YAML; supports formalize-existing.
- ENGN-09 shape: HIGH — existing `ReviewRequest.model` + multicall wiring read directly.
- Token capture (PERF-03): MEDIUM — capability matrix solid for Claude/Cursor/Copilot (official + tool docs); LOW for Antigravity.
- Cost/pricing (PERF-03): HIGH — LiteLLM JSON structure verified from source file.
- OUTP-05: HIGH — 1 MB limit verified; pydantic serialization trivial.
- Antigravity engine (D-12): LOW-MEDIUM — flags/auth/install corroborated; token reporting + CI reliability unconfirmed → live checkpoint required.

**Research date:** 2026-06-28
**Valid until:** 2026-07-28 for stable surfaces (codebase, LiteLLM JSON, Actions limits); 2026-07-05 for fast-moving CLI surfaces (Antigravity especially — verify `agy` flags/usage at plan time).
