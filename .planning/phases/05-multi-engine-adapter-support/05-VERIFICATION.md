---
phase: 05-multi-engine-adapter-support
verified: 2026-06-13T19:00:00Z
status: passed
score: 11/11 must-haves verified (1 override)
overrides_applied: 1
overrides:
  - must_have: "D-12 Claude Code adapter live E2E on sandbox PR"
    reason: "ANTHROPIC_API_KEY unavailable (Pro subscription). Adapter contract tests green; Cursor + unknown-engine live UAT passed. Environmental constraint, not code gap."
    accepted_by: "user"
    accepted_at: "2026-06-13T19:00:00Z"
re_verification:
  previous_status: human_needed
  previous_score: 10/11 automated
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Sandbox PR with PREVUE_ENGINE=claude-code-cli and ANTHROPIC_API_KEY — confirm sticky comment + check, diff-only review, clean exit"
    expected: "Review references only PR diff content (--bare); sticky upsert + prevue/review check published"
    result: override_accepted
    why_human: "D-12 live CLI + real auth; UAT skipped (no ANTHROPIC_API_KEY). Override accepted — contract suite green."
  - test: "Sandbox PR with PREVUE_ENGINE=cursor-cli and CURSOR_API_KEY — confirm sticky + check, no hang, no repo writes"
    expected: "cursor-agent resolves via official installer; completes within budget_seconds; read-only (no --force)"
    why_human: "D-12 live CLI; UAT pass on PR #11 — spot re-run optional for regression confidence"
  - test: "Sandbox run with PREVUE_ENGINE=typo — confirm visible UnknownEngineError failure"
    expected: "Workflow fails closed naming bad value and listing valid engines"
    why_human: "D-04 live fail-closed; UAT pass — spot re-run optional for regression confidence"
---

# Phase 5: Multi-Engine Adapter Support — Verification Report

**Phase Goal:** EngineAdapter abstraction proven engine-agnostic — Claude Code, Cursor, and Gemini skeleton registered, selectable via PREVUE_ENGINE, sharing prompt/flow/parsing

**Verified:** 2026-06-13T19:00:00Z  
**Status:** passed (1 override — Claude D-12 live E2E environmental skip accepted)  
**Score:** 11/11 must-haves verified

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Shared prompt/errors/flow hoisted; Copilot green through registry (D-09, D-03) | ✓ VERIFIED | `prompt.py`, `errors.py`, `flow.py` substantive; `copilot_cli.py` re-exports from `prompt.py`; `review.py:77` uses `get_adapter(...)`; `test_prompt.py`, `test_review_flow::test_engine_selection_via_prevue_engine` |
| 2 | Unknown PREVUE_ENGINE fail-closed (D-04) | ✓ VERIFIED | `registry.py:21-30` `UnknownEngineError`; `test_unknown_engine_raises_with_valid_names`; UAT test 3 pass |
| 3 | ClaudeCodeAdapter registered, contract suite green (D-01) | ✓ VERIFIED | `claude_code_cli.py` `--bare -p`; `registry.py:15`; contract tests pass (`-k "claude-code-cli and valid_fence"`) |
| 4 | CursorAdapter registered, contract suite green (D-01) | ✓ VERIFIED | `cursor_cli.py` `-f` tempfile, no `--force`; `registry.py:16`; contract + UAT test 2 pass |
| 5 | Gemini skeleton raises NotImplementedError (D-02) | ✓ VERIFIED | `gemini_cli.py:22`; `test_gemini_registered_and_raises_not_implemented` |
| 6 | Workflow curl installs only; npm impostor rejected | ✓ VERIFIED | `review.yml:47-52` curl for Claude/Cursor; `test_workflow_yaml.py` asserts `cursor.com/install` present and `npm install -g cursor-agent` absent |
| 7 | ROADMAP SC: three adapters + contract tests | ✓ VERIFIED | All four in `ENGINES`; `test_engine_contract.py` parametrizes `FUNCTIONAL` (excludes gemini-cli skeleton) |
| 8 | ROADMAP SC: engine selectable via config; unknown fails closed | ✓ VERIFIED | `review.yml:35-39` resolves `vars.PREVUE_ENGINE`; registry fail-closed; live UAT typo pass |
| 9 | ROADMAP SC: each adapter headless on Actions with own auth env | PASSED (override) | Cursor live pass (UAT); Claude live override accepted (contract green, no key); Gemini skeleton N/A; workflow maps per-engine secrets |
| 10 | ROADMAP SC: no orchestration/findings/gate interface leak | ✓ VERIFIED | `git diff 9a1e2f7..78c4951` — gate/checks/comments formatting-only; `review.py` registry wiring only |
| 11 | D-12: both new adapters live E2E on sandbox PR | PASSED (override) | Cursor pass + unknown pass (UAT); Claude override accepted — contract suite green, `ANTHROPIC_API_KEY` unavailable |

**Score:** 11/11 truths verified (1 override)

