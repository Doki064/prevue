---
phase: 10-boundary-contracts
fixed_at: 2026-06-30T10:30:00Z
review_path: .planning/phases/10-boundary-contracts/10-REVIEW.md
iteration: 3
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-06-30T10:30:00Z
**Source review:** .planning/phases/10-boundary-contracts/10-REVIEW.md
**Iteration:** 3

**Summary:**
- Findings in scope: 1 (fix_scope: critical_warning — CR-01 only; REVIEW.md reports 0
  Warning findings, and IN-01/IN-02/IN-03 are Info-tier, out of scope)
- Fixed: 1
- Skipped: 0

## Fixed Issues

### CR-01: `_parse_copilot_otel` crashes with uncaught `AttributeError` on non-dict-shaped OTEL JSONL records, violating the documented T-10-07 graceful-degradation contract

**Files modified:** `src/prevue/engines/usage.py`, `tests/test_usage_capture.py`
**Commit:** `ee60605` (made on temp branch `gsd-reviewfix/10-19890`, fast-forwarded into `gsd/phase-10-boundary-contracts`)
**Applied fix:**

`_parse_copilot_otel` decoded each JSONL line with `json.loads()` (wrapped in
`except (json.JSONDecodeError, ValueError)`) but then called `.get()` on the decoded
value, and on each nested `resourceSpans`/`scopeSpans`/`spans` element, without
verifying dict-ness. A JSON-decodable-but-wrong-shaped line (e.g. a bare array, or a
non-dict element inside `resourceSpans`) raised an uncaught `AttributeError` that
propagated out of `capture_usage()` and crashed the whole review run, instead of
degrading to the documented bytes/4 fallback.

Read the actual source at the cited line range (188-217) and confirmed it matched the
review's description exactly — no drift. Added `isinstance(..., dict)` guards at all
four nesting levels (the top-level decoded record, each `resourceSpans` element, each
`scopeSpans` element, each `spans` element), plus an `isinstance(a, dict)` guard on the
attribute-list comprehension, per the fix suggested in REVIEW.md. Non-dict values at
any level now `continue` to the next line/element (same degrade-don't-crash behavior
as a JSON decode failure) rather than raising.

Verified both repros from REVIEW.md no longer raise and instead return a zeroed
usage dict (`{"input": 0, "output": 0, "cache_read": 0, "estimated": False}`):
- A JSONL line that decodes to a bare list (`[1, 2, 3]`)
- A JSONL line decoding to `{"resourceSpans": ["not-a-dict"]}`

Added two regression tests to `tests/test_usage_capture.py`:
- `test_copilot_otel_non_dict_top_level_line_skipped` — non-dict top-level decoded line
- `test_copilot_otel_non_dict_resource_span_element_skipped` — non-dict `resourceSpans`
  element

**Verification:**
- Tier 1: re-read modified sections in both files, fix text present, surrounding code
  intact.
- Tier 2: `python3 -c "import ast; ast.parse(...)"` passed for both files.
- Full suite: `uv run pytest -q` → **802 passed** (800 baseline + 2 new regression
  tests, no regressions).
- `uv run ruff check .` → `All checks passed!`
- `uv run ruff format --check .` → `105 files already formatted`

## Skipped Issues

None — the single in-scope finding (CR-01) was fixed.

_Note: IN-01, IN-02, IN-03 are Info-tier findings, explicitly out of scope for this run
(fix_scope: critical_warning). They remain documented in `10-REVIEW.md`, unaddressed,
for a future `--all` pass if desired._

---

_Fixed: 2026-06-30T10:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3_
