# Phase 5: Multi-Engine Adapter Support - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver **ENGN-04**: additional `EngineAdapter` implementations behind the
existing locked interface, selectable at runtime via config, proving the engine
abstraction is genuinely vendor-agnostic before any consumer-facing surface
locks in Phase 6.

**In scope:**
- Two fully-built new adapters: **Claude Code CLI** and **Cursor CLI**
- A `Gemini` adapter as a registered, documented skeleton (not functional)
- Runtime engine selection mechanism (env var + registry) replacing the
  hard-coded `CopilotCliAdapter()` at `review.py:75`
- Per-engine auth credential handling and model passthrough
- Hoisting shared prompt assembly + output contract + prompt-injection fencing
  out of `copilot_cli.py` into a shared module
- A parametrized contract test suite proving every adapter honors the same
  `ReviewRequest → ReviewResult` contract

**Out of scope (Phase 6+):**
- The full `prevue.yml` config surface (rich engine config, per-engine tuning)
- A functional Gemini adapter
- Per-engine timeout/budget tuning
- Engine fallback chains (no silent fallback — fail-closed)

</domain>

<decisions>
## Implementation Decisions

### Adapter Scope
- **D-01:** Build **two** new adapters fully end-to-end: **Claude Code CLI**
  and **Cursor CLI**. User has live access to both — enables real test-PR
  verification. Two data points prove agnosticism better than one.
- **D-02:** **Gemini** ships as a registered skeleton: a `GeminiAdapter` class
  in the registry whose `review()` raises
  `NotImplementedError("Gemini adapter planned — see ENGN-04")`, with a
  docstring noting the intended CLI/auth/model. Demonstrates the "add an engine"
  extension point concretely without shipping dead, live-untested code that
  claims to work.

### Engine Selection
- **D-03:** Selection via a `PREVUE_ENGINE` env var (default `copilot-cli`)
  mapped through a name→adapter **registry**. Minimal and workflow-settable now;
  Phase 6 wires `prevue.yml` to the same env/registry without an interface
  change. Replaces the hard-coded `CopilotCliAdapter()` at `review.py:75`.
- **D-04:** Unknown/unregistered `PREVUE_ENGINE` value is **fail-closed**: raise
  a config error naming the bad value and listing valid engines; the run fails
  visibly. No silent fallback to Copilot (consistent with Phase 1 D-09).

### Per-Engine Auth & Model
- **D-05:** **Native per-engine env vars** for credentials — each adapter reads
  its vendor's standard var: `ANTHROPIC_API_KEY` (Claude Code),
  `CURSOR_API_KEY` (Cursor), `COPILOT_GITHUB_TOKEN` (Copilot, unchanged).
  Matches each CLI's own docs; no translation layer. The workflow passes the
  correct secret per selected engine.
