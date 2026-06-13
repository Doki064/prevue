# Phase 5: Multi-Engine Adapter Support - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 12 (5 new src modules, 3 modified src, 4 test files — 1 new conftest extension)
**Analogs found:** 12 / 12 (strong analog exists for every file — this phase is a refactor + clone)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/prevue/engines/prompt.py` (NEW) | utility | transform | `src/prevue/engines/copilot_cli.py` (lines 23–110) | exact (pure hoist) |
| `src/prevue/engines/errors.py` (NEW) | utility | n/a | `src/prevue/engines/copilot_cli.py` (lines 15–20, 54–65) | exact (pure hoist) |
| `src/prevue/engines/registry.py` (NEW) | config/factory | request-response | `src/prevue/classify/router.py` (named-module convention); RESEARCH Pattern 1 | role-match |
| `src/prevue/engines/claude_code_cli.py` (NEW) | adapter | request-response (subprocess) | `src/prevue/engines/copilot_cli.py` (whole file) | exact |
| `src/prevue/engines/cursor_cli.py` (NEW) | adapter | request-response (subprocess) | `src/prevue/engines/copilot_cli.py` (whole file) | exact |
| `src/prevue/engines/gemini_cli.py` (NEW) | adapter (skeleton) | n/a | `src/prevue/engines/base.py` + RESEARCH Gemini snippet | role-match |
| `src/prevue/engines/copilot_cli.py` (MODIFIED) | adapter | request-response | itself (slim + re-export) | exact |
| `src/prevue/review.py` (MODIFIED) | orchestration | request-response | itself (lines 11–12, 72, 75) | exact |
| `src/prevue/cli.py` (MODIFIED) | entrypoint | request-response | itself (lines 8, 32) | exact |
| `tests/test_engine_contract.py` (NEW) | test | n/a | `tests/test_copilot_adapter.py` | exact (subprocess-mock) |
| `tests/test_registry.py` (NEW) | test | n/a | `tests/test_copilot_adapter.py` (auth/error tests) | role-match |
| `tests/test_prompt.py` (NEW) | test | n/a | `tests/test_copilot_adapter.py` (TestBuildPrompt, lines 68–119) | exact |
| `tests/conftest.py` (MODIFIED) | test fixtures | n/a | itself + `test_copilot_adapter.py` helpers | exact |

## Critical Hoist Map (`copilot_cli.py` → new shared modules)

**Source file read in full:** `src/prevue/engines/copilot_cli.py` (234 lines). Below is what moves and what the post-hoist import surface must be. The non-negotiable constraint: `copilot_cli.py` MUST re-export every moved symbol so the four existing import sites stay green (verified by reading each).

### Symbols currently in `copilot_cli.py`

| Symbol | Lines | Action | Re-export from `copilot_cli.py`? |
|--------|-------|--------|----------------------------------|
| `CopilotAuthError(RuntimeError)` | 15–16 | Becomes `class CopilotAuthError(AuthError)`; `AuthError` base moves to `errors.py` | YES — `cli.py` + `test_copilot_adapter.py` import it from `copilot_cli` |
| `EngineFailure(RuntimeError)` | 19–20 | MOVE → `errors.py` | YES — `cli.py`, `review.py`-test, `test_review_flow.py`, `test_copilot_adapter.py` import it from `copilot_cli` |
| `MAX_PROMPT_BYTES = 1_000_000` | 23 | MOVE → `prompt.py` (sizing belongs with prompt) | YES — `test_copilot_adapter.py` does `monkeypatch.setattr(copilot_cli, "MAX_PROMPT_BYTES", ...)` (line 398) and imports it (line 12) |
| `OUTPUT_CONTRACT` | 25–51 | MOVE → `prompt.py` (verbatim) | YES — imported by `test_copilot_adapter.py` line 13 |
| `_sanitize_stderr(stderr, token)` | 54–65 | MOVE → `errors.py` as `sanitize_stderr(stderr, secret)` (shared, secret-param generalized) | YES — imported by `test_copilot_adapter.py` line 18 (keep name resolvable; if renamed, keep `_sanitize_stderr` alias) |
| `_safe_diff_block(patch)` | 68–71 | MOVE → `prompt.py` (verbatim — security-critical) | optional (not directly imported by tests) |
| `_escape_line(value)` | 74–76 | MOVE → `prompt.py` (verbatim) | optional |
| `_build_retry_prompt(orig, err)` | 79–87 | MOVE → `prompt.py` (verbatim) | optional |
| `_build_prompt(req)` | 90–110 | MOVE → `prompt.py` (keep name OR alias `build_prompt`) | YES — imported by `test_copilot_adapter.py` line 17 |
| `CopilotCliAdapter._invoke` | 116–144 | STAYS (per-adapter argv `["copilot", "-s", "--no-ask-user"]`) | n/a |
| `CopilotCliAdapter._degraded_result` | 146–167 | CANDIDATE to hoist into shared flow (see Shared Patterns / retry-flow) | n/a |
| `CopilotCliAdapter.review` retry-then-degrade body | 169–233 | CANDIDATE to hoist into a free function (RESEARCH Open Q1: prefer `engines/flow.py::review_with_retry`) | n/a |

### Verified existing import sites (must stay green)

- `src/prevue/cli.py:8` → `from prevue.engines.copilot_cli import CopilotAuthError, EngineFailure`
- `src/prevue/review.py:12` → `from prevue.engines.copilot_cli import CopilotCliAdapter`
- `tests/test_review_flow.py:10` → `from prevue.engines.copilot_cli import EngineFailure`
- `tests/test_copilot_adapter.py:11-19` → imports `MAX_PROMPT_BYTES, OUTPUT_CONTRACT, CopilotAuthError, CopilotCliAdapter, EngineFailure, _build_prompt, _sanitize_stderr` all from `copilot_cli`

## Pattern Assignments

### `src/prevue/engines/errors.py` (NEW, utility)

**Analog:** `copilot_cli.py` lines 15–20, 54–65.

Move `EngineFailure` and add a shared `AuthError` base. Generalize `_sanitize_stderr` to take a `secret` param (it is identical logic, lines 54–65):

```python
def _sanitize_stderr(stderr: str | bytes | None, token: str) -> str:
    """Truncate stderr and redact the auth token so it never appears in errors."""
    try:
        if isinstance(stderr, bytes):
            snippet = stderr.decode("utf-8", errors="replace")[-500:]
        else:
            snippet = (stderr or "")[-500:]
    except (UnicodeDecodeError, TypeError, AttributeError):
        snippet = "<stderr decode failed>"
    if token:
        snippet = snippet.replace(token, "[REDACTED]")
    return snippet
