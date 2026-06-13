# Phase 5: Multi-Engine Adapter Support - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 5-Multi-Engine Adapter Support
**Areas discussed:** Adapter scope, Engine selection, Per-engine auth & secrets, Agnosticism validation, Output variance, Gemini stub, Timeout

---

## Adapter Scope

| Option | Description | Selected |
|--------|-------------|----------|
| One solid + scaffold | Build one second adapter fully, scaffold the rest | |
| All three, fully | Claude Code + Cursor + Gemini all the way | |
| Two adapters | Build two fully, stub the last | ✓ |

**User's choice:** Two adapters — **Claude Code + Cursor** ("I have access both of them"). Gemini stubbed.
**Notes:** Live access to both new engines drove the choice; two data points prove agnosticism without the full three-vendor cost.

## Engine Selection Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Env var + registry | `PREVUE_ENGINE` env → name→adapter registry, default copilot-cli | ✓ |
| Introduce prevue.yml key now | Add `engine:` key to prevue.yml this phase | |
| You decide | Claude picks during planning | |

**User's choice:** Env var + registry.
**Notes:** Keeps Phase 6 config surface separate; replaces hard-coded `CopilotCliAdapter()` at review.py:75.

### Unknown engine behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed, clear error | Raise config error, list valid engines, run fails | ✓ |
| Fall back to copilot-cli | Warn and default to Copilot | |

**User's choice:** Fail-closed, clear error.

## Per-Engine Auth & Secrets

| Option | Description | Selected |
|--------|-------------|----------|
| Native per-engine env vars | ANTHROPIC_API_KEY / CURSOR_API_KEY / COPILOT_GITHUB_TOKEN | ✓ |
| Unified PREVUE_ENGINE_TOKEN | One generic var per adapter | |
| You decide | Claude picks during planning | |

**User's choice:** Native per-engine env vars.

### Credential validation

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed, per-adapter early check | Validate + format-check before subprocess | ✓ |
| Presence-only check | Verify non-empty, let CLI reject | |

**User's choice:** Fail-closed, per-adapter early check.

### Model selection

| Option | Description | Selected |
|--------|-------------|----------|
| Per-engine native model var, default each CLI's default | None pinned, env passthrough | ✓ |
| Unified PREVUE_MODEL | One var mapped per adapter | |
| You decide | Claude handles during planning | |

**User's choice:** Per-engine native model var, defaults unpinned.

## Agnosticism Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Parametrized contract suite, mocked subprocess | One suite over all adapters, no live calls | ✓ |
| Per-adapter bespoke tests only | Separate test files, no shared contract | |
| You decide | Claude designs strategy | |

**User's choice:** Parametrized contract suite, mocked subprocess.

### Live verification

| Option | Description | Selected |
|--------|-------------|----------|
| All three built adapters live | Real PR through Copilot + Claude + Cursor | |
| New adapters only | Live-test Claude Code + Cursor (Copilot done Phase 1) | ✓ |
| Defer to UAT | Contract tests now, live at UAT | |

**User's choice:** New adapters only (Claude Code + Cursor).

### Shared prompt extraction

| Option | Description | Selected |
|--------|-------------|----------|
| Hoist to shared module | OUTPUT_CONTRACT + _build_prompt + fencing reused by all | ✓ |
| Per-adapter prompt building | Each adapter owns its prompt | |
| You decide | Claude decides refactor boundary | |

**User's choice:** Hoist to shared module.

## Output Variance

| Option | Description | Selected |
|--------|-------------|----------|
| Same contract + retry-then-degrade for all | Reuse parsing.py + degrade-to-neutral | ✓ |
| Per-engine output adapters | Per-engine post-processing before parser | |
| You decide | Claude handles per adapter | |

**User's choice:** Same contract + retry-then-degrade for all.

## Gemini Stub

| Option | Description | Selected |
|--------|-------------|----------|
| Registered skeleton, raises NotImplementedError | Registry slot + intent docstring | ✓ |
| No Gemini code at all | Note in docs only | |
| Full Gemini adapter too | Build all three | |

**User's choice:** Registered skeleton, raises NotImplementedError.

## Timeout / Budget

| Option | Description | Selected |
|--------|-------------|----------|
| Keep shared 300s default | All adapters use budget_seconds=300 | ✓ |
| Per-engine default budgets now | Each adapter own default timeout | |
| You decide | Claude picks during planning | |

**User's choice:** Keep shared 300s default.

---

## Claude's Discretion

- Exact module names/layout for shared prompt module and registry (`engines/prompt.py`, `engines/registry.py` vs `__init__.py`).
- Per-adapter subprocess invocation flags for `claude -p` and `cursor-agent` — locked during planning against each CLI's headless docs.

## Deferred Ideas

- Full Gemini adapter (skeleton only this phase).
- Rich `prevue.yml` engine config — Phase 6.
- Per-engine timeout/budget tuning — deferred until latency data.
- Engine fallback chains — rejected for v1 (fail-closed).
