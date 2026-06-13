---
status: complete
phase: 05-multi-engine-adapter-support
source: [05-VERIFICATION.md]
started: 2026-06-13T08:00:00Z
updated: 2026-06-13T17:00:00Z
uat_pr: "#11"
---

## UAT Infrastructure

Live UAT via `uat/phase-05` → `gsd/phase-05-multi-engine-adapter-support`.

Fixture: `uat/phase-05/sample.py`. Engine via `uat/phase-05/ACTIVE`. See `uat/README.md`.

## Current Test

[testing complete]

## Tests

### 1. Claude Code adapter live review on sandbox PR
expected: Sticky + check published; diff-only review; clean exit with --bare
result: skipped
reason: Pro subscription — no ANTHROPIC_API_KEY available for live CLI auth

### 2. Cursor adapter live review on sandbox PR
expected: Sticky + check; cursor-agent from official installer; no hang; no file writes
result: pass
note: prevue/review check neutral; user ok. Workflow installed all 3 CLIs + loaded all secrets — fixed in follow-up commit (selective install).

### 3. Unknown engine fail-closed live
expected: PREVUE_ENGINE=typo fails visibly with UnknownEngineError message
result: pass

## Summary

total: 3
passed: 2
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps
