# Phase 10: Boundary Contracts - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Stabilize the three highest-churn-cost boundaries before more adapters and config knobs accrue and make every change N× more expensive to retrofit:

1. **Engine-adapter contract** — consolidate the 4 near-identical CLI adapters into a spec-driven generic, then add the contract features (real tokens, raw-args, per-role models) once against the generic instead of 4× against copy-pasted adapters.
2. **Config resolution precedence** — declare, document, and test the order so ambiguous precedence cannot silently change behavior.
3. **Machine-readable output** — emit the validated `ReviewResult` as a stable, versioned contract consumers can chain automation on.

**Hard sequencing (from ROADMAP):** ENGN-10 (adapter consolidation) lands FIRST. PERF-03 / ENGN-08 / ENGN-09 are adapter-contract changes that cost 4× against copy-pasted adapters but 1× against the spec-driven generic. Consolidate, then add contract features once.

**Scope guard:** This is a contract/boundary-locking phase. No new review *behavior* (no LLM consolidate pass, no new classification logic). The one behavioral addition is real token + cost reporting, which extends existing OUTP-04 output.

</domain>

<decisions>
## Implementation Decisions

### ENGN-10 — Adapter consolidation (lands FIRST)
- **D-01:** Use a **spec-driven generic** adapter, not a template-method base. One concrete `CliEngineAdapter` class implements `review`/`classify`/`classify_skills` once; each engine is a declarative `CliEngineSpec` (secret env + validator, argv, prompt delivery `{stdin | tempfile-arg}`, model flag `{env | argv}`, cwd, functional bool). The registry **auto-populates** by iterating the spec list — adding a CLI engine = ~1 data entry, no duplicated methods, no manual registry import+dict edit.
  - **Why:** User priority is minimizing the per-engine cost of adding future engines. Spec-as-data wins decisively over per-engine subclasses.
- **D-02:** Keep the `EngineAdapter` ABC as the **top boundary**. `CliEngineAdapter(spec)` is the spec-driven generic for the **CLI family only**. A future `ApiEngineAdapter` (for SDK/API engines) is a **sibling** to `CliEngineAdapter`, NOT forced through `CliEngineSpec`. The registry holds both kinds uniformly.
  - **Why:** User named Bedrock / Vertex / Azure as desired future engines — those are API/SDK-based, not CLI subprocess. The CLI spec must not become the only extension path. Do NOT build Bedrock/Vertex/Azure this phase — just don't block them.
- **D-03:** Drop the `SKELETON_ENGINES` special-case; `functional` becomes a field on the spec. (See D-12 for the Gemini→Antigravity migration that makes the former skeleton functional.)

### PERF-03 — Real token accounting + cost
- **D-04:** Capture **real input/output/cache tokens for all engines** — estimation is NOT the primary path. Switch each adapter to its CLI's structured/usage output as needed to obtain real counts. `bytes/4` (`src/prevue/engines/tokens.py`) is demoted to a **labeled fallback** used only when an engine genuinely cannot report usage.
  - **Why:** User cites tokscale as proof accurate cross-engine reporting is achievable without estimation.
- **D-05:** **Surface dollar cost now** (not deferred). Compute estimated cost per review from a pricing table and add a cost line to the existing OUTP-04 sticky summary. The existing `token_meta.estimated` / `review_estimated` / `classify_estimated` flags anticipate this swap.
- **D-06:** **Pricing source of truth = LiteLLM's `model_prices_and_context_window.json`** (BerriAI/litellm) — the same community-maintained DB tokscale uses; covers most models incl. cache-token discounts and tiered pricing.
  - **D-06a:** Vendor a **pinned snapshot** of that JSON in-repo. NO runtime fetch during a review (preserves SKIL-04 trust posture). It's a single JSON file — low cost to bundle.
  - **D-06b:** **Auto-update via a scheduled CI workflow** that pulls the latest LiteLLM JSON and opens a PR to bump the pinned snapshot — low manual upkeep, still pinned + reviewed (trust-safe).
  - **D-06c:** **Consumer override:** a `engine.pricing` map in `prevue.yml` takes precedence over the bundled snapshot — for enterprise/negotiated rates, self-hosted, or engines absent from LiteLLM.

