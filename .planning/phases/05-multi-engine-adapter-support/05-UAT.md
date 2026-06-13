---
status: testing
phase: 05-multi-engine-adapter-support
source: [05-VERIFICATION.md]
started: 2026-06-13T08:00:00Z
updated: 2026-06-13T08:00:00Z
---

## Current Test

number: 1
name: Claude Code adapter live review on sandbox PR
expected: |
  PREVUE_ENGINE=claude-code-cli with ANTHROPIC_API_KEY produces sticky comment +
  prevue/review check; review references diff content only; clean exit.
awaiting: user response

## Tests

### 1. Claude Code adapter live review on sandbox PR
expected: Sticky + check published; diff-only review; clean exit with --bare
result: [pending]

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
pending: 3
skipped: 0
blocked: 0

## Gaps
