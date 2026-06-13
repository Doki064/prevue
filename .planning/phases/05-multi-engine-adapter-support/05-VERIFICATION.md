---
phase: 05-multi-engine-adapter-support
verified: 2026-06-13T08:00:00Z
status: human_needed
score: 6/6 must-haves verified (automated)
overrides_applied: 0
human_verification:
  - test: "Sandbox PR with PREVUE_ENGINE=claude-code-cli and ANTHROPIC_API_KEY — confirm sticky comment + check, diff-only review, clean exit"
    expected: "Review references only PR diff content (--bare); sticky upsert + prevue/review check published"
    why_human: "D-12 live CLI + real auth; CI mocks subprocess per D-11"
  - test: "Sandbox PR with PREVUE_ENGINE=cursor-cli and CURSOR_API_KEY — confirm sticky + check, no hang, no repo writes"
    expected: "cursor-agent resolves via official installer; completes within budget_seconds; read-only (no --force)"
    why_human: "D-12 live CLI; Pitfall 2 hang and A4 read-only require real runner"
  - test: "Sandbox run with PREVUE_ENGINE=typo — confirm visible UnknownEngineError failure"
    expected: "Workflow fails closed naming bad value and listing valid engines"
    why_human: "D-04 live fail-closed confirmation"
---

# Phase 5: Multi-Engine Adapter Support — Verification Report

**Phase Goal:** EngineAdapter abstraction proven engine-agnostic — Claude Code, Cursor, and Gemini skeleton registered, selectable via PREVUE_ENGINE, sharing prompt/flow/parsing

**Verified:** 2026-06-13  
**Status:** human_needed (D-12 live verification pending)  
**Automated score:** 6/6 plan must-haves

## Observable Truths (Automated)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Shared prompt/errors/flow hoisted; Copilot green through registry (D-09, D-03) | ✓ | `prompt.py`, `errors.py`, `flow.py`; `test_prompt.py`; re-exports on `copilot_cli.py`; `test_review_flow::test_engine_selection_via_prevue_engine` |
| 2 | Unknown PREVUE_ENGINE fail-closed (D-04) | ✓ | `UnknownEngineError` in `registry.py`; `test_registry.py`; review flow test |
| 3 | ClaudeCodeAdapter registered, contract suite green (D-01) | ✓ | `claude_code_cli.py`; `--bare -p` argv tests; auth pre-subprocess |
| 4 | CursorAdapter registered, contract suite green (D-01) | ✓ | `cursor_cli.py`; `-f` tempfile, no `--force`; auth pre-subprocess |
| 5 | Gemini skeleton raises NotImplementedError (D-02) | ✓ | `gemini_cli.py`; `test_registry.py` |
| 6 | Workflow curl installs only; npm impostor rejected | ✓ | `review.yml`; `test_workflow_yaml.py` guards |

## Regression

- `uv run pytest -q` — **257 passed**
- Gate/findings/comments/checks layers unchanged (`git diff 9a1e2f7..HEAD --stat src/prevue/gate.py src/prevue/github/` empty)

## Human Verification Required (D-12)

See `.planning/phases/05-multi-engine-adapter-support/05-UAT.md`.

Run: `/gsd-verify-work 5`

## Gaps

None automated. D-12 live runs pending user sandbox verification.
