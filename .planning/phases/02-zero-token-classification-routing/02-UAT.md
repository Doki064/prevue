---
status: complete
phase: 02-zero-token-classification-routing
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md]
started: 2026-06-12T14:00:00Z
updated: 2026-06-12T20:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Clear-cut frontend PR classification
expected: PR with only `.tsx` files receives `frontend` label with matched glob in Metadata; zero LLM classify tokens
result: pass

### 2. Multi-domain PR union labels
expected: PR with both `.tsx` and `.tf` files receives both `frontend` and `infra` labels (D-01 union), not just one
result: pass

### 3. Unclassifiable PR general fallback
expected: PR with files matching no label rules receives only `{general}` fallback label — never alongside real labels (D-03)
result: pass

### 4. Lockfile-only PR neutral skip
expected: PR with only lockfiles/generated/vendored files (all filtered) skips engine entirely; idempotent sticky note says "no reviewable files (N filtered)" with zero engine tokens (D-10)
result: pass

### 5. Metadata audit trail
expected: Sticky comment Metadata shows labels, matched globs per label, routed bundles, and filtered-file count in canonical order (security before infra, not alphabetical)
result: pass

### 6. Consumer prevue.yml rule merge
expected: Consumer `.github/prevue.yml` merges additively (ignore globs append) and overrides by label (consumer globs replace built-in for that label key); malformed YAML fails closed
result: pass

### 7. Zero-token classify and bundle routing outcome
expected: Classification stage makes zero subprocess/network/LLM calls; labels resolve to bundle ids via `route()` with consumer override precedence; engine receives reduced diff only (lockfiles filtered before classify)
result: pass

### 8. Test suite green
expected: `uv run pytest -q` passes all 100 tests including classify, filter, router, review flow, and comments tests
result: pass

### 9. End-to-end outcome coverage
expected: Full Phase 2 goal met — clear-cut PRs classified deterministically at zero LLM tokens, auditable decision trail in Metadata, edge cases handled (union, general, empty skip, consumer merge)
result: pass

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
