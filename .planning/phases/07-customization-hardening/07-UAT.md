---
status: resolved
phase: 07-customization-hardening
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md, 07-05-SUMMARY.md]
started: 2026-06-15T12:00:00.000Z
updated: 2026-06-15T18:00:00.000Z
---

## Current Test

[testing complete]

## Tests

### 1. Consumer skill override replaces built-in
expected: Consumer skill at same bundle/filename overrides built-in; review routes to custom skill content
result: pass
note: "07-06: sticky Skills line tags consumer overrides as (bundle, consumer); Engine line reads adapter.name"

### 2. Consumer skill add-alongside built-ins
expected: New filename in an existing bundle (e.g. security/) adds alongside built-ins; both can load when globs match
result: pass

### 3. skills.exclude disables a skill
expected: Listing `bundle/filename` under `skills.exclude` in `.github/prevue.yml` removes that skill from the loaded set regardless of source
result: pass
note: "07-07: docs/examples/prevue.yml starter + consumer-setup section for copy-paste adoption"

### 4. Token transparency in sticky summary
expected: Every review sticky comment includes a token line (review + classify split, ~est when estimated) and per-bundle loaded/skipped ratios on the packed file set
result: pass

### 5. Large-PR budget packing and disclosure
expected: PR exceeding token budget gets partial review; sticky shows "N files not reviewed" with collapsible path list; check conclusion is neutral (never green pass) when files were dropped
result: pass

### 6. Prompt-injection defenses verified
expected: SECURITY.md documents trust boundary and four vectors; adversarial CI suite green; injected diff/path text cannot force PASS or alter findings/labels
result: pass

### 7. Engine tool posture (D-08 human verify)
expected: Each available engine adapter (Copilot, Claude Code, Cursor) in default headless mode cannot fetch PR title/body/comments or reach network to satisfy injection instructions in the diff
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Consumer skill at same bundle/filename overrides built-in; sticky summary shows which skills loaded and that consumer override is active"
  status: resolved
  resolved_by: 07-06
  test: 1

- truth: "Consumer can adopt .github/prevue.yml from documented starter example"
  status: resolved
  resolved_by: 07-07
  test: 3
