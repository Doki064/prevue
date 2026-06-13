---
status: testing
phase: 05-multi-engine-adapter-support
source: [05-VERIFICATION.md]
started: 2026-06-13T08:00:00Z
updated: 2026-06-13T16:00:00Z
uat_pr: "#11"
---

## UAT Infrastructure

Live UAT via `uat/phase-05` → `gsd/phase-05-multi-engine-adapter-support`.

Fixture: `uat/phase-05/sample.py`. Engine switching via repo variable `PREVUE_ENGINE`. See `uat/README.md`.

## Current Test

number: 2
name: Cursor adapter live review on sandbox PR
expected: |
  PREVUE_ENGINE=cursor-cli with CURSOR_API_KEY produces sticky comment +
  prevue/review check; cursor-agent from official installer; no hang; no file writes.
awaiting: user response

## Tests

### 1. Claude Code adapter live review on sandbox PR
expected: Sticky + check published; diff-only review; clean exit with --bare
result: skipped
reason: Pro subscription — no ANTHROPIC_API_KEY available for live CLI auth

### 2. Cursor adapter live review on sandbox PR
expected: Sticky + check; cursor-agent from official installer; no hang; no file writes
result: [pending]

### 3. Unknown engine fail-closed live
expected: PREVUE_ENGINE=typo fails visibly with UnknownEngineError message
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 2
skipped: 1
blocked: 0

## Gaps