```

Post-hoist `errors.py` surface (RESEARCH Pattern 3): `AuthError(RuntimeError)` base, `EngineFailure(RuntimeError)`, `sanitize_stderr(stderr, secret)`. `copilot_cli.py` then: `class CopilotAuthError(AuthError): ...` and re-exports `EngineFailure`.

---

### `src/prevue/engines/prompt.py` (NEW, utility, transform)

**Analog:** `copilot_cli.py` lines 23–110 — moved **verbatim** (D-09: fencing is security-critical, no behavioral change). Move `MAX_PROMPT_BYTES`, `OUTPUT_CONTRACT`, `_safe_diff_block`, `_escape_line`, `_build_retry_prompt`, `_build_prompt`. These have no Copilot-specific logic — they operate only on `ReviewRequest`/`req.diff.files`.

Parity is enforced by `tests/test_prompt.py` (new) + the existing `TestBuildPrompt`/`TestOutputContract` in `test_copilot_adapter.py` staying green via re-export.

---

### `src/prevue/engines/registry.py` (NEW, factory, fail-closed)

**Analog:** project named-module convention (`classify/router.py`, `classify/rules.py`) + RESEARCH Pattern 1 (lines 205–240). Single source of truth for the name is each adapter's `name` class attribute.

```python
ENGINES: dict[str, type[EngineAdapter]] = {
    CopilotCliAdapter.name: CopilotCliAdapter,
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CursorAdapter.name: CursorAdapter,
    GeminiAdapter.name: GeminiAdapter,
}
DEFAULT_ENGINE = "copilot-cli"

class UnknownEngineError(ValueError): ...

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

D-04: unknown name raises naming the bad value + listing valid engines. No silent fallback.

---

### `src/prevue/engines/claude_code_cli.py` (NEW, adapter)

