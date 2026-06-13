---
phase: 05-multi-engine-adapter-support
plan: 03
subsystem: engines
tags: [cursor-cli, workflow, supply-chain, ENGN-04]

requires:
  - phase: 05-multi-engine-adapter-support
    plan: 02
    provides: registry pattern, contract suite
provides:
  - CursorAdapter (cursor-cli)
  - Workflow Claude/Cursor curl install steps + secret pass-through
  - Supply-chain guard rejecting npm cursor-agent impostor
affects: [06]

key-files:
  created:
    - src/prevue/engines/cursor_cli.py
  modified:
    - src/prevue/engines/registry.py
    - .github/workflows/review.yml
    - tests/test_workflow_yaml.py

requirements-completed: [ENGN-04]

duration: 25min
completed: 2026-06-13
---

# Phase 5 Plan 03 Summary

**Cursor adapter + workflow install vectors; D-12 live verification pending human run**

## Accomplishments

- CursorAdapter registered as `cursor-cli`; invokes `cursor-agent -p -f <tmpfile>` without `--force`
- CURSOR_API_KEY checked pre-subprocess; `-m` model mapping when set
- Workflow installs Claude via claude.ai/install.sh and Cursor via cursor.com/install
- Static tests reject `npm install -g cursor-agent` impostor
- All four adapters in ENGINES; contract suite parametrized over copilot/claude/cursor

## D-12 Live Verification

**Status: PENDING** — requires sandbox PR with live CLIs and secrets.

| Run | PREVUE_ENGINE | Expected | Result |
|-----|---------------|----------|--------|
| 1 | claude-code-cli | sticky + check, diff-only review, clean exit | pending |
| 2 | cursor-cli | sticky + check, no hang, no file writes | pending |
| 3 | typo | UnknownEngineError visible failure | pending |

Run via `/gsd-verify-work 5` after configuring sandbox secrets `ANTHROPIC_API_KEY` and `CURSOR_API_KEY`.

## Task Commits

Combined in `c366b2b`

## Self-Check: PASSED (automated)

- `uv run pytest -q` — 257 passed
- `uv run pytest tests/test_workflow_yaml.py -q` — passed
