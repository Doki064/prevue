---
status: testing
phase: 10-boundary-contracts
source: [10-VERIFICATION.md]
started: 2026-06-29T12:00:00Z
updated: 2026-06-29T12:00:00Z
---

## Current Test

number: 1
name: Live Antigravity sandbox review end-to-end
expected: |
  Antigravity review posts sticky summary with findings (pseudo-TTY wrapper prevents stdout-drop).
  Tokens labeled ~est (estimate fallback honest). Cost line renders. prevue-result.json artifact
  uploaded. Compact job outputs populated (conclusion, error_count, etc.) in downstream job.
awaiting: user response

## Tests

### 1. Live Antigravity sandbox review end-to-end
expected: |
  In gap-demo-sandbox, set engine: antigravity-cli, provide ANTIGRAVITY_API_KEY.
  Open a test PR. Confirm: sticky summary posted with findings, ~est token label,
  cost line renders, prevue-result.json artifact uploaded, compact job outputs populated.
result: [pending]

### 2. Copilot OTEL WARNING-3 real-token spot-check
expected: |
  Run engine: copilot-cli on same sandbox. Sticky Tokens line shows WITHOUT ~est label
  (estimated=False), confirming COPILOT_OTEL_FILE_EXPORTER_PATH wiring enables real
  OTEL capture in CI.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