**Analog:** `copilot_cli.py` — clone the class shape. The ONLY differences from Copilot are: auth var, model mapping, and `_invoke` argv.

**Auth check (D-06, mirrors lines 170–175 but presence-only — A3 says no stable prefix):**
```python
key = os.environ.get("ANTHROPIC_API_KEY", "")
if not key:
    raise ClaudeAuthError("ANTHROPIC_API_KEY is not set.")
```

**`_invoke` (mirror lines 116–144; stdin like Copilot; argv per RESEARCH):**
```python
cmd = ["claude", "--bare", "-p", "--output-format", "text"]
if model:                      # req.model
    cmd += ["--model", model]
proc = subprocess.run(cmd, input=prompt, env=env, capture_output=True,
                      text=True, timeout=budget_seconds)
# same nonzero/timeout/empty handling as copilot_cli lines 133-144,
# using shared sanitize_stderr(proc.stderr, key)
```

`--bare` is mandatory (Pitfall 3: avoids loading runner CLAUDE.md/MCP, forces `ANTHROPIC_API_KEY` auth). Model goes on `--model` argv (NOT env, unlike Copilot's `COPILOT_MODEL` env at line 179).

---

### `src/prevue/engines/cursor_cli.py` (NEW, adapter)

**Analog:** `copilot_cli.py`. Differences: `CURSOR_API_KEY` presence check; argv `["cursor-agent", "-p", "--output-format", "text"]` with model on `-m`; prompt via `-f <tmpfile>` (RESEARCH Open Q2 — avoid ARG_MAX/`-p` positional hang, Pitfall 2). Read-only: omit `--force` (A4). Reuse the same timeout/nonzero/empty handling from `copilot_cli.py` lines 133–144.

**WARNING (RESEARCH security finding):** install via `curl https://cursor.com/install -fsS | bash` ONLY. Reject any `npm install -g cursor-agent` (impersonating package).

---

### `src/prevue/engines/gemini_cli.py` (NEW, adapter skeleton)

**Analog:** `base.py` EngineAdapter ABC + RESEARCH snippet (lines 391–401). D-02:
```python
class GeminiAdapter(EngineAdapter):
    """Skeleton (ENGN-04). Intended: `gemini -p "<prompt>" --output-format json`,
    model via `-m <model>` (e.g. gemini-2.5-flash), auth via GEMINI_API_KEY.
    Functional implementation deferred — see CONTEXT D-02."""
    name = "gemini-cli"

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise NotImplementedError("Gemini adapter planned — see ENGN-04")
```

---

### `src/prevue/review.py` (MODIFIED, orchestration)

**Analog:** itself. Two line-anchored edits:

- **Line 72** `model=os.environ.get("COPILOT_MODEL")` → `model=os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))` (neutral seam, additive fallback — RESEARCH Open Q3).
- **Line 75** `engine = adapter or CopilotCliAdapter()` → `engine = adapter or get_adapter(os.environ.get("PREVUE_ENGINE", DEFAULT_ENGINE))`.
- **Line 11–12** swap the direct `CopilotCliAdapter` import for `from prevue.engines.registry import DEFAULT_ENGINE, get_adapter`.

The injected-adapter path (`adapter=...`) is preserved — all `test_review_flow.py` tests pass an explicit adapter, so the registry path is production-default only.

---

### `src/prevue/cli.py` (MODIFIED, entrypoint)

**Analog:** itself, line 32. Catch the shared base so non-Copilot auth errors surface correctly (Pitfall 5):

- **Line 8** `from prevue.engines.copilot_cli import CopilotAuthError, EngineFailure` → import `EngineFailure, AuthError` from `prevue.engines.errors`.
- **Line 32** `except (EngineFailure, CopilotAuthError) as exc:` → `except (EngineFailure, AuthError) as exc:` (CopilotAuthError is now an AuthError subclass, so still caught).

---

### `tests/test_engine_contract.py` (NEW, test)

**Analog:** `tests/test_copilot_adapter.py` — lift the subprocess-mock pattern verbatim. Parametrize over `ENGINES` from the registry (RESEARCH lines 489–510). Reuse helpers from conftest.

**Mock pattern (from `test_copilot_adapter.py` lines 35–37, 319–322):**
```python
def _stdout_with_fence(*, prose=PROSE_REVIEW, payload=None) -> str:
    body = json.dumps([] if payload is None else payload)
    return f"{prose}\n\n```json\n{body}\n```"

monkeypatch.setattr(subprocess, "run",
    lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout, stderr=""))
```

Cover (parametrized over `FUNCTIONAL = [n for n in ENGINES if n != "gemini-cli"]`): valid-fence → not degraded; unparseable → retry → degrade; bad-then-good → `retried=True`; missing credential → `AuthError` pre-subprocess; correct vendor argv.

---

### `tests/test_registry.py` (NEW, test)

**Analog:** error/auth tests in `test_copilot_adapter.py` (TestAuthGuard lines 203–216). Cover: known name resolves to instance; unknown → `UnknownEngineError` naming bad value + listing valid; default `copilot-cli` when env unset; `GeminiAdapter` registered AND `review()` raises `NotImplementedError`.

---

### `tests/test_prompt.py` (NEW, test)

**Analog:** `TestBuildPrompt` (lines 68–119) + `TestOutputContract` (lines 267–306). Assert hoisted `build_prompt` output is byte-identical to pre-hoist (fencing preserved verbatim, D-09): instructions preamble, changed-file paths+status, `` ```diff `` blocks, `UNTRUSTED DATA` labels, contract-before-untrusted ordering, no PR title/body leak.

---

### `tests/conftest.py` (MODIFIED, fixtures)

**Analog:** itself + `test_copilot_adapter.py` helpers. Move shared `_stdout_with_fence` (lines 35–37), `_sample_request`/`SAMPLE_REQUEST` (lines 40–65), `VALID_FINDING` (lines 25–32), `PROSE_REVIEW` (line 23) into `conftest.py` so both `test_copilot_adapter.py` and `test_engine_contract.py` consume them (RESEARCH Wave 0 gap). Existing `FakeEngine`/`fake_engine` (lines 18–39) stay unchanged.

## Shared Patterns

### Subprocess invocation (all functional adapters)
**Source:** `copilot_cli.py` lines 116–144 (`_invoke`).
**Apply to:** claude_code_cli, cursor_cli.
Identical structure: `subprocess.run(cmd, input=prompt OR -f file, env=env, capture_output=True, text=True, timeout=budget_seconds)`; `TimeoutExpired` → `EngineFailure(...timed out...)`; nonzero → `EngineFailure(f"...exited {rc}: {sanitize_stderr(stderr, secret)}")`; empty stdout → `EngineFailure(...empty...)`. Secrets ALWAYS via `env` dict, never argv (Security V2/V7).

### Auth pre-check (all functional adapters, D-06)
**Source:** `copilot_cli.py` lines 170–175.
**Apply to:** all adapters before building prompt/spawning subprocess. Copilot keeps `github_pat_` prefix check; Claude/Cursor presence-only (A3 — no stable prefix). Each raises its own `*AuthError(AuthError)` subclass.

### Retry-then-degrade flow (all functional adapters, D-08)
**Source:** `copilot_cli.py` lines 188–233 + `_degraded_result` lines 146–167.
**Apply to:** all functional adapters via a SHARED free function (RESEARCH Open Q1 recommendation: `engines/flow.py::review_with_retry(req, invoke, ...)`) to avoid 3-way copy-paste and keep `base.py` untouched. Uses `extract_json_fence`/`validate_findings` from `parsing.py` (unchanged, D-08).

### Output parsing (all adapters, unchanged)
**Source:** `src/prevue/engines/parsing.py` (`extract_json_fence`, `validate_findings`).
**Apply to:** all functional adapters — reused as-is. Proof of agnosticism (D-08).

## No Analog Found

None. Every file maps to a strong existing analog (`copilot_cli.py` for adapters/hoist, `test_copilot_adapter.py` for tests, named-module convention for registry).

## Metadata

**Analog search scope:** `src/prevue/engines/`, `src/prevue/review.py`, `src/prevue/cli.py`, `src/prevue/classify/` (convention), `tests/`.
**Files scanned (read in full):** `engines/copilot_cli.py`, `engines/base.py`, `engines/parsing.py`, `review.py`, `cli.py`, `tests/test_copilot_adapter.py`, `tests/conftest.py`; grep on `tests/test_review_flow.py`.
**Pattern extraction date:** 2026-06-13
