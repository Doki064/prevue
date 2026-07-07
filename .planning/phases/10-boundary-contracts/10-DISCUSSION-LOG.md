# Phase 10: Boundary Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28
**Phase:** 10-boundary-contracts
**Areas discussed:** Area selection, ENGN-10 consolidation, PERF-03 token capture, PERF-03 cost, WKFL-05 precedence, OUTP-05 output form, ENGN-09 model shape, ENGN-08 raw-args, Gemini/API direction, Output JSON versioning, Consolidate-role scope, Pricing source

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| ENGN-10 consolidation shape | Spec-driven vs template-method | ✓ |
| PERF-03 token capture | JSON output vs best-effort + cost | ✓ |
| WKFL-05 precedence mechanism | Generic resolver vs formalize existing | ✓ |
| OUTP-05 + adapter surface | Output form + ENGN-08/09 config | ✓ |

**User's choice:** all
**Notes:** User wants to lock the entire boundary surface this phase.

---

## ENGN-10 — Adapter consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| Spec-driven generic | One `CliEngineAdapter` + declarative `CliEngineSpec` per engine; registry auto-populates from spec list | ✓ |
| Template-method base | Abstract base + per-engine subclass hooks; registry still lists classes | |

**User's choice:** Spec-driven generic — "One that will minimize work when adding another engine (Bedrock, Vertex, Azure, etc.) I don't mind big changes now, as long as it benefits later."
**Notes:** Claude flagged that Bedrock/Vertex/Azure are API/SDK-based, not CLI — so `EngineAdapter` ABC stays the top boundary and a future `ApiEngineAdapter` is a sibling, not forced through `CliEngineSpec`. API engines not built this phase (D-02).

---

## PERF-03 — Token capture

| Option | Description | Selected |
|--------|-------------|----------|
| JSON output mode per engine | Switch all CLIs to structured output, parse usage | ✓ (intent) |
| Best-effort, per-engine | Real tokens only where cleanly exposed, bytes/4 otherwise | |
| You decide | Researcher picks least-invasive path | |

**User's choice:** Real tokens for all engines, no estimation — "Since tokscale can report from a bunch of engines, I'm sure it is possible without estimation. So let choose the best method to report accurate token consumptions for all possible engines."
**Notes:** tokscale (junhoyeo/tokscale) added as canonical ref. bytes/4 demoted to labeled fallback.

## PERF-03 — Cost

| Option | Description | Selected |
|--------|-------------|----------|
| Tokens + cost now | Ship pricing table, compute cost in summary | ✓ |
| Tokens now, cost later | Measured tokens only, defer pricing DB | |

**User's choice:** Tokens + cost now.

---

## WKFL-05 — Config precedence

| Option | Description | Selected |
|--------|-------------|----------|
| Generic layered resolver | Every knob overridable by workflow input through one tested layer | |
| Formalize existing per-field | Document + test order for knobs with real input overrides | (leaning) |
| You decide | Planner picks after counting knobs | ✓ |

**User's choice:** First asked for clarification ("I don't remember about this requirement"); Claude explained the three config sources (workflow input / prevue.yml / defaults) and the lock-the-contract intent. User then chose "You decide."
**Notes:** Claude leaning formalize-existing + precedence test matrix; planner confirms (D-07).

---

## OUTP-05 — Output form

| Option | Description | Selected |
|--------|-------------|----------|
| Both: compact output + full artifact | Compact job output for chaining + full ReviewResult JSON artifact | ✓ |
| Job output only | Risks Actions output size limits | |
| JSON artifact only | Complete but heavier to chain | |

**User's choice:** Both.

---

## ENGN-09 — Model tiering config shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-role block in prevue.yml | `engine.models: {classify, review, consolidate}` + single fallback | (leaning) |
| Role enum on the contract | `role` param on adapter methods | |
| You decide | Researcher/planner picks | ✓ |

**User's choice:** You decide.
**Notes:** Claude leaning per-role `engine.models` block with single-model fallback (D-11).

---

## ENGN-08 — Raw-args passthrough

| Option | Description | Selected |
|--------|-------------|----------|
| prevue.yml only, base-ref trusted | `engine.raw_args` from base-ref only, list form, appended to argv | ✓ |
| prevue.yml + workflow input | Allow from both sources | |
| You decide | Planner picks source + safety | |

**User's choice:** prevue.yml only, base-ref trusted.

---

## Gemini / API-engine direction

| Option | Description | Selected |
|--------|-------------|----------|
| Gemini functional + leave API room | Make gemini a real spec; ApiEngineAdapter sibling possible later | ✓ |
| Keep gemini skeleton | functional=false, not wired live | |
| You decide | Researcher checks gemini CLI maturity | |

**User's choice:** Option A — "But Gemini CLI is replaced by Antigravity CLI, so we need to change to that."
**Notes:** Engine becomes functional but targets Antigravity CLI, not the old `gemini` binary. Researcher must verify Antigravity CLI invocation + usage reporting (D-12).

---

## Output JSON versioning

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, versioned + documented | `schema_version` + documented shape | ✓ |
| No, raw ReviewResult dump | Serialize as-is, no version field | |

**User's choice:** Yes, versioned + documented (D-09).

---

## Consolidate-role scope (ENGN-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Reserve role wiring only | Role/model slot resolves; merge stays deterministic; LLM pass = Phase 13 | ✓ |
| Add LLM consolidate pass now | Wire a cheap-model consolidate call this phase | |
| You decide | Planner decides | |

**User's choice:** Reserve role wiring only (D-13). Keeps Phase 10 contract-only; LLM consolidate deferred to Phase 13 (QUAL-01).

---

## Pricing table source of truth

| Option | Description | Selected |
|--------|-------------|----------|
| In-repo table, config-overridable | Hardcoded map + consumer override | (partially) |
| Reuse tokscale's pricing map | Depend on tokscale pricing data | (informed final) |
| You decide | Researcher checks tokscale pricing reuse | ✓ |

**User's choice:** "You decide" with rich guidance — noted tokscale uses LiteLLM pricing data (BerriAI/litellm); asked Claude to weigh upkeep, auto-update feasibility, and enterprise/custom pricing plans.
**Notes:** Resolved to: vendor a pinned snapshot of LiteLLM's `model_prices_and_context_window.json` (no runtime fetch), auto-update via scheduled CI PR, consumer `engine.pricing` override for enterprise/negotiated/self-hosted rates (D-06).

---

## Claude's Discretion

- **WKFL-05 mechanism** — leaning formalize-existing + precedence test matrix; planner confirms (D-07).
- **ENGN-09 config shape** — leaning per-role `engine.models` block + single-model fallback (D-11).
- **Pricing implementation** — resolved by Claude to LiteLLM pinned snapshot + auto-update CI + consumer override (D-06).

## Deferred Ideas

- LLM consolidate/dedup pass → Phase 13 (QUAL-01).
- API engines (Bedrock/Vertex/Azure) + `ApiEngineAdapter` sibling → future phase; left possible by D-02, not built now.
- Generic layered config resolver → only if planner finds enough knobs warrant it; otherwise deferred.
