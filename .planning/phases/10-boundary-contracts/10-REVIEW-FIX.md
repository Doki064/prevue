---
phase: 10-boundary-contracts
fixed_at: 2026-06-29T00:00:00Z
review_path: .planning/phases/10-boundary-contracts/10-REVIEW.md
iteration: 3
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-06-29T00:00:00Z
**Source review:** .planning/phases/10-boundary-contracts/10-REVIEW.md
**Iteration:** 3

**Summary:**
- Findings in scope: 5 (2 Critical + 3 Warning; Info excluded by fix_scope=critical_warning)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Antigravity CLI always receives literal `$_AGY_PROMPT` instead of the review prompt

**Files modified:** `src/prevue/engines/cli_adapter.py`
**Commit:** 2bdab92
**Applied fix:** Replaced the single loop `" ".join(shlex.quote(p) for p in inner_parts)` (which quoted `"$_AGY_PROMPT"` into `'$_AGY_PROMPT'`, suppressing shell expansion) with a two-step approach: shell-quote only the non-variable parts (`inner_parts_to_quote`) and concatenate `" $_AGY_PROMPT"` unquoted at the end. The env-var reference now reaches `bash -c` as a bare token, so the shell expands it to the actual prompt text before passing it to `agy`.

---

### CR-02: Consumer `engine.pricing` override (D-06c) is parsed but never applied

**Files modified:** `src/prevue/engines/flow.py`, `src/prevue/engines/cli_adapter.py`, `src/prevue/review.py`
**Commit:** 8c6f903
**Applied fix:**
1. Added `pricing_override: dict | None = None` parameter to `review_with_retry` in `flow.py`.
2. Threaded `pricing_override` into both `compute_cost()` calls (first invocation and retry) replacing the hard-coded `override=None`.
3. Added `_pricing_override: dict | None = None` field and `set_pricing_override()` method to `CliEngineAdapter`, analogous to `set_raw_args()`.
4. Passed `pricing_override=self._pricing_override` into the `flow.review_with_retry()` call in `CliEngineAdapter.review()`.
5. In `review.py`, added a block after the existing `set_raw_args` injection that calls `engine.set_pricing_override(config.engine_config.pricing)` when the adapter supports it, sourcing the dict from the base-ref-gated `load_config` read.

---

### WR-01: `review.yml` (dogfood) omits `gemini-api-key` secret pass-through

**Files modified:** `.github/workflows/review.yml`
**Commit:** 4044c30
**Applied fix:** Added `gemini-api-key: ${{ secrets.GEMINI_API_KEY }}` to the `secrets:` block of the `review` job's `uses: ./.github/workflows/prevue-review.yml` call, matching the optional secret declared in `prevue-review.yml`.

---

### WR-02: `emit_machine_output` writes result file without warning when `PREVUE_RESULT_FILE` is unset under Actions

**Files modified:** `src/prevue/review.py`
**Commit:** 9f4248e
**Applied fix:** Added a diagnostic `print(..., file=sys.stderr)` inside `emit_machine_output` that fires when `GITHUB_ACTIONS` is set and `PREVUE_RESULT_FILE` is not set (and no `output_file` kwarg was injected). The warning makes the default CWD fallback explicit so misconfigured step environments are immediately visible in the workflow log.

---

### WR-03: `EngineConfig.raw_args` validator does not reject non-string list elements

**Files modified:** `src/prevue/config.py`
**Commit:** f647fbe
**Applied fix:** Extended `_validate_raw_args` to iterate over list elements and raise `ValueError` for any element that is not a `str` (e.g., `None`, `int`). Added an inline docstring explaining that Pydantic v2 would otherwise silently coerce those values to strings, producing invalid CLI flags with no error.

---

_Fixed: 2026-06-29T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3_
