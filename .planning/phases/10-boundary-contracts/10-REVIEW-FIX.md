---
phase: 10-boundary-contracts
fixed_at: 2026-07-01T19:10:00Z
review_path: .planning/phases/10-boundary-contracts/10-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 1
status: all_fixed
---

# Phase 10: Code Review Fix Report (10-09 gap-closure round)

**Fixed at:** 2026-07-01T19:10:00Z
**Source review:** .planning/phases/10-boundary-contracts/10-REVIEW.md (9-file scope, plan 10-09's changeset)
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (Critical: 2 — CR-01, CR-02; Warning: 2 — WR-01, WR-02; Info IN-01 excluded, `fix_scope: critical_warning`)
- Fixed: 4
- Skipped: 0 in scope (IN-01 left as a documented follow-up, not applied)

Fixes applied manually by the orchestrator (not via `gsd-code-fixer`) since CR-01 required a
user decision (CI-pinned dependency version bump — see below) before it could be applied.

## Fixed Issues

### CR-02: Partial-field parse failure inside one OTEL span silently produces a corrupted total reported as `estimated=False`

**Files modified:** `src/prevue/engines/usage.py`, `tests/test_usage_capture.py`
**Commit:** `cdd96e8`
**Applied fix:** Parse all four token fields into locals first; only merge into the running
totals and increment `span_count` if the whole span parses cleanly, otherwise skip the span
entirely (same as any other malformed span). Added regression test
`test_copilot_otel_partial_field_parse_failure_skips_whole_span`.

### CR-01: Fix root-caused against `gh copilot` v1.0.67, but CI still installed 1.0.61

**Files modified:** `.github/scripts/install-engine-cli.sh`, `docs/configuration.md`, `docs/DEVELOPMENT.md`, `tests/test_workflow_yaml.py`
**Commit:** `4956f00`
**Applied fix:** User selected "bump CI pin to 1.0.67" (of three options: bump pin, add
runtime diagnostic only, leave as documented gap) via AskUserQuestion. Bumped
`install-engine-cli.sh`'s `@github/copilot` pin from `1.0.61` to `1.0.67`, updated
`docs/configuration.md`'s engine-install-versions table and OTEL paragraph to state support
plainly instead of hedging, updated `docs/DEVELOPMENT.md`'s example, and bumped
`tests/test_workflow_yaml.py`'s `COPILOT_CLI_VERSION` constant (which asserts the installer
string matches it).

### WR-02: `span_count`'s doc comment claims a stronger guarantee than the code provided

**Resolved as a byproduct of CR-02** — `span_count` is now only incremented for spans that
parsed all four fields cleanly, so the existing comment's claim ("distinguishes 'no real
spans found' from a genuine zero-token span") now holds. No separate edit needed.

### WR-01: `docs/configuration.md`'s OTEL claim hedged rather than resolved the version-mismatch gap

**Resolved as a byproduct of CR-01** — once the pin was bumped to `1.0.67`, the paragraph was
rewritten to state plainly that the pinned version ships OTEL export and matches the parser's
schema, rather than instructing the reader to self-verify.

## Skipped (left for follow-up, not fixed)

### IN-01: `github.copilot.cost` correctly excluded from parser output, but no regression test pins that decision

**Reason:** Info-severity, no correctness impact — `fix_scope: critical_warning` excludes Info
findings by default. Left as a documented follow-up; a future change adding a fixture with a
`github.copilot.cost` field and asserting no `cost_usd` key leaks into `_parse_copilot_otel`'s
return dict would close it.

---

_Full CI mirror (`bash scripts/ci-local.sh`: 823 tests, ruff, ruff format, actionlint, zizmor) green after both fixes._