### WKFL-05 — Config precedence
- **D-07:** Declared order is **workflow input > `.github/prevue.yml` > built-in defaults**. (Claude discretion on mechanism — see Claude's Discretion below.) Today only `engine` has explicit precedence (`PREVUE_ENGINE` env > yml > default, `src/prevue/config.py:141`); this phase declares + tests the order so it cannot silently change once consumers rely on it.

### OUTP-05 — Machine-readable output
- **D-08:** Emit **both** forms: a **compact job output** (conclusion, severity counts, tokens, cost) for cheap downstream chaining (merge gates in `if:`), AND the **full `ReviewResult` JSON as a build artifact** for richer automation/dashboards. Both-form covers small gates and big consumers and sidesteps Actions job-output size limits on large reviews.
- **D-09:** The emitted JSON is a **versioned contract**: include `schema_version` (start `"1.0"`) and a documented field shape, so it can evolve without silently breaking consumer automations. Applies to both the compact output and the full artifact.

### ENGN-08 — Raw-args passthrough
- **D-10:** `engine.raw_args: [...]` read **only from the trusted base-ref `prevue.yml`** (never PR-head). **List form** (no shell string), appended after the framework's argv. Consistent with SKIL-04 fail-closed config trust — a malicious PR cannot inject CLI flags into its own review.

### ENGN-09 — Per-role model tiering
- **D-11:** Add the per-role model concept (cheap classify / strong review / cheap consolidate) + a single-model fallback. (Config shape is Claude discretion — see below.)
- **D-13 (consolidate-role scope):** **Reserve the role wiring only** this phase — the consolidate role + model slot must *resolve* in config/contract, but multicall merge stays **deterministic (fingerprint)**. The actual LLM consolidate/dedup pass lands in **Phase 13 (QUAL-01)**, which depends on ENGN-09. Keeps Phase 10 a pure boundary phase with no new review behavior.

### Engine roster
- **D-12:** **Gemini CLI is replaced by Antigravity CLI.** Make this engine a **functional** spec now (D-01/D-03), targeting Google's **Antigravity CLI**, not the old `gemini` binary. Researcher MUST verify Antigravity CLI specifics: binary name, prompt delivery (`stdin` | tempfile-arg), model flag form, auth env var, and its usage/token reporting format (needed for PERF-03 D-04). The existing `src/prevue/engines/gemini_cli.py` skeleton is replaced by an Antigravity spec entry.

### Claude's Discretion
- **WKFL-05 mechanism (D-07):** User said "you decide." **Leaning: formalize existing per-field reads** — add one documented precedence statement + a precedence **test matrix** for the knobs that actually have an input override (engine, model, fallback enable/model), rather than building a generic layered resolver that gives every knob a `PREVUE_*` input layer. Planner confirms by counting how many knobs realistically need a caller-side override before deciding whether the generic resolver earns its cost. Most teams set policy once in `prevue.yml`; the caller `with:` block is mainly engine/model selection.
- **ENGN-09 config shape (D-11):** User said "you decide." **Leaning: a per-role `engine.models: { classify, review, consolidate }` block in `prevue.yml` with a single `model:` as the fallback for any unset role**, adapter selects per call-site by role. Fits the existing single-read config loader and is the natural consumer-facing surface. Planner confirms against the spec-driven adapter + multicall wiring for least churn.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements (locked WHAT)
- `.planning/REQUIREMENTS.md` — ENGN-10 (line 55, FIRST), WKFL-05 (line 16), PERF-03 (line 100), ENGN-08 (line 51), ENGN-09 (line 53), OUTP-05 (line 71). Full requirement text + rationale; this CONTEXT locks only the HOW.
- `.planning/ROADMAP.md` §"Phase 10: Boundary Contracts" — goal, 6 success criteria, the ENGN-10-first sequencing rule.

### External references (study before implementing)
- https://github.com/junhoyeo/tokscale — reference for capturing accurate per-engine token usage without estimation (PERF-03 D-04). README states it uses LiteLLM pricing data with tiered + cache-token discount support.
- https://github.com/BerriAI/litellm — `model_prices_and_context_window.json` is the pricing source of truth (PERF-03 D-06). Vendor a pinned snapshot.
- Google **Antigravity CLI** docs — verify invocation + usage reporting (D-12). Researcher to locate the official CLI reference (replaces the old `gemini` CLI).

### Code touchpoints (existing boundaries being locked)
- `src/prevue/engines/base.py` — `EngineAdapter` ABC (stays the top boundary, D-02).
- `src/prevue/engines/registry.py` — manual `ENGINES` dict + `SKELETON_ENGINES` special-case (replaced by spec-list auto-population, D-01/D-03).
- `src/prevue/engines/copilot_cli.py`, `cursor_cli.py`, `claude_code_cli.py`, `gemini_cli.py` — the 4 adapters being consolidated; their varying axes define the `CliEngineSpec` fields.
- `src/prevue/engines/flow.py` — shared `review_with_retry` + `_token_meta`/`_retry_token_meta` (where real-token capture replaces bytes/4, D-04).
- `src/prevue/engines/tokens.py` — `estimate_tokens` (demoted to labeled fallback, D-04).
- `src/prevue/config.py` — `load_config` + `_resolve_engine` (the precedence to declare/test, D-07; add `engine.raw_args` D-10, `engine.models` D-11, `engine.pricing` D-06c).
- `src/prevue/models.py` — `ReviewResult` (serialized + versioned for OUTP-05, D-08/D-09).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `flow.review_with_retry` + `subprocess_invoke.invoke_subprocess_text`: already de-duplicate the review/retry/timeout/secret-sanitize path across all 4 adapters (Phase 5, D-08). The spec-driven generic builds directly on these — the per-engine bodies collapse to spec data.
- `engine_meta["tokens"]` shape (`{review, estimated}`): the carrier for real token counts; extend with input/output/cache + cost while keeping the `estimated` flag for fallback labeling.
- `_resolve_engine` (config.py:141): the one existing precedence implementation — generalize its pattern (env/input > yml > default) into the declared WKFL-05 order.

### Established Patterns
- **Fail-closed trust (SKIL-04):** base-ref-only config reads, sentinel-path fallback in Actions (`resolve_consumer_config_path`). Raw-args (D-10) and pricing override (D-06c) MUST inherit this — never read from PR-head.
- **Single-read config loader:** `load_config` does one `yaml.safe_load` and validates each section into a pydantic model. New `engine.*` knobs (raw_args, models, pricing) slot into the same `PrevueConfig`.
- **`functional` vs skeleton:** today via `SKELETON_ENGINES` frozenset + `require_functional_adapter`; becomes a spec field (D-03).

### Integration Points
- Registry → spec list: `get_adapter` / `require_functional_adapter` resolve from the auto-populated registry.
- Multicall (`src/prevue/multicall.py`) → per-role model resolution (D-11) + reserved consolidate slot (D-13).
- OUTP-04 sticky summary (in `src/prevue/review.py`) → add measured tokens + cost line (D-05).
- Workflow YAML (`.github/workflows/`) → new job `output:` + artifact upload step for OUTP-05 (D-08).

</code_context>

<specifics>
## Specific Ideas

- tokscale (junhoyeo/tokscale) is the user's reference point for "accurate tokens are achievable without estimation" — it leans on LiteLLM pricing data with tiered + cache-token-discount support. Mirror that approach.
- Antigravity CLI replaces Gemini CLI in the user's mental model of the engine roster — treat the old `gemini` adapter as obsolete, not just dormant.
- The whole phase is framed as "lock the contract before it ossifies" — favor stable, versioned, documented, tested boundaries over feature breadth.

</specifics>

<deferred>
## Deferred Ideas

- **LLM consolidate/dedup pass** — the actual cheap-model merge pass behind ENGN-09's consolidate role belongs to **Phase 13 (QUAL-01)**. Phase 10 only reserves the role wiring (D-13).
- **API engines (Bedrock / Vertex / Azure)** — the `ApiEngineAdapter` sibling is left *possible* by D-02 but **not built** this phase. Future phase when an API engine is actually needed.
- **Generic layered config resolver** — only if the planner finds enough knobs need caller-side overrides to justify it (D-07); otherwise deferred indefinitely in favor of formalize-existing.

None of the above are scope creep into Phase 10 — they are explicitly bounded out.

</deferred>

---

*Phase: 10-boundary-contracts*
*Context gathered: 2026-06-28*
