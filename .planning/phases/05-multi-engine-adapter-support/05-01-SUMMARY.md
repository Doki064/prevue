---
phase: 05-multi-engine-adapter-support
plan: 01
subsystem: engines
tags: [registry, prompt, pytest, tdd, ENGN-04]

requires:
  - phase: 04-structured-findings-merge-gate
    provides: parsing.py, copilot_cli reference adapter, run_review orchestration
provides:
  - Shared engines/prompt.py, errors.py, flow.py
  - Fail-closed registry with PREVUE_ENGINE selection
  - Gemini skeleton adapter
  - Parametrized contract test suite scaffolds
affects: [05-02, 05-03, 06]

tech-stack:
  added: []
  patterns: [shared review_with_retry free function, re-export shims on copilot_cli]

key-files:
  created:
    - src/prevue/engines/prompt.py
    - src/prevue/engines/errors.py
    - src/prevue/engines/flow.py
    - src/prevue/engines/registry.py
    - src/prevue/engines/gemini_cli.py
    - tests/test_prompt.py
    - tests/test_registry.py
    - tests/test_engine_contract.py
    - tests/engine_helpers.py
  modified:
    - src/prevue/engines/copilot_cli.py
    - src/prevue/review.py
    - src/prevue/cli.py
    - tests/conftest.py
    - tests/test_copilot_adapter.py
    - tests/test_review_flow.py
    - tests/test_fork_guard.py

key-decisions:
  - "PREVUE_ENGINE env + get_adapter registry replaces hard-coded CopilotCliAdapter"
  - "Unknown engine raises UnknownEngineError with valid engine list (D-04)"
  - "Prompt fencing hoisted verbatim to prompt.py (D-09)"

requirements-completed: [ENGN-04]

duration: 45min
completed: 2026-06-13
---

# Phase 5 Plan 01 Summary

**Shared engine foundation + fail-closed registry; Copilot path unchanged behavior through PREVUE_ENGINE**

## Accomplishments

- Hoisted OUTPUT_CONTRACT, build_prompt, fencing, errors, and review_with_retry into shared modules
- Registry resolves copilot-cli by default; unknown names fail closed
- GeminiAdapter registered with NotImplementedError
- cli.py catches AuthError base class
- 257-test suite green including parametrized contract suite for copilot-cli

## Task Commits

Combined in `c366b2b` (feat(05): multi-engine adapter support)

## Self-Check: PASSED

- `uv run pytest -q` — 257 passed
- `uv run ruff check src/prevue/engines tests/...` — clean on modified files
