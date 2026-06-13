---
status: testing
phase: 04-structured-findings-merge-gate
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md]
started: 2026-06-13T12:05:00Z
updated: 2026-06-13T12:05:00Z
---

## Current Test

number: 1
name: Inline comment placement on live PR
expected: |
  💬 inline comments appear on correct changed lines in GitHub PR UI;
  unplaceable findings visible only in sticky summary index (not dropped)
awaiting: user response

## Tests

### 1. Inline comment placement on live PR
expected: Open/refresh sandbox test PR; inline comments land on changed diff lines; invalid positions appear in sticky summary only
result: pending

### 2. Check run merge gate visibility
expected: `prevue/review` check appears in PR merge box; conclusion (success/neutral/failure) mirrors sticky Verdict section; blocking only when min_severity_to_fail configured
result: pending

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
