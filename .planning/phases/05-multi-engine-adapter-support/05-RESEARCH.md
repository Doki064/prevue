# Phase 5: Multi-Engine Adapter Support - Research

**Researched:** 2026-06-13
**Domain:** Pluggable AI engine adapters (CLI subprocess invocation), runtime registry/selection, shared prompt hoist, parametrized contract testing
**Confidence:** HIGH (CLI invocations verified against official docs; architecture verified against existing codebase)

## Summary

Phase 5 proves the `EngineAdapter` abstraction is genuinely vendor-agnostic by adding three adapters (Claude Code CLI, Cursor CLI — both functional; Gemini CLI — skeleton) behind the existing locked `EngineAdapter` ABC, selectable at runtime via a `PREVUE_ENGINE` env var routed through a name→class registry. The hard work is **not** the new adapters (each is ~60 lines mirroring `copilot_cli.py`); it is (1) hoisting the security-critical prompt/fencing machinery out of `copilot_cli.py` into a shared module so all adapters share one audited prompt-injection posture, and (2) generalizing the auth/failure classes so each adapter validates its own credential before spawning a subprocess.

All three target CLIs support the exact headless pattern the Copilot adapter already uses: a non-interactive print flag, prompt via stdin or positional arg, clean text on stdout, model selection, and a vendor-specific auth env var. **Claude Code** (`claude -p`, reads stdin, `ANTHROPIC_API_KEY`) maps almost identically to the existing Copilot stdin approach. **Cursor** (`cursor-agent -p "<prompt>" --output-format text`, `CURSOR_API_KEY`) takes the prompt positionally and `--output-format text` yields only the final answer. **Gemini** (`gemini -p`, `GEMINI_API_KEY`) is documented only enough for an accurate skeleton docstring.

**Primary recommendation:** Create `engines/prompt.py` (hoisted prompt/contract/fencing) and `engines/errors.py` (shared `AuthError`/`EngineFailure` base) and `engines/registry.py` (name→class map + `get_adapter(name)` with fail-closed error). Each new adapter is a subclass differing ONLY in: subprocess argv, auth env var + prefix check, and model-env mapping. Replace `review.py:75` `adapter or CopilotCliAdapter()` with `adapter or get_adapter(os.environ.get("PREVUE_ENGINE", "copilot-cli"))`. One parametrized pytest suite iterates the registry so any future adapter is auto-covered.