### Roadmap Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Three additional adapters implement EngineAdapter + pass contract tests | ✓ | Claude, Cursor functional; Gemini skeleton registered; contract suite green |
| 2 | Active engine selectable via config; unknown fails closed | ✓ | `PREVUE_ENGINE` in workflow + registry |
| 3 | Each adapter headless on Actions with own auth + shared retry-degrade | PASSED (override) | Automated contract green; Claude live override accepted (environmental) |
| 4 | No orchestration/findings/gate layer changes (abstraction held) | ✓ | Only registry wiring + ruff formatting |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/prompt.py` | Hoisted prompt fencing (D-09) | ✓ VERIFIED | `build_prompt`, `_build_prompt`, OUTPUT_CONTRACT |
| `src/prevue/engines/errors.py` | Shared AuthError, EngineFailure | ✓ VERIFIED | Used by all adapters + `cli.py` |
| `src/prevue/engines/flow.py` | Shared review_with_retry | ✓ VERIFIED | Called from copilot/claude/cursor |
| `src/prevue/engines/registry.py` | ENGINES + fail-closed get_adapter | ✓ VERIFIED | 4 adapters registered |
| `src/prevue/engines/claude_code_cli.py` | ClaudeCodeAdapter | ✓ VERIFIED | Auth pre-subprocess, shared flow |
| `src/prevue/engines/cursor_cli.py` | CursorAdapter | ✓ VERIFIED | Tempfile prompt, no `--force` |
| `src/prevue/engines/gemini_cli.py` | Skeleton NotImplementedError | ✓ VERIFIED | D-02 |
| `src/prevue/engines/copilot_cli.py` | Re-export shims | ✓ VERIFIED | Imports from `prompt.py` |
| `.github/workflows/review.yml` | Per-engine curl install + secrets | ✓ VERIFIED | Selective case install |
| `tests/test_engine_contract.py` | Parametrized contract suite | ✓ VERIFIED | 259 tests collected |

**gsd-tools verify.artifacts:** 05-01 6/6, 05-02 2/2, 05-03 3/3 — all passed

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `review.py` | `registry.py` | `get_adapter(PREVUE_ENGINE)` | ✓ WIRED | Line 77 |
| `copilot_cli.py` | `prompt.py` | re-export shim | ✓ WIRED | `from prevue.engines.prompt import` |
| `cli.py` | `errors.py` | `except (EngineFailure, AuthError)` | ✓ WIRED | Line 32 |
| `claude_code_cli.py` | `flow.py` | `review_with_retry` | ✓ WIRED | Line 61 |
| `claude_code_cli.py` | `prompt.py` | `build_prompt` | ✓ WIRED | Line 11, 65 |
| `cursor_cli.py` | `flow.py` | `review_with_retry` | ✓ WIRED | Line 71 |
| `registry.py` | `claude_code_cli.py` / `cursor_cli.py` | ENGINES map | ✓ WIRED | Lines 15-16 |
| `review.yml` | Cursor installer | `curl cursor.com/install` | ✓ WIRED | Line 51 (gsd-tools regex false negative; string present) |

**gsd-tools verify.key-links:** 05-01 3/3, 05-02 3/3, 05-03 2/3 (cursor.com/install link false negative — manually verified)

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `ClaudeCodeAdapter.review` | `ReviewResult` | mocked subprocess in contract tests; live CLI in UAT | Yes (automated); live skipped | ⚠️ STATIC for live |
| `CursorAdapter.review` | `ReviewResult` | contract tests + UAT PR #11 | Yes | ✓ FLOWING |
| `run_review` engine selection | `engine` | `PREVUE_ENGINE` env → registry | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite exists | `uv run pytest --collect-only -q` | 259 collected | ✓ PASS |
| Unknown engine fail-closed | `pytest tests/test_registry.py::test_unknown_engine_raises_with_valid_names -q` | 1 passed | ✓ PASS |
| Claude contract | `pytest tests/test_engine_contract.py -k "claude-code-cli and valid_fence" -q` | 1 passed | ✓ PASS |
| Cursor contract | `pytest tests/test_engine_contract.py -k "cursor-cli and valid_fence" -q` | 1 passed | ✓ PASS |
| Workflow guards | `pytest tests/test_workflow_yaml.py -q` | 16 passed | ✓ PASS |
| Full regression | `uv run pytest -q` | 259 passed in 0.76s | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no probe scripts declared or conventional `scripts/*/tests/probe-*.sh` for this phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENGN-04 | 05-01, 05-02, 05-03 | Additional adapters (Claude, Cursor, Gemini) pluggable + selectable via config | ✓ SATISFIED (automated) | Registry, adapters, contract suite, workflow; live Claude pending |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `gemini_cli.py` | 22 | `raise NotImplementedError` | ℹ️ Info | Intentional D-02 skeleton — not a stub leak |

No TBD/FIXME/XXX in phase-modified source files.

### Human Verification Required

#### 1. Claude Code adapter live review — OVERRIDE ACCEPTED

**Test:** Sandbox PR with `PREVUE_ENGINE=claude-code-cli` and valid `ANTHROPIC_API_KEY`  
**Expected:** Sticky comment + check published; review references diff only (`--bare`); clean exit  
**Status:** PASSED (override) — accepted by user 2026-06-13. `ANTHROPIC_API_KEY` unavailable; contract suite green.

#### 2. Cursor adapter live review (UAT pass — optional re-run)

**Test:** Sandbox PR with `PREVUE_ENGINE=cursor-cli` and `CURSOR_API_KEY`  
**Expected:** Official `cursor-agent` via curl installer; sticky + check; no hang; no repo writes  
**Why human:** UAT pass on PR #11; optional regression confirmation

#### 3. Unknown engine fail-closed live (UAT pass — optional re-run)

**Test:** Workflow run with `PREVUE_ENGINE=typo`  
**Expected:** Visible `UnknownEngineError` naming bad value and listing valid engines  
**Why human:** UAT pass; optional regression confirmation

See also `.planning/phases/05-multi-engine-adapter-support/05-UAT.md`.

### Gaps Summary

Automated implementation complete — 259 tests pass, all plan artifacts substantive and wired. Claude Code D-12 live E2E override accepted (environmental — no `ANTHROPIC_API_KEY`). Cursor live + unknown-engine fail-closed both passed. Phase status: **passed**.

---

_Verified: 2026-06-13T18:30:00Z_  
_Verifier: Claude (gsd-verifier)_
