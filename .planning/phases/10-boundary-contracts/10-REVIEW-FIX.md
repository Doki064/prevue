---
phase: 10-boundary-contracts
fixed_at: 2026-07-06T05:52:00Z
review_path: .planning/phases/10-boundary-contracts/10-REVIEW.md
iteration: 4
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-07-06T05:52:00Z
**Source review:** .planning/phases/10-boundary-contracts/10-REVIEW.md
**Iteration:** 4

**Summary:**
- Findings in scope: 2 (CR-01, WR-01 — fix_scope: critical_warning; this pass's
  REVIEW.md (pass 5) has 1 critical and 1 warning finding, 0 info)
- Fixed: 2
- Skipped: 0

Note: this is the 5th REVIEW.md pass for this phase (iterations 1-3 of this file
cover the prior three passes' fixes). This pass's reviewer re-derived findings
independently and confirmed the prior pass's CR-01 (pricing leaf-value
validation) and WR-01 (E501 lint) fixes are still holding, but found that the
prior pass's WR-02 fix to `update-pricing.yml` introduced a new, more severe
regression — re-flagged as this pass's CR-01 — and that the prior pass's own
CR-01 shipped with zero regression test coverage — flagged as this pass's WR-01.

## Fixed Issues

### CR-01: `update-pricing.yml`'s "reuse existing PR" idempotency fix always takes the wrong branch — the workflow can never create a pricing-bump PR

**Files modified:** `.github/workflows/update-pricing.yml`
**Commit:** ccb200d
**Applied fix:** Changed the jq filter from `.[0].number` to `.[0].number // empty`.
`jq '.[0].number'` on an empty PR-list array (the common, no-existing-PR case)
prints the literal 4-character string `"null"`, which is non-empty, so
`[ -n "$EXISTING_PR" ]` was always true and the workflow always ran
`gh pr edit "null" ...` — which fails — instead of ever reaching the `gh pr
create` branch. `// empty` makes jq emit nothing when there's no match, so
`$EXISTING_PR` is genuinely empty in that case and the `if` behaves as
intended. Verified directly: `echo '[]' | jq '.[0].number // empty'` now
prints nothing (previously printed `null`), and `[ -n "$EXISTING_PR" ]`
correctly evaluates to false on the reproduced empty-array case. Also
confirmed the YAML still parses cleanly (`python3 -c "import yaml; ..."`)
and `zizmor` (part of `scripts/ci-local.sh`) reports no findings against
`update-pricing.yml` after the edit.

### WR-01: CR-01's (previous pass's) `engine.pricing` leaf-value validator shipped with no regression test

**Files modified:** `tests/test_engine_config_pricing.py`
**Commit:** 255f86b
**Applied fix:** Added two tests mirroring the existing file's style:
`test_pricing_rejects_string_scientific_notation_leaf` (asserts a string leaf
value like `"1e-06"` for `input_cost_per_token` is rejected with a
`ValidationError` matching `"number or null"` — the PyYAML
scientific-notation-without-a-decimal-point gotcha) and
`test_pricing_rejects_bool_leaf` (asserts a `bool` leaf value like `True` is
rejected with the same `ValidationError`, since `bool` is an `int` subclass
in Python but must not be treated as a valid cost rate). Read the actual
`_validate_pricing` implementation and error message in `src/prevue/config.py`
first to confirm the `match="number or null"` text is accurate rather than
guessing from the REVIEW.md snippet. Both new tests pass; full suite (835
tests, up from 833) is green.

## Skipped Issues

None — all in-scope findings were fixed.

## Verification

Ran the full `scripts/ci-local.sh` mirror after both fixes:
- `pytest` (with coverage): 835 passed
- `ruff check .`: All checks passed!
- `ruff format --check`: 106 files already formatted
- `actionlint`: clean
- `zizmor`: no findings across all 6 workflow files, including
  `update-pricing.yml`

---

_Fixed: 2026-07-06T05:52:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 4_
</content>