> **CRITICAL SECURITY FINDING (read before planning the install step):** The npm package named `cursor-agent` (v1.0.3, maintainer `zalab-inc`, "Task sequence creator for Cursor AI agents") is **NOT** the official Cursor CLI. The official Cursor CLI installs via `curl https://cursor.com/install -fsS | bash`. Do **not** `npm install -g cursor-agent`. See the Package Legitimacy Audit.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Build **two** new adapters fully end-to-end: **Claude Code CLI** and **Cursor CLI**. User has live access to both.
- **D-02:** **Gemini** ships as a registered skeleton: a `GeminiAdapter` class in the registry whose `review()` raises `NotImplementedError("Gemini adapter planned — see ENGN-04")`, with a docstring noting the intended CLI/auth/model.
- **D-03:** Selection via a `PREVUE_ENGINE` env var (default `copilot-cli`) mapped through a name→adapter **registry**. Replaces the hard-coded `CopilotCliAdapter()` at `review.py:75`.
- **D-04:** Unknown/unregistered `PREVUE_ENGINE` value is **fail-closed**: raise a config error naming the bad value and listing valid engines; the run fails visibly. No silent fallback to Copilot.
- **D-05:** **Native per-engine env vars** for credentials: `ANTHROPIC_API_KEY` (Claude Code), `CURSOR_API_KEY` (Cursor), `COPILOT_GITHUB_TOKEN` (Copilot, unchanged). No translation layer.
- **D-06:** **Fail-closed, per-adapter early credential check** — each adapter validates its credential is present (and format-checks where the vendor has a known prefix, e.g. Copilot's `github_pat_`) and raises an auth error BEFORE spawning the subprocess.
- **D-07:** **Per-engine native model selection**, none pinned — use each CLI's default with an env passthrough escape hatch. `ReviewRequest.model` remains the single carrier; each adapter maps it to its vendor's native model flag/var.
- **D-08:** **Same output contract + retry-then-degrade for all adapters.** Reuse engine-agnostic `parsing.py` and the existing retry-then-degrade flow for every engine.
- **D-09:** **Hoist shared prompt to a shared module.** Move `OUTPUT_CONTRACT`, `_build_prompt`, and the untrusted-data fencing (`_safe_diff_block`, `_escape_line`, `_build_retry_prompt`) out of `copilot_cli.py` into a shared module so every adapter uses identical, audited prompt-injection posture.
- **D-10:** **Keep the shared 300s default** (`ReviewRequest.budget_seconds=300`) for all adapters this phase.
- **D-11:** **Parametrized contract test suite, mocked subprocess.** One pytest suite parametrized over every registered adapter; assert each returns a valid `ReviewResult` honoring the contract including degrade, retry, and auth-fail paths. No live API calls in CI; reuse the subprocess-mock pattern from existing Copilot tests.
- **D-12:** **Live verification of new adapters only** (Claude Code + Cursor) on a real sandbox-repo test PR (Phase 1 D-11 sandbox path).

### Claude's Discretion

- Exact module names/layout for the shared prompt module and registry.
- Precise per-adapter subprocess invocation flags for Claude Code (`claude -p`) and Cursor (`cursor-agent`) — researched and locked below.
- Whether the registry lives in `engines/__init__.py` or a dedicated `engines/registry.py`. **Recommendation below: dedicated `engines/registry.py`.**

### Deferred Ideas (OUT OF SCOPE)

- **Full Gemini adapter** — skeleton only this phase.
- **Rich `prevue.yml` engine config** — Phase 6 owns the consumer config surface. Phase 5 only introduces the minimal `PREVUE_ENGINE` env+registry.
- **Per-engine timeout/budget tuning** — deferred until latency data exists.
- **Engine fallback chains** — explicitly rejected (fail-closed, no silent fallback).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENGN-04 | Additional engine adapters (Claude Code CLI, Cursor CLI, Gemini CLI) implement the same pluggable interface and are selectable via config, validating the engine abstraction beyond Copilot | Verified headless invocation + auth + model mapping for all three CLIs (Standard Stack); registry/selection pattern (Architecture Patterns); shared-prompt hoist map (Architecture Patterns); parametrized contract suite (Validation Architecture). Inherited contract ENGN-01/02/03 confirmed unchanged via reading `base.py`, `parsing.py`, `models.py`. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Subprocess only, no wrapper libraries.** The engine adapter "is ~100 lines of Python" — shell out via stdlib `subprocess`. Do NOT add any vendor SDK (`anthropic`, `openai`) or agent framework (LangChain). All three new adapters follow the Copilot pattern of `subprocess.run(...)`. `[CITED: CLAUDE.md "What NOT to Use"]`
- **pydantic models at boundaries.** `ReviewRequest → ReviewResult` is the locked contract; do not change it (ENGN-01, Phase 1 D-02).
- **No new dependencies** for this phase: the new adapters are pure stdlib + existing models. The CLIs themselves are installed in the workflow runner, not as Python deps.
- **Python 3.12 floor, run on 3.13.** ruff 0.15.x lint/format, pytest 9.0.x. Keep `from __future__ import annotations` at top of every module (existing convention).
- **Prompt-injection fencing is security-critical** — D-09 hoist must preserve the fencing verbatim so no adapter re-implements a weaker version.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Engine selection (name→class) | Orchestration (`review.py` + `engines/registry.py`) | — | Selection is an orchestration concern read from env at run start; adapters must not know about each other. |
| Subprocess invocation per vendor | Adapter (`engines/<vendor>_cli.py`) | — | The ONLY thing that legitimately differs per engine: argv, auth var, model mapping. |
| Prompt assembly + injection fencing | Shared module (`engines/prompt.py`) | — | Security-critical; must be identical across adapters (D-09). Not per-adapter. |
| Output parsing (fence extraction, validation) | Shared (`engines/parsing.py`, unchanged) | — | Already engine-agnostic (Phase 4). Reused as-is (D-08). |
| Credential validation (presence + prefix) | Adapter (early, pre-subprocess) | Shared base class for the error type | Each vendor's var/prefix differs (D-05/D-06) but the failure CLASS is shared. |
| Retry-then-degrade flow | Shared logic (base method or shared helper) | Adapter (invoke hook) | The flow is identical (D-08); only `_invoke` differs. Candidate to lift into a shared base or helper to avoid copy-paste across 3 adapters. |
| Findings → gate → comments → check | Orchestration/gate/github tiers (unchanged) | — | Criterion 4: adding adapters must require NO change here. |

## Standard Stack

This phase adds **no Python packages**. The "stack" is the set of vendor CLIs installed on the Actions runner and their verified headless invocations.

### Core (CLIs installed in the workflow runner)

| CLI | Version (verified) | Install (CI) | Auth env var | Headless invocation | Why |
|-----|--------------------|--------------|--------------|---------------------|-----|
| GitHub Copilot CLI | `@github/copilot@1.0.61` (existing) | `npm install -g @github/copilot@1.0.61` | `COPILOT_GITHUB_TOKEN` (`github_pat_` prefix) | `copilot -s --no-ask-user` (prompt via **stdin**) | Existing reference adapter (ENGN-02). Unchanged. |
| Claude Code CLI | `claude` 2.1.177 (latest on npm 2026-06-13) | `curl -fsSL https://claude.ai/install.sh \| bash` (native, recommended) OR `npm install -g @anthropic-ai/claude-code@<ver>` | `ANTHROPIC_API_KEY` | `claude -p --output-format text` (prompt via **stdin**, e.g. `printf '%s' "$prompt" \| claude -p`) | First new functional adapter (D-01). stdin + clean text stdout mirror Copilot exactly. `[VERIFIED: code.claude.com/docs/en/headless + cli-reference]` |
| Cursor CLI (`cursor-agent`) | `cursor-agent` 2026 GA | `curl https://cursor.com/install -fsS \| bash` (**NOT npm**) | `CURSOR_API_KEY` | `cursor-agent -p "<prompt>" --output-format text` (prompt **positional**) | Second new functional adapter (D-01). `[VERIFIED: cursor.com/docs/cli/headless + reference/output-format]` |
| Gemini CLI (`gemini`) | `@google/gemini-cli` 0.46.0 (npm 2026-06-13) | (skeleton — not installed this phase) | `GEMINI_API_KEY` | `gemini -p "<prompt>"` (`-m <model>`, `--output-format json`) | Skeleton only (D-02). Facts captured for the docstring. `[CITED: google-gemini.github.io/gemini-cli/docs/cli/headless.html]` |

### Per-adapter invocation detail (LOCK THESE during planning)

**Claude Code CLI** — `[VERIFIED: code.claude.com/docs/en/cli-reference & /headless]`
- Non-interactive flag: `-p` / `--print`. "Print response without interactive mode."
- Prompt: **reads stdin** in non-interactive mode (`cat build-error.txt | claude -p '...'`). This matches the existing Copilot stdin approach (`subprocess.run(cmd, input=prompt, ...)`). Use stdin to avoid ARG_MAX (the same reason Copilot uses stdin — Phase 1 P07).
- Output format: `--output-format text` is the **default** and is "plain text output of the agent's final response" → clean for the existing `extract_json_fence` parser. (Do NOT use `json`/`stream-json`; the JSON wrapper would put the model's prose+fence inside a `result` field and break the parser. Plain `text` is correct.)
- Model: `--model <alias|full>` (aliases `sonnet`, `opus`, `haiku`, `fable`, or full name e.g. `claude-sonnet-4-6`). Map `ReviewRequest.model` → `--model` arg when set; omit for vendor default (D-07).
- Permissions: review is read-only — pass **no** tools (zero-tool posture, mirroring Copilot's zero `--allow-tool`). If any permission prompt risk exists in CI, `--permission-mode dontAsk` (locked-down) or `--bare` is the safest. **Recommended: `claude --bare -p --output-format text`** — `--bare` skips auto-discovery of hooks/skills/plugins/MCP/CLAUDE.md, making the call deterministic in CI and faster; docs explicitly recommend `--bare` for scripted/CI calls. With `--bare`, auth MUST come from `ANTHROPIC_API_KEY` (it skips OAuth/keychain) — which is exactly D-05.
- Auth: `ANTHROPIC_API_KEY` env var (with `--bare`, this is the required auth path). No documented universal key prefix; treat the credential as opaque (presence check only; see D-06 note below). `[VERIFIED]`
- stdin cap: 10MB (≥ existing `MAX_PROMPT_BYTES` 1MB guard, so the existing guard is sufficient).

**Cursor CLI** — `[VERIFIED: cursor.com/docs/cli/headless, /using, /reference/output-format]`
- Non-interactive flag: `-p` / `--print`.
- Prompt: **positional argument** — `cursor-agent -p "<prompt>"` (also supports `-f <file>`). NOTE: this differs from Copilot/Claude which use stdin. For large diffs on argv, ARG_MAX is a risk — **recommend `-f <tmpfile>`** (write prompt to a temp file, pass path) to stay safe, mirroring the file-based fallback noted for Phase 6. Verify positional vs stdin behavior during the live test; a forum report notes `-p` can hang in some setups, so set the existing `budget_seconds` timeout (already done) and verify clean exit on the sandbox PR. `[CITED: forum.cursor.com — print-mode hang report — MEDIUM]`
- Output format: `--output-format text` → "only the final assistant message without any intermediate progress updates or tool call summaries" → clean for the fence parser. (Default for `-p` is `text`.) Do NOT use `json` (wraps text in a `result` field). `[VERIFIED]`
- Model: `-m` / `--model <name>` (e.g. `sonnet-4`, `sonnet-4-thinking`, `gpt-5`). Map `ReviewRequest.model` → `-m` when set; omit for default (D-07). `[CITED: cursor.com/docs/cli/using — MEDIUM]`
- File changes: `--force` allows direct file changes; for a read-only review pass **omit `--force`** (or use `--no-force`/"propose only") so the agent cannot write. Verify the exact read-only flag on the sandbox PR.
- Auth: `CURSOR_API_KEY` env var. `[VERIFIED]`
- Binary name caveat: official docs sometimes shorthand the binary as `agent`; the PATH binary from the curl installer is `cursor-agent`. **Confirm `command -v cursor-agent` on the runner during the live test.** `[ASSUMED — binary name needs runner confirmation]`

**Gemini CLI (skeleton docstring only)** — `[CITED: google-gemini.github.io/gemini-cli/docs/cli/headless.html — MEDIUM]`
- Binary: `gemini`. Headless flag: `-p` / `--prompt` (one-shot, exits after a single turn; also auto-headless in non-TTY). `--non-interactive` available for CI.
- Model: `-m <model>` (e.g. `gemini-2.5-flash`). Output: `--output-format json` available.
- Auth: `GEMINI_API_KEY` env var (CLI exits with error in non-interactive mode if absent).
- This is enough for an accurate `GeminiAdapter` docstring naming the real CLI/auth/model; `review()` raises `NotImplementedError("Gemini adapter planned — see ENGN-04")` (D-02).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `subprocess` shell-out per adapter | Vendor SDK (`anthropic`, `openai`) | Rejected by CLAUDE.md — adds dependency surface, breaks the "adapter is the portability layer" thesis, and the CLI is the documented headless path. |
| Claude `--output-format text` (default) | `--output-format json` + `--json-schema` | json wraps prose in `.result`; our parser expects prose+fence on raw stdout. Plain text keeps `parsing.py` unchanged (D-08). Revisit `--json-schema` only if fence reliability becomes a problem (out of scope). |
| Cursor prompt positional (`-p "..."`) | Cursor `-f <tmpfile>` | For large diffs, argv risks ARG_MAX. Prefer `-f` with a temp file for robustness; confirm on live test. |
| Dedicated `engines/registry.py` | Registry in `engines/__init__.py` | See recommendation below — dedicated module wins for testability and import-cycle safety. |

**Installation (workflow steps added per selected engine — Phase 6 wires selection; Phase 5 may add steps gated/commented):**
```bash
# Claude Code (native installer, recommended; auto-pins to a channel)
curl -fsSL https://claude.ai/install.sh | bash      # provides `claude`; verify `claude --version`

# Cursor CLI (official — NOT npm)
curl https://cursor.com/install -fsS | bash         # provides `cursor-agent`; verify `command -v cursor-agent`
```
*Version verification (run 2026-06-13): `npm view @anthropic-ai/claude-code version` → 2.1.177; `npm view @google/gemini-cli version` → 0.46.0; Cursor installs out-of-band via curl (no canonical npm package — see audit).*

## Package Legitimacy Audit

> This phase installs vendor CLIs on the runner (not Python packages). Audit covers the install vectors.

| Package / vector | Registry | Age | Source Repo | Verdict | Disposition |
|------------------|----------|-----|-------------|---------|-------------|
| `@github/copilot@1.0.61` | npm | GA since 2026-02 | github.com (official) | OK | Approved (existing, unchanged) |
| `@anthropic-ai/claude-code` (2.1.177) | npm | mature, updated 2026-06-13 | github.com/anthropics/claude-code (official) | OK | Approved — has `postinstall: node install.cjs` which is EXPECTED (downloads the per-platform native binary; documented behavior). Prefer the **native curl installer** for CI per official docs. |
| `curl https://claude.ai/install.sh \| bash` | n/a (official Anthropic) | n/a | claude.ai (official) | OK | Approved — recommended CI path; binaries are GPG-signed (manifest signature). |
| `curl https://cursor.com/install -fsS \| bash` | n/a (official Cursor) | n/a | cursor.com (official) | OK | Approved — the ONLY official Cursor CLI install. |
| `cursor-agent` (npm v1.0.3, maintainer `zalab-inc`) | npm | low/unknown | third-party | **SLOP / IMPERSONATION** | **REMOVED — do NOT install.** Description "Task sequence creator for Cursor AI agents" is unrelated to the official Cursor CLI. Installing it would run an unrelated third party's code with `CURSOR_API_KEY` in env. |
| `@google/gemini-cli` (0.46.0) | npm | updated 2026-06-13 | github.com/google-gemini/gemini-cli (official) | OK | Not installed this phase (skeleton). Recorded for the docstring. |

**Packages removed due to SLOP/impersonation verdict:** `cursor-agent` (npm) — use `curl https://cursor.com/install | bash` instead.
**Packages flagged as suspicious:** none beyond the above.

> **Planner action:** The Cursor install step in any workflow YAML MUST use the curl installer. If a plan task ever proposes `npm install -g cursor-agent`, that is the wrong (impersonating) package and must be rejected. Consider a `checkpoint:human-verify` on the first Cursor install step during live verification.

## Architecture Patterns

### System Architecture Diagram

```
run_review() [review.py]
   │
   │  PREVUE_ENGINE env (default "copilot-cli")
   ▼
get_adapter(name) ──► engines/registry.py
   │                     │ {name: AdapterClass}
   │                     │ unknown name ──► raise UnknownEngineError(name, valid=[...])  (FAIL-CLOSED, D-04)
   ▼
EngineAdapter instance (CopilotCli | ClaudeCode | Cursor | Gemini)
   │
   │ .review(ReviewRequest)
   ▼
adapter.review():
   1. read vendor auth env var ──► missing/bad ──► raise AuthError (pre-subprocess, D-06)
   2. build_prompt(req) ◄────────── engines/prompt.py  (SHARED: OUTPUT_CONTRACT + fencing, D-09)
   3. _invoke(prompt) ───────────► subprocess.run([vendor argv], stdin/arg, env) [PER-ADAPTER]
   4. extract_json_fence(stdout) ◄ engines/parsing.py  (SHARED, unchanged, D-08)
        │ fence error ──► build_retry_prompt ──► _invoke again ──► still bad ──► degrade (neutral)
   5. validate_findings(payload) ◄ engines/parsing.py  (SHARED)
   ▼
ReviewResult  ──► gate.py ──► github/{comments,checks}  (UNCHANGED — criterion 4)
```

### Recommended Project Structure

```
src/prevue/engines/
├── __init__.py        # thin (existing convention); optionally re-export get_adapter
├── base.py            # EngineAdapter ABC (UNCHANGED — locked)
├── errors.py          # NEW: AuthError (base), EngineFailure (shared) — moved/generalized
├── prompt.py          # NEW: OUTPUT_CONTRACT, build_prompt, _safe_diff_block, _escape_line, build_retry_prompt (D-09 hoist)
├── parsing.py         # UNCHANGED (engine-agnostic, Phase 4)
├── registry.py        # NEW: ENGINES map {name: class}, get_adapter(name), UnknownEngineError (D-03/D-04)
├── copilot_cli.py     # SLIMMED: imports from prompt.py + errors.py; keeps CopilotAuthError (subclass) + _invoke
├── claude_code_cli.py # NEW: ClaudeCodeAdapter (D-01)
├── cursor_cli.py      # NEW: CursorAdapter (D-01)
└── gemini_cli.py      # NEW: GeminiAdapter skeleton (D-02)
```

### Pattern 1: Dedicated registry module with fail-closed resolver (D-03/D-04)
**What:** A name→class dict plus a resolver that raises a clear error on unknown names.
**When to use:** Runtime selection of one implementation from a fixed set, chosen by a string from config/env.
**Recommendation — `engines/registry.py` (dedicated module), NOT `engines/__init__.py`:**
- The package already uses thin `__init__.py` files and puts logic in named modules (`classifier.py`, `router.py`, `rules.py`). A dedicated `registry.py` matches that convention.
- Avoids import cycles: `registry.py` imports each adapter; `review.py` imports `registry`. Putting the map in `__init__.py` makes every `from prevue.engines import X` import all adapters eagerly and risks cycles as adapters grow.
- Testable in isolation: the parametrized contract suite imports `ENGINES`/`get_adapter` from one place and iterates it.

```python
# Source: pattern (project convention + Python stdlib); no external lib
# engines/registry.py
from __future__ import annotations

from prevue.engines.base import EngineAdapter
from prevue.engines.claude_code_cli import ClaudeCodeAdapter
from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.engines.cursor_cli import CursorAdapter
from prevue.engines.gemini_cli import GeminiAdapter

ENGINES: dict[str, type[EngineAdapter]] = {
    CopilotCliAdapter.name: CopilotCliAdapter,
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CursorAdapter.name: CursorAdapter,
    GeminiAdapter.name: GeminiAdapter,
}

DEFAULT_ENGINE = "copilot-cli"


class UnknownEngineError(ValueError):
    """Raised when PREVUE_ENGINE names an unregistered engine (fail-closed, D-04)."""


def get_adapter(name: str) -> EngineAdapter:
    try:
        cls = ENGINES[name]
    except KeyError:
        valid = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(
            f"Unknown PREVUE_ENGINE {name!r}; valid engines: {valid}"
        ) from None
    return cls()
```
**Note:** keys come from each adapter's `name` class attribute (single source of truth), so the registry and the adapter never disagree on the name string.

### Pattern 2: Shared prompt module hoist (D-09)
**What:** Move all prompt/contract/fencing out of `copilot_cli.py` into `engines/prompt.py`; `copilot_cli.py` re-imports so its public surface is unchanged.

**Hoist map (exact — what moves, what stays):**

| Symbol | Current location | Action |
|--------|------------------|--------|
| `OUTPUT_CONTRACT` (constant) | `copilot_cli.py` | **MOVE → `prompt.py`**. Re-export from `copilot_cli.py` (`from prevue.engines.prompt import OUTPUT_CONTRACT`) — `test_copilot_adapter.py` imports it by that path. |
| `_build_prompt(req)` | `copilot_cli.py` | **MOVE → `prompt.py`** as `build_prompt` (or keep `_build_prompt` name + re-export). `test_copilot_adapter.py` imports `_build_prompt` from `copilot_cli` — re-export to keep tests green. |
| `_safe_diff_block(patch)` | `copilot_cli.py` | **MOVE → `prompt.py`** (verbatim — security-critical fencing). |
| `_escape_line(value)` | `copilot_cli.py` | **MOVE → `prompt.py`** (verbatim). |
| `_build_retry_prompt(orig, err)` | `copilot_cli.py` | **MOVE → `prompt.py`** (verbatim). |
| `MAX_PROMPT_BYTES` | `copilot_cli.py` | **DECISION:** belongs with prompt sizing → move to `prompt.py` OR keep per-adapter. Note: `test_copilot_adapter.py` does `monkeypatch.setattr(copilot_cli, "MAX_PROMPT_BYTES", ...)` and imports it from `copilot_cli`. **Keep it importable from `copilot_cli`** (re-export if moved) so that test stays green. Each adapter references `prompt.MAX_PROMPT_BYTES` (or its own) in its `review()` size guard. |
| `_sanitize_stderr(stderr, token)` | `copilot_cli.py` | **STAYS / generalize:** it redacts the auth token from stderr. Each adapter passes its own credential. Either keep in `errors.py` as a shared helper taking the secret to redact, or keep per-adapter. Recommend `errors.py` shared helper `sanitize_stderr(stderr, secret)`. |
| `CopilotAuthError` | `copilot_cli.py` | **GENERALIZE:** becomes a subclass of a shared `AuthError` in `errors.py` (see Pattern 3). Keep the `CopilotAuthError` name (imported by `cli.py` and tests). |
| `EngineFailure` | `copilot_cli.py` | **MOVE → `errors.py`** (shared by all adapters). Re-export from `copilot_cli.py` — `cli.py`, `review.py` test, and `test_copilot_adapter.py` import `EngineFailure` from `prevue.engines.copilot_cli`. |
| `CopilotCliAdapter._invoke` | `copilot_cli.py` | **STAYS** (per-adapter argv). |
| `CopilotCliAdapter._degraded_result` + retry-then-degrade body in `review()` | `copilot_cli.py` | **CANDIDATE to hoist** into a shared base method to avoid copy-pasting the retry/degrade flow across 3 adapters. See coupling note. |

**Coupling flags (make the hoist non-trivial):**
1. **`review.py:75` re-imports `CopilotCliAdapter` directly** AND `cli.py` imports `CopilotAuthError, EngineFailure` from `prevue.engines.copilot_cli`, AND `test_review_flow.py` imports `EngineFailure` from there. To keep all three green with zero churn, `copilot_cli.py` MUST re-export `EngineFailure` and `CopilotAuthError` after the hoist. (Plan a task to update imports OR add re-exports; re-exports are the lower-risk choice.)
2. **`cli.py` catches `(EngineFailure, CopilotAuthError)`** — once other adapters raise their own auth errors (e.g. `ClaudeAuthError`), `cli.py`'s except clause must catch the shared base `AuthError` instead, or it will let a `ClaudeAuthError` fall through to the generic `Exception` handler (still exit 1, but loses the specific message path). **Recommend: `cli.py` catches `(EngineFailure, AuthError)` (shared base).** This is a required edit and a good TDD target.
3. **`review.py:72`** sets `model=os.environ.get("COPILOT_MODEL")` — Copilot-specific. With multi-engine, the model carrier should be engine-neutral. Minimal Phase-5 change: read a neutral `PREVUE_MODEL` (or keep per-engine model env mapping inside each adapter, leaving `req.model` populated from a generic source). **Recommend:** `review.py` sets `model=os.environ.get("PREVUE_MODEL")` (neutral); each adapter maps `req.model` to its vendor flag. Flag for the planner — this is a small but real interface touch-point at the orchestration seam (still no change to the `ReviewRequest`/`ReviewResult` models, so criterion 4 holds).
4. **The retry-then-degrade flow in `review()` is ~40 lines and identical across adapters.** If copy-pasted into 3 adapters, a future fix touches 4 files. Recommend lifting it into a shared base method `EngineAdapter.run_with_retry(req, invoke=self._invoke)` (or a free function in `prompt.py`/a new `flow.py`). This keeps adapters to "argv + auth + model map only" (the stated goal of D-09). **However:** `base.py` is described as FINAL/locked (Phase 1 D-02) for the *interface* (`name` + `review`). Adding a concrete helper method to the ABC does not change the interface contract — but confirm with the planner whether to (a) add a non-abstract helper to `EngineAdapter`, or (b) put the shared flow in a free function the adapters call. **Recommend (b)** a free function (e.g. `prompt.run_review_flow(...)` or `flow.review_with_retry(...)`) to leave `base.py` untouched and keep the flow unit-testable in isolation.

### Pattern 3: Shared auth/failure error hierarchy (D-05/D-06)
**What:** One shared `AuthError` base + per-adapter subclasses; one shared `EngineFailure`.
```python
# Source: pattern (stdlib exceptions). engines/errors.py
from __future__ import annotations

class AuthError(RuntimeError):
    """Base: a required engine credential is missing or malformed (pre-subprocess)."""

class EngineFailure(RuntimeError):
    """An engine CLI failed, timed out, or returned unusable output."""

# copilot_cli.py keeps the specific name as a subclass:
# class CopilotAuthError(AuthError): ...
```
**Per-adapter credential check shape (D-06):**
```python
# In each adapter.review(), BEFORE building prompt / spawning subprocess:
key = os.environ.get("ANTHROPIC_API_KEY", "")        # Claude Code
if not key:
    raise ClaudeAuthError("ANTHROPIC_API_KEY is not set.")
# Cursor: CURSOR_API_KEY presence check.
# Copilot KEEPS its github_pat_ prefix check (it has a known prefix).
```
**Format-check guidance (D-06 "where the vendor has a known prefix"):**
- Copilot: `github_pat_` prefix — KEEP existing check.
- Anthropic: keys historically start `sk-ant-` — but this is **not guaranteed stable** and `--bare` accepts any value. **Recommend presence-only check for Claude/Cursor** unless the live test confirms a stable prefix. Tag a prefix check `[ASSUMED]` if added; presence-only is the safe default. `[ASSUMED — sk-ant- prefix stability unverified]`
- Cursor: no documented stable key prefix → presence-only.

### Pattern 4: New adapter shape (minimal, mirrors Copilot)
```python
# Source: pattern derived from existing copilot_cli.py. engines/claude_code_cli.py
class ClaudeCodeAdapter(EngineAdapter):
    name = "claude-code-cli"

    def _invoke(self, prompt, env, secret, budget_seconds) -> str:
        cmd = ["claude", "--bare", "-p", "--output-format", "text"]
        if model:                       # from req.model, set on env or as --model arg
            cmd += ["--model", model]
        proc = subprocess.run(cmd, input=prompt, env=env, capture_output=True,
                              text=True, timeout=budget_seconds)
        # ... same nonzero/timeout/empty handling as Copilot, using shared sanitize_stderr
        return proc.stdout.strip()

    def review(self, req): ...   # auth check → build_prompt → shared retry-then-degrade flow
```

### Anti-Patterns to Avoid
- **`npm install -g cursor-agent`** — impersonating package (see audit). Use the curl installer.
- **Re-implementing prompt fencing per adapter** — defeats D-09; one audited copy in `prompt.py` only.
- **Using `--output-format json` for Claude/Cursor** — wraps prose in a `result` field and breaks the prose+fence parser. Use `text`.
- **Silent fallback to Copilot on unknown engine** — violates D-04. Must raise `UnknownEngineError`.
- **Adding a vendor SDK dependency** — violates CLAUDE.md; subprocess only.
- **Changing `ReviewRequest`/`ReviewResult`/`EngineAdapter` interface** — violates criterion 4 and Phase 1 D-02 lock.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vendor API calls | Custom HTTP client / SDK wrapper | The vendor CLI via `subprocess` | CLAUDE.md mandate; the CLI is the documented headless path and the portability boundary. |
| Output parsing | New per-adapter parser | Existing `engines/parsing.py` | Already engine-agnostic (Phase 4, D-08); reusing it IS the proof of agnosticism. |
| Prompt-injection fencing | Per-adapter fence logic | Hoisted `engines/prompt.py` | Security-critical; one audited copy (D-09). |
| Engine selection | if/elif on engine name | `registry.py` dict + `get_adapter` | Extensible (Gemini slot), testable, fail-closed in one place. |
| Retry/degrade flow | Copy-paste into each adapter | Shared free function | One fix site; keeps adapters to argv+auth+model only. |

**Key insight:** In this phase, *more shared code = more proof*. Every line the new adapters reuse (parser, fencing, retry flow, error types) is evidence the abstraction holds. The new adapters should be almost boring.

## Runtime State Inventory

> This is a refactor/extension phase (hoisting code + adding modules). State inventory:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — stateless reusable workflow; no DB/datastore keys reference engine names. | None. |
| Live service config | The `.github/workflows/review.yml` hard-codes the Copilot install + `COPILOT_GITHUB_TOKEN` env. Adding engines means the workflow needs per-engine install + secret pass-through. Phase 5 may add commented/gated steps; Phase 6 wires `prevue.yml` selection. | Workflow YAML edit (add Claude/Cursor install steps + `ANTHROPIC_API_KEY`/`CURSOR_API_KEY` secrets) — minimal for live verify; full wiring is Phase 6. |
| OS-registered state | None. | None. |
| Secrets/env vars | `review.py:72` reads `COPILOT_MODEL` (Copilot-specific). New code reads `PREVUE_ENGINE` (new), `ANTHROPIC_API_KEY`, `CURSOR_API_KEY`, optionally `PREVUE_MODEL`. No secret renames — additive. | Add new secrets to the workflow for the engines being live-verified; consider renaming `COPILOT_MODEL`→`PREVUE_MODEL` at the orchestration seam (code edit, additive — keep reading `COPILOT_MODEL` as fallback to avoid breaking Phase 1/4). |
| Build artifacts | None — no compiled artifacts; `uv.lock` unchanged (no new Python deps). | None. |

**Import-surface state (the real "runtime state" for this refactor):** Three call sites import from `prevue.engines.copilot_cli`: `review.py` (`CopilotCliAdapter`), `cli.py` (`CopilotAuthError, EngineFailure`), `tests/test_review_flow.py` (`EngineFailure`), and `tests/test_copilot_adapter.py` (`MAX_PROMPT_BYTES, OUTPUT_CONTRACT, CopilotAuthError, CopilotCliAdapter, EngineFailure, _build_prompt, _sanitize_stderr`). After the hoist, `copilot_cli.py` MUST re-export these names so existing imports/tests stay green (verified by reading all four files).

## Common Pitfalls

### Pitfall 1: Breaking existing Copilot tests during the hoist
**What goes wrong:** Moving `OUTPUT_CONTRACT`/`_build_prompt`/`EngineFailure`/`MAX_PROMPT_BYTES` out of `copilot_cli.py` breaks `test_copilot_adapter.py` (imports them by that path) and `test_review_flow.py` (imports `EngineFailure`).
**Why it happens:** Tests pin the import path; `monkeypatch.setattr(copilot_cli, "MAX_PROMPT_BYTES", ...)` requires the name to live on `copilot_cli`.
**How to avoid:** Re-export every moved symbol from `copilot_cli.py` (`from prevue.engines.prompt import OUTPUT_CONTRACT, _build_prompt, MAX_PROMPT_BYTES`; `from prevue.engines.errors import EngineFailure`). Run the full suite after the hoist commit (TDD: hoist is a pure refactor — tests must stay green BEFORE adding new adapters).
**Warning signs:** `ImportError` in collection; `monkeypatch` AttributeError.

### Pitfall 2: Cursor `-p` hang / non-release of terminal
**What goes wrong:** A community report notes `cursor-agent -p` can hang indefinitely in some environments and "does not release the terminal."
**Why it happens:** Streaming/TTY assumptions; possibly missing `--output-format text` or an interactive auth fallback when `CURSOR_API_KEY` is absent/invalid.
**How to avoid:** Always pass `--output-format text`, ensure `CURSOR_API_KEY` is set (pre-subprocess check, D-06), rely on the existing `budget_seconds` timeout (already wired), and verify clean exit on the sandbox PR before trusting CI. Consider `-f <tmpfile>` for the prompt.
**Warning signs:** Timeout fires on every Cursor run; empty stdout.

### Pitfall 3: Claude `claude -p` loading local context in CI
**What goes wrong:** Without `--bare`, `claude -p` auto-discovers hooks/skills/MCP/CLAUDE.md from the runner's working dir and `~/.claude`, making output non-deterministic and slower, and could read the consumer's repo files.
**Why it happens:** Default `-p` loads the same context an interactive session would.
**How to avoid:** Use `claude --bare -p --output-format text`. `--bare` is the documented CI-recommended mode and forces auth via `ANTHROPIC_API_KEY` (which is D-05). `[VERIFIED]`
**Warning signs:** Review output references repo files not in the diff; long latencies; auth via keychain instead of env.

### Pitfall 4: Cursor impersonation package
**What goes wrong:** `npm install -g cursor-agent` installs an unrelated third-party package and runs it with `CURSOR_API_KEY` in env.
**How to avoid:** Use `curl https://cursor.com/install -fsS | bash`. Verify `command -v cursor-agent` resolves to the official binary on the runner.
**Warning signs:** `cursor-agent --version` shows an unexpected version/description.

### Pitfall 5: `cli.py` swallows new auth errors generically
**What goes wrong:** `cli.py` catches `(EngineFailure, CopilotAuthError)`; a `ClaudeAuthError`/`CursorAuthError` falls into the generic `except Exception` — still exit 1, but the specific auth message path is lost and the distinction blurs.
**How to avoid:** Catch the shared base `(EngineFailure, AuthError)`. TDD target.

## Code Examples

### Replacing the hard-coded adapter at review.py:75 (D-03)
```python
# Source: existing review.py (line 75) — minimal change
# before:  engine = adapter or CopilotCliAdapter()
# after:
from prevue.engines.registry import DEFAULT_ENGINE, get_adapter
...
engine = adapter or get_adapter(os.environ.get("PREVUE_ENGINE", DEFAULT_ENGINE))
```
*Note: `run_review(adapter=...)` keeps the injected-adapter path for tests (all `test_review_flow.py` tests pass an explicit adapter). The registry path is the production default.*

### Gemini skeleton (D-02)
```python
# Source: pattern. engines/gemini_cli.py
class GeminiAdapter(EngineAdapter):
    """Skeleton (ENGN-04). Intended: `gemini -p "<prompt>" --output-format json`,
    model via `-m <model>` (e.g. gemini-2.5-flash), auth via GEMINI_API_KEY.
    Functional implementation deferred — see CONTEXT D-02."""
    name = "gemini-cli"

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise NotImplementedError("Gemini adapter planned — see ENGN-04")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Claude Code via `npm install -g @anthropic-ai/claude-code` | Native installer `curl https://claude.ai/install.sh \| bash` (npm "deprecated" / no longer primary) | 2026 | Prefer native installer in CI; npm still works (installs same native binary via postinstall). |
| Cursor as IDE only | `cursor-agent` headless CLI with `-p`/`--output-format` | 2025–2026 GA | Enables the second functional adapter. |
| `claude -p` loads full local context | `claude --bare -p` recommended for scripts/CI; "will become default for `-p`" | 2026 | Use `--bare` now for deterministic CI. |

**Deprecated/outdated:**
- npm `@anthropic-ai/claude-code` as the *primary* install path — superseded by native installer (still supported).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Cursor PATH binary is `cursor-agent` (docs sometimes shorthand `agent`) | Standard Stack | Wrong argv → command-not-found on runner. Mitigate: `command -v cursor-agent` during live verify. |
| A2 | Cursor model values `sonnet-4`/`gpt-5` valid for `-m` | Standard Stack | Wrong model flag value → error or default. Low risk (D-07 allows default; omit `-m` when unset). |
| A3 | Anthropic key prefix `sk-ant-` is not stable enough to format-check | Pattern 3 | If a prefix check is added and the prefix changes, valid keys rejected. Mitigate: presence-only check. |
| A4 | Cursor read-only is achieved by omitting `--force` (vs an explicit `--no-force`/read-only flag) | Standard Stack | Agent could attempt file writes. Mitigate: confirm read-only flag on live test; review is diff-in/findings-out, no repo checkout of PR head anyway. |
| A5 | Gemini headless facts (binary `gemini`, `-p`, `GEMINI_API_KEY`, `-m`) | Standard Stack (skeleton) | Only affects a docstring; no runtime impact this phase. |

**Confirmation path:** A1–A4 are confirmed during the D-12 live sandbox PR verification of the Claude and Cursor adapters.

## Open Questions (RESOLVED)

1. **Where does the shared retry-then-degrade flow live?**
   - What we know: It's ~40 identical lines; copy-pasting across 3 adapters is bad.
   - What's unclear: Add a non-abstract helper to `EngineAdapter` (base.py is "FINAL" for the interface) vs a free function.
   - **RESOLVED:** Free function (e.g. `engines/flow.py::review_with_retry(req, invoke, build_prompt, ...)`), leaving `base.py` untouched and the flow independently unit-testable. Consumed by plan 05-01 (flow.py) + 05-02/05-03 adapters delegate to it.

2. **Cursor prompt: positional arg vs `-f <tmpfile>`?**
   - What we know: docs show positional `-p "<prompt>"`; `-f` reads a file. Copilot/Claude use stdin to dodge ARG_MAX.
   - **RESOLVED:** use `-f` with a temp file for robustness; confirm during live test. Consumed by plan 05-03-T1.

3. **`COPILOT_MODEL` → `PREVUE_MODEL` rename at review.py:72?**
   - **RESOLVED:** read `PREVUE_MODEL` with `COPILOT_MODEL` as fallback (additive, no breakage). Small orchestration-seam edit; does not touch the pydantic contract. Consumed by plan 05-01-T3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `claude` CLI | Claude Code adapter (live verify) | ✗ on dev box (install in workflow/sandbox) | 2.1.177 (latest) | curl native installer; npm install |
| `cursor-agent` CLI | Cursor adapter (live verify) | ✗ on dev box | GA 2026 | curl official installer ONLY |
| `gemini` CLI | Gemini adapter | n/a (skeleton — not invoked) | 0.46.0 | — |
| `node`/`npm` | CLI installs (npm path) | ✓ (Node 22 preinstalled on ubuntu-latest) | — | — |
| `pytest` 9.0.x, `ruff` 0.15.x | Contract suite + lint | ✓ (uv-managed) | — | — |

**Missing dependencies with no fallback:** none — all installable in-workflow.
**Missing dependencies with fallback:** Claude/Cursor CLIs (not on dev box) — installed on the sandbox runner for D-12 live verification. CI contract suite mocks subprocess, so CI does NOT need the CLIs installed (D-11).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.x + pytest-cov 7.1.x (existing) |
| Config file | `pyproject.toml` (existing pytest config) |
| Quick run command | `uv run pytest tests/test_engine_contract.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENGN-04 | Registry resolves a known name → adapter instance | tdd / unit | `pytest tests/test_registry.py -k resolves -x` | ❌ Wave 0 |
| ENGN-04 | Unknown `PREVUE_ENGINE` → `UnknownEngineError` naming bad value + listing valid (fail-closed, D-04) | tdd / unit | `pytest tests/test_registry.py -k unknown -x` | ❌ Wave 0 |
| ENGN-04 | Default engine is `copilot-cli` when env unset (D-03) | tdd / unit | `pytest tests/test_registry.py -k default -x` | ❌ Wave 0 |
| ENGN-04 | Each adapter: missing credential → `AuthError` BEFORE subprocess (D-06) — parametrized over registry (Copilot excluded from "missing key" if prefix-checked) | tdd / unit | `pytest tests/test_engine_contract.py -k auth -x` | ❌ Wave 0 |
| ENGN-04 | Each adapter: valid fence stdout → valid `ReviewResult`, not degraded (contract) | tdd / unit | `pytest tests/test_engine_contract.py -k valid_fence -x` | ❌ Wave 0 |
| ENGN-04 | Each adapter: unparseable stdout → retry → still bad → degraded neutral (D-08) | tdd / unit | `pytest tests/test_engine_contract.py -k degrade -x` | ❌ Wave 0 |
| ENGN-04 | Each adapter: bad-then-good retry sets `retried=True` (D-08) | tdd / unit | `pytest tests/test_engine_contract.py -k retry -x` | ❌ Wave 0 |
| ENGN-04 | Each adapter passes correct vendor argv (claude `--bare -p --output-format text`; cursor `-p --output-format text`) | unit | `pytest tests/test_engine_contract.py -k argv -x` | ❌ Wave 0 |
| ENGN-04 | Gemini adapter is registered AND `review()` raises `NotImplementedError` (D-02) | tdd / unit | `pytest tests/test_registry.py -k gemini -x` | ❌ Wave 0 |
| ENGN-04 | Hoisted prompt: `build_prompt` output identical to pre-hoist (fencing preserved verbatim, D-09) | tdd / unit | `pytest tests/test_prompt.py -x` (+ existing `test_copilot_adapter.py` stays green) | ❌ Wave 0 |
| ENGN-04 | `review.py` resolves adapter via `PREVUE_ENGINE` registry path when no adapter injected (D-03) | unit | `pytest tests/test_review_flow.py -k engine_selection -x` | ⚠️ extend existing |
| ENGN-04 | `cli.py` catches shared `AuthError` for non-Copilot adapters | tdd / unit | `pytest tests/test_cli.py -k auth -x` (or extend) | ⚠️ extend |
| ENGN-04 | Criterion 4: gate/findings/comments/checks unchanged | regression | `uv run pytest -q` (whole suite green) | ✓ existing |
| ENGN-04 | Live: Claude Code adapter reviews a real sandbox PR end-to-end | manual / live | Sandbox test PR (D-12) — see Live Verification | n/a (manual) |
| ENGN-04 | Live: Cursor adapter reviews a real sandbox PR end-to-end | manual / live | Sandbox test PR (D-12) | n/a (manual) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_engine_contract.py tests/test_registry.py tests/test_prompt.py -x -q`
- **Per wave merge:** `uv run pytest -q` (full suite — guards criterion 4 / no-regression)
- **Phase gate:** Full suite green + two live sandbox verifications (Claude + Cursor) pass before `/gsd-verify-work`.

### Parametrized contract suite design (D-11)
One suite (`tests/test_engine_contract.py`) parametrizes over the registry so a newly added adapter is auto-covered:
```python
# Source: pattern derived from tests/test_copilot_adapter.py + conftest FakeEngine
import pytest, subprocess
from types import SimpleNamespace
from prevue.engines.registry import ENGINES

FUNCTIONAL = [n for n in ENGINES if n != "gemini-cli"]  # Gemini raises NotImplementedError

@pytest.fixture
def set_all_engine_keys(monkeypatch):
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "github_pat_x...")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")

@pytest.mark.parametrize("name", FUNCTIONAL)
def test_valid_fence_returns_result(name, monkeypatch, set_all_engine_keys):
    monkeypatch.setattr(subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=STDOUT_WITH_FENCE, stderr=""))
    result = ENGINES[name]().review(SAMPLE_REQUEST)
    assert result.degraded is False and len(result.findings) == 1
```
The mock pattern is lifted directly from `test_copilot_adapter.py` (`monkeypatch.setattr(subprocess, "run", _stub)` returning a `SimpleNamespace(returncode, stdout, stderr)`; `_stdout_with_fence` helper). Parametrizing over `ENGINES.keys()` means adding a 5th adapter to the registry automatically subjects it to the full contract (valid-fence, degrade, retry, auth-fail, argv) with zero new test code — structurally enforcing "all adapters honor one contract."

### Wave 0 Gaps
- [ ] `tests/test_engine_contract.py` — parametrized contract suite (covers ENGN-04 valid/degrade/retry/auth/argv across registry)
- [ ] `tests/test_registry.py` — resolve/default/unknown-fail-closed/gemini-skeleton
- [ ] `tests/test_prompt.py` — hoisted prompt parity + fencing preserved (D-09)
- [ ] Shared subprocess-mock helpers (move `_stdout_with_fence`, `SAMPLE_REQUEST` into `conftest.py` so the contract suite and `test_copilot_adapter.py` share them)
- [ ] Framework install: none needed (pytest/ruff already present)

## Security Domain

> `security_enforcement` not disabled in config → included.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Per-adapter credential presence check before subprocess (D-06); secrets passed via env, never argv. |
| V3 Session Management | no | Stateless reusable workflow. |
| V4 Access Control | partial | Read-only review posture: zero tools (Copilot), `--bare` (Claude), no `--force` (Cursor) — agents cannot write repo files. |
| V5 Input Validation | yes | `parsing.py` strict pydantic `Finding` validation (existing); diff is untrusted input fenced in `prompt.py`. |
| V6 Cryptography | no | No crypto introduced; rely on TLS in CLI installers (curl `-fsSL`, GPG-signed Claude binaries). |
| V7 Error Handling/Logging | yes | `sanitize_stderr` redacts the auth secret from `EngineFailure` messages — generalize per-adapter so each secret is redacted (existing Copilot pattern). |

### Known Threat Patterns for multi-engine subprocess adapters
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via untrusted diff | Tampering | Shared `prompt.py` UNTRUSTED-DATA fencing (`_safe_diff_block`, `_escape_line`) preserved verbatim for ALL adapters (D-09). |
| Credential leak in error/stderr | Information Disclosure | `sanitize_stderr(stderr, secret)` shared helper redacts the per-adapter secret. |
| Impersonating CLI package (`cursor-agent` npm) | Tampering / Supply chain | Install via official curl installer only; reject npm `cursor-agent`. |
| Secret on argv (process listing leak) | Information Disclosure | Pass credentials via env dict (existing pattern), never as CLI args. |
| Agent file-write on runner | Elevation/Tampering | Read-only posture per adapter (`--bare` / no `--force` / zero tools); diff-only review, no PR-head checkout (SECR-01). |

## Sources

### Primary (HIGH confidence)
- `src/prevue/engines/{base,copilot_cli,parsing}.py`, `models.py`, `review.py`, `cli.py`, `tests/{test_copilot_adapter,test_review_flow}.py`, `conftest.py` — read in full; authoritative for the existing contract and import surface.
- https://code.claude.com/docs/en/cli-reference — `-p/--print`, `--output-format text/json`, `--model`, `--bare`, `--permission-mode`, `--allowedTools`, `--dangerously-skip-permissions`. (HIGH, official)
- https://code.claude.com/docs/en/headless — stdin piping (`cat ... | claude -p`), `--bare` recommended for CI + forces `ANTHROPIC_API_KEY` auth, 10MB stdin cap, `text` is plain final response. (HIGH, official)
- https://code.claude.com/docs/en/setup — native installer `curl -fsSL https://claude.ai/install.sh | bash`, npm path + postinstall behavior, GPG-signed binaries. (HIGH, official)
- https://cursor.com/docs/cli/headless — `cursor-agent`/`agent -p`, `CURSOR_API_KEY`, `--output-format text` default. (HIGH, official)
- https://cursor.com/docs/cli/reference/output-format — `text` = only final assistant message (clean for parsing); `json` wraps text in `.result`. (HIGH, official)
- https://cursor.com/docs/cli/overview — official install `curl https://cursor.com/install -fsS | bash` (NOT npm). (HIGH, official)
- `npm view` (2026-06-13): `@anthropic-ai/claude-code` 2.1.177 (+ `postinstall: node install.cjs`), `@google/gemini-cli` 0.46.0, `cursor-agent` npm = third-party `zalab-inc` package (impersonation). (HIGH, registry-verified)

### Secondary (MEDIUM confidence)
- WebSearch: Cursor `-m`/`--model` values (`sonnet-4`, `gpt-5`), `--force`/`--yolo`. Cross-checked with official output-format page.
- https://google-gemini.github.io/gemini-cli/docs/cli/headless.html — Gemini `-p`/`--prompt`, `-m`, `--output-format json`, `GEMINI_API_KEY`. (skeleton-only)

### Tertiary (LOW confidence)
- https://forum.cursor.com — `cursor-agent -p` hang / terminal-non-release reports (pitfall, mitigated by timeout + `--output-format text`).
- https://playbooks.com/skills/openclaw/skills/cursor-cli-headless — community cursor headless skill (`-f` file input, `-o` format).

## Metadata

**Confidence breakdown:**
- Standard stack (CLI invocations): HIGH for Claude & Cursor (official docs verified); MEDIUM for Cursor model values + binary-name shorthand (verify on live); MEDIUM for Gemini (skeleton-only, doc-cited).
- Architecture (hoist map, registry): HIGH — derived from reading every affected source file and the existing test imports.
- Pitfalls: HIGH for hoist/import breakage and Claude `--bare`; MEDIUM for Cursor hang (community report).

**Research date:** 2026-06-13
**Valid until:** 2026-07-13 (CLIs are fast-moving — re-verify Claude/Cursor flags if more than ~30 days elapse before execution).
