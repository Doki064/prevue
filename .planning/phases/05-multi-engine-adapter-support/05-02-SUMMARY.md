---
phase: 05-multi-engine-adapter-support
plan: 02
subsystem: engines
tags: [claude-code, ANTHROPIC_API_KEY, ENGN-04]

requires:
  - phase: 05-multi-engine-adapter-support
    plan: 01
    provides: shared prompt/flow/errors, registry, contract suite
provides:
  - ClaudeCodeAdapter (claude-code-cli)
  - ClaudeAuthError
affects: [05-03, 06]

key-files:
  created:
    - src/prevue/engines/claude_code_cli.py
  modified:
    - src/prevue/engines/registry.py

requirements-completed: [ENGN-04]

duration: 20min
completed: 2026-06-13
---

# Phase 5 Plan 02 Summary

**Claude Code CLI adapter — argv + auth only; shared prompt/flow/parsing reused**

## Accomplishments

- ClaudeCodeAdapter registered as `claude-code-cli`
- Invokes `claude --bare -p --output-format text` with prompt via stdin
- ANTHROPIC_API_KEY checked pre-subprocess; `--model` mapped when set
- Parametrized contract suite auto-covers Claude alongside Copilot

## Task Commits

Combined in `c366b2b`

## Self-Check: PASSED

- Contract tests for auth, argv, valid/degrade/retry paths pass
