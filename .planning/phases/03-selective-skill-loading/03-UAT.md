---
status: testing
phase: 03-selective-skill-loading
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md]
started: 2026-06-12T21:00:00Z
updated: 2026-06-12T21:30:00Z
uat_branch: uat/phase-03
uat_base: gsd/phase-03-selective-skill-loading
uat_scenario: 01-backend-only
---

## UAT Branch

| Field | Value |
|-------|-------|
| Branch | `uat/phase-03` |
| Base | `gsd/phase-03-selective-skill-loading` |
| Active scenario | `01-backend-only` → `uat/active/sample.py` |
| Switch | `./uat/switch-scenario.sh <id>` then `git add uat/active uat/ACTIVE` + push |

**PR diff rule:** only `uat/active/*` may change on this branch — scenario templates stay on base (`uat/scenarios/`).

Scenario map: see `uat/README.md`. Branch updates only for live workflow tests (1, 4, 5 skip, 9).

## Current Test

number: 1
name: Backend-only PR selective skill loading
expected: |
  A PR touching only backend files (e.g. `src/api/*.py`) loads backend + security skills into review context — not frontend, data, or infra skills. Sticky comment Metadata shows loaded skill names grouped by bundle; backend/security present, frontend/data/infra absent.
awaiting: user response

## Tests

### 1. Backend-only PR selective skill loading
expected: PR with only backend files loads backend + security skills, not frontend/data/infra; Metadata audit reflects selective load
result: [pending]

### 2. Five built-in skill bundles
expected: Five bundle directories exist under `src/prevue/skills/` (security, frontend, backend, data, infra); each skill file has valid frontmatter (`name`, `description`, `applies-to` globs)
result: [pending]

### 3. Trusted framework-only loading (SKIL-04)
expected: Skills load from packaged framework directory via importlib.resources — never from PR head or consumer-modified paths in the same run
result: [pending]

### 4. Loaded skills in sticky Metadata (D-13)
expected: Sticky comment Metadata section includes a `Skills:` line listing loaded skill names with their bundle (e.g. `Skills: Error Handling (backend), Committed Secrets & Credentials (security)`)
result: [pending]

### 5. No-match baseline fallback (D-06)
expected: When no skill globs match changed files, review context contains only `BASELINE_INSTRUCTIONS` — no specialist skill sections appended
result: [pending]

### 6. Security secrets-flagging skill (SKIL-02)
expected: Security bundle includes a skill that flags secrets/credentials committed in the diff (e.g. `committed-secrets.md`)
result: [pending]

### 7. Built-in skill content quality (D-11)
expected: Each built-in skill contains genuine lean review guidance (checklists, actionable criteria) — not placeholder stubs
result: [pending]

### 8. Test suite green
expected: `uv run pytest -q` passes all tests including skills loader, builtin, review flow, and comments tests; `uv run ruff check` clean
result: [pending]

### 9. End-to-end outcome coverage
expected: Full Phase 3 goal met — review context contains exactly matched skills from trusted ref, auditable in Metadata, five bundles shipped, selective loading proven end-to-end
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps

[none yet]
