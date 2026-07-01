---
phase: 10-boundary-contracts
fixed_at: 2026-07-01T13:38:12Z
review_path: .planning/phases/10-boundary-contracts/10-REVIEW.md
iteration: 3
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-07-01T13:38:12Z
**Source review:** .planning/phases/10-boundary-contracts/10-REVIEW.md
**Iteration:** 3

**Summary:**
- Findings in scope: 2 (Critical: 0, Warning: 2 — `fix_scope: critical_warning`; Info
  findings IN-01/IN-02/IN-03 excluded)
- Fixed: 2
- Skipped: 0

_Note: this report documents iteration 3 (final, `--auto` loop cap = 3) of the fix loop — a
re-review pass run after iteration 2's CR-01/WR-01..03 fixes, which confirmed those four
fixed and surfaced two new warnings, no new critical. It overwrites iteration 2's
`10-REVIEW-FIX.md`; that report remains available in `10-REVIEW-FIX.iter3.md`._

## Fixed Issues

### WR-01: `prevue-command-run.yml` missing the `antigravity-cli` install exclusion added to `prevue-review.yml` in iteration 2 — drift between the two entry points

**Files modified:** `.github/workflows/prevue-command-run.yml`
**Commit:** `30c5cf9`
**Applied fix:** Added the matching `github.event.client_payload.engine != 'antigravity-cli'`
exclusion to the command-run workflow's own "Install engine CLI" `if:` condition, mirroring
iteration 2's WR-03 fix in `prevue-review.yml`, with a comment cross-referencing that finding
and noting the exclusion should be removed once `antigravity-cli` ships headless auth and
`spec.py` flips `functional=True`.

### WR-02: `_validate_pricing` field validator (iteration 2's CR-01 fix) had zero regression test coverage

**Files modified:** `tests/test_engine_config_pricing.py` (new)
**Commit:** `5801c14`
**Applied fix:** Added a new test file covering the validator: non-dict `pricing` value
rejected, non-dict/non-null row rejected, `None` tolerated as "no override," and a
well-formed row accepted — mirroring `test_raw_args.py`'s structure for the sibling
`raw_args` validator.

## Skipped Issues

None — all in-scope findings were fixed.

_Note: IN-01, IN-02, IN-03 are Info-tier findings, explicitly out of scope for this run
(`fix_scope: critical_warning`) and unchanged across all three iterations. A future `--all`
pass can address them if desired._

## Verification Summary

- Both fix commits (`30c5cf9`, `5801c14`) were made in an isolated git worktree and
  fast-forwarded onto `gsd/phase-10-boundary-contracts`; worktree, temp branch, and recovery
  sentinel were cleaned up.
- Full test suite (`uv run pytest -q`): **813 passed**, 0 failed, 0 errors (807 baseline + 6
  new tests from `test_engine_config_pricing.py`).
- `uv run ruff check .`: all checks passed.
- No findings required rollback.

## `--auto` Loop Summary (iterations 1–3)

| Iteration | Critical | Warning | Fixed | Key findings |
|---|---|---|---|---|
| 1 | 2 | 4 | 6/6 | `load_config()` uncaught crash on empty `models`/`raw_args` YAML; pricing-table key mismatch; missing secrets docs; dead `_resolve_model`; silent adapter override |
| 2 | 1 | 3 | 4/4 | `engine.pricing` shape unvalidated; undocumented `engine.models`/`raw_args`/`pricing`; command-run/review workflow env drift; wasted install for non-functional antigravity-cli |
| 3 | 0 | 2 | 2/2 | command-run/review workflow install-exclusion drift (same class as iteration 2, second entry point); no test coverage for the new pricing validator |

Loop cap (3 iterations) reached with 0 critical findings remaining and only Info-tier findings
outstanding (unaddressed by design, out of `critical_warning` scope). Total across all three
iterations: 12 Critical/Warning findings fixed, 0 skipped, 12 commits.

---

_Fixed: 2026-07-01T13:38:12Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3_