- **D-06:** **Fail-closed, per-adapter early credential check** — each adapter
  validates its credential is present (and format-checks where the vendor has a
  known prefix, e.g. Copilot's `github_pat_`) and raises an auth error BEFORE
  spawning the subprocess. Consistent with the existing `CopilotAuthError` +
  Phase 1 D-09.
- **D-07:** **Per-engine native model selection**, none pinned — use each CLI's
  default with an env passthrough escape hatch (mirrors Phase 1 D-03).
  `ReviewRequest.model` remains the single carrier into the adapter; each
  adapter maps it to its vendor's native model flag/var.

### Output Handling
- **D-08:** **Same output contract + retry-then-degrade for all adapters.**
  Reuse the engine-agnostic `parsing.py` (`extract_json_fence`,
  `validate_findings`) and the existing retry-then-degrade flow for every
  engine. If a model doesn't emit a clean `json` fence, it degrades to a
  neutral check exactly like Copilot today. This is itself a proof that the
  parser is engine-agnostic.
- **D-09:** **Hoist shared prompt to a shared module.** Move `OUTPUT_CONTRACT`,
  `_build_prompt`, and the untrusted-data fencing (`_safe_diff_block`,
  `_escape_line`, `_build_retry_prompt`) out of `copilot_cli.py` into a shared
  module (e.g. `engines/prompt.py`) so every adapter uses identical, audited
  prompt-injection posture. Adapters then differ ONLY in subprocess
  invocation + auth + model mapping. Prevents a weaker re-implementation of the
  security-critical fencing per engine.

### Timeout / Budget
- **D-10:** **Keep the shared 300s default** (`ReviewRequest.budget_seconds=300`)
  for all adapters this phase. `ReviewRequest` already carries `budget_seconds`,
  so per-engine tuning is overridable later (Phase 6) without an interface
  change. No latency data yet to justify per-engine budgets.

### Validation
- **D-11:** **Parametrized contract test suite, mocked subprocess.** One pytest
  suite parametrized over every registered adapter: feed the same
  `ReviewRequest` fixture, mock the CLI subprocess with canned stdout, assert
  each returns a valid `ReviewResult` and honors the contract — including the
  degrade, retry, and auth-fail paths. No live API calls in CI; reuses the
  subprocess-mock pattern from the existing Copilot tests. Structurally enforces
  that all adapters honor one contract.
- **D-12:** **Live verification of new adapters only** (Claude Code + Cursor) on
  a real sandbox-repo test PR (Phase 1 D-11 sandbox path). Copilot was verified
  in Phase 1; the contract suite guards against regression.

### Claude's Discretion
- Exact module names/layout for the shared prompt module and registry.
- Precise per-adapter subprocess invocation flags for Claude Code (`claude -p`)
  and Cursor (`cursor-agent`) — research and lock during planning against each
  CLI's headless docs.
- Whether the registry lives in `engines/__init__.py` or a dedicated
  `engines/registry.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Engine adapter contract & existing implementation
- `src/prevue/engines/base.py` — the locked `EngineAdapter` ABC (`name` +
  `review(req) -> ReviewResult`). Interface is FINAL (Phase 1 D-02); new
  adapters must not break it.
- `src/prevue/engines/copilot_cli.py` — reference adapter. Source of
  `OUTPUT_CONTRACT`, `_build_prompt`, untrusted-data fencing, `CopilotAuthError`,
  `EngineFailure`, retry-then-degrade flow — all to be reused/hoisted.
- `src/prevue/engines/parsing.py` — engine-agnostic `extract_json_fence` +
  `validate_findings`; reused unchanged by all adapters.
- `src/prevue/models.py` — `ReviewRequest` / `ReviewResult` / `Finding` pydantic
  contract carrying `model` and `budget_seconds`.
- `src/prevue/review.py` §`run_review` (line ~75) — the `adapter or
  CopilotCliAdapter()` hard-coding to be replaced by registry lookup.

### Requirements & decisions
- `.planning/REQUIREMENTS.md` — ENGN-04 definition (promoted from CUST-03,
  2026-06-13); ENGN-01/02/03 for the inherited contract.
- `.planning/ROADMAP.md` §Phase 5 — phase goal and boundary.
- `.planning/research/STACK.md` — verified CLI/packaging facts; Copilot CLI
  headless invocation pattern that the new adapters mirror.
- `.planning/phases/01-walking-skeleton-review-loop/01-CONTEXT.md` — D-01/D-02
  (adapter contract locked), D-03 (model default + env passthrough), D-09
  (engine-failure posture), D-11 (sandbox live-verify path).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EngineAdapter` ABC (`engines/base.py`): the locked port every new adapter
  subclasses. No changes needed.
- `parsing.py` (`extract_json_fence`, `validate_findings`): already
  engine-agnostic — new adapters parse output through it directly.
- `copilot_cli.py` prompt/fencing/error machinery: hoist to shared module
  (D-09) and reuse; `CopilotAuthError`/`EngineFailure` patterns generalize to
  per-adapter auth/failure classes.
- `ReviewRequest`/`ReviewResult` models already carry `model` + `budget_seconds`
  — no interface change needed for per-engine model/timeout.

### Established Patterns
- Adapter = a class with `name` + one `review()` that shells out via stdlib
  `subprocess` (no wrapper libs) — STACK.md pattern. New adapters follow it.
- Early-validation-then-fail: `CopilotAuthError` raised before subprocess
  (D-06 generalizes this).
- Retry-then-degrade on unparseable output → neutral check (D-08 reuses).
- Subprocess-mock test pattern from existing Copilot tests → parametrized
  contract suite (D-11).

### Integration Points
- `review.py:75` `adapter or CopilotCliAdapter()` → registry lookup keyed by
  `PREVUE_ENGINE`.
- New shared `engines/prompt.py` consumed by all adapters.
- New `engines/registry.py` (or `engines/__init__.py`) maps engine name →
  adapter class.

</code_context>

<specifics>
## Specific Ideas

- User explicitly has live access to **Copilot, Claude Code, and Cursor** — the
  two new adapters (Claude Code, Cursor) are chosen specifically because they
  can be verified on real test PRs this phase.
- The "add an engine" extension point should be visibly demonstrated by the
  Gemini skeleton (registry slot + `NotImplementedError` + intent docstring),
  not just described.

</specifics>

<deferred>
## Deferred Ideas

- **Full Gemini adapter** — registered as a skeleton this phase; functional
  implementation is a future addition (own slice once Gemini access/need is
  confirmed).
- **Rich `prevue.yml` engine config** (engine selection key, per-engine tuning) —
  Phase 6 (Reusable Workflow & Hybrid Classification) owns the consumer config
  surface. Phase 5 only introduces the minimal `PREVUE_ENGINE` env+registry.
- **Per-engine timeout/budget tuning** — deferred until latency data exists;
  revisit with Phase 6 config.
- **Engine fallback chains** — explicitly rejected for v1 (fail-closed, no
  silent fallback).

</deferred>

---

*Phase: 5-Multi-Engine Adapter Support*
*Context gathered: 2026-06-13*
