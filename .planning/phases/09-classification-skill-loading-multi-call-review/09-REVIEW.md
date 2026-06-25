---
phase: 09-classification-skill-loading-multi-call-review
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - docs/ARCHITECTURE.md
  - docs/configuration.md
  - src/prevue/classify/llm_fallback.py
  - src/prevue/engines/base.py
  - src/prevue/gate.py
  - src/prevue/github/comments.py
  - src/prevue/importscan.py
  - src/prevue/multicall.py
  - src/prevue/review.py
  - src/prevue/skills/loader.py
  - src/prevue/skills/selection.py
  - tests/conftest.py
  - tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md
  - tests/test_comments.py
  - tests/test_config.py
  - tests/test_importscan.py
  - tests/test_llm_fallback.py
  - tests/test_multicall.py
  - tests/test_review_flow.py
  - tests/test_selection.py
findings:
  critical: 0
  warning: 2
  info: 6
  total: 8
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-23
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Iteration-2 re-review after the WR-08/WR-09/WR-10 fixes. All three iteration-1 warnings
are genuinely addressed in code (not merely annotated), and the full suite (712 tests)
passes:

- **WR-08** — `render_body` now emits a durable machine-readable `PARTIAL_MARKER`
  (`<!-- prevue:partial -->`) in the stable header whenever a render leaves files
  unreviewed OR the caller carries a recovered partial state via the new
  `partial_marker` kwarg (comments.py:646-656). `_finish_noop_review` threads
  `partial_marker=prior_partial` (review.py:462) and `_PARTIAL_COVERAGE_MARKERS` lists
  the durable marker first (review.py:389-394). The partial signal now survives an
  arbitrary number of consecutive no-op re-runs. The logic is correct.
- **WR-09** — `CallGroup.instructions` is removed; the docstring Note states there is no
  per-group scoping (multicall.py:55-63). `test_call_group_is_a_dataclass_or_model`
  asserts `not hasattr(group, "instructions")` so the model can't silently re-drift.
- **WR-10** — `_supports_skill_classify` now gates on `isinstance(adapter, EngineAdapter)`
  before inspecting the overridden method (selection.py:148-153). Verified all four
  concrete adapters (copilot/cursor/claude_code/gemini) subclass `EngineAdapter`, so the
  real escalation path is unaffected; MagicMock/duck-typed doubles are conservatively
  treated as unsupported.

Two findings remain open. WR-11 (new) is the most important: the WR-08 durable-marker
fix — a correctness-critical guard against silently upgrading a partial review to a clean
pass — landed with **zero regression test coverage**, exactly the kind of fix that should
ship with a test reproducing the prior break. WR-12 is a doc/code default mismatch. The
five carried Info items (IN-01..IN-05) plus one new doc inconsistency (IN-06) are
maintainability gaps that were out of the `critical_warning` fix tier.

## Narrative Findings (AI reviewer)

## Warnings

### WR-11: The WR-08 durable partial-marker fix ships with no regression test — the exact break it closes is unguarded

**File:** `src/prevue/github/comments.py:646-656`, `src/prevue/review.py:389-410, 462`
(test gap across `tests/test_comments.py`, `tests/test_review_flow.py`)
**Issue:** The WR-08 fix is correct, but nothing tests it. A grep across the full test
tree for `prevue:partial`, `PARTIAL_MARKER`, `partial_marker=`, or `_prior_review_was_partial`
returns nothing. Specifically:
- No test asserts `render_body(...)` emits `PARTIAL_MARKER` when
  `not_reviewed_file_count > 0` / `run_budget_reached` / `skipped_paths` are set, nor when
  `partial_marker=True` is passed explicitly.
- No test reproduces the original 3-step break (partial real review → no-op #1 → no-op #2)
  to prove a second consecutive no-op can no longer upgrade `neutral`→`success`. The
  existing no-op tests (`test_identical_rerun_noop_skips_engine`,
  `test_incremental_false_same_sha_is_noop_not_full`) mock `upsert_sticky`, so the
  marker round-trip through `render_body` → `read_newest_trusted_sticky_body` →
  `_prior_review_was_partial` is never exercised end to end.

The fix correctly emits the marker, but its entire value is preventing a silent
data-integrity regression (a partial review being reported as a clean pass). If a future
edit to `render_body`'s `is_partial` predicate, the marker placement, or the
`_PARTIAL_COVERAGE_MARKERS` tuple breaks the round-trip, every test still passes. The fix
report itself flagged WR-08 as "requires human verification (logic)" — that is precisely
the signal that a regression test is owed.
**Fix:** Add two targeted tests:
1. A `render_body` unit test asserting `PARTIAL_MARKER in body` for each partial trigger
   (`not_reviewed_file_count`, `run_budget_reached`+count, `skipped_paths`, and bare
   `partial_marker=True`) and `PARTIAL_MARKER not in body` for a clean render.
2. A flow/integration test that drives `render_body` (real, un-mocked) to build a partial
   sticky body, feeds it back through `_prior_review_was_partial(pr)`, and asserts a
   double no-op keeps the conclusion `neutral` (no `success` upgrade on no-op #2). A
   string-level test that re-runs `render_body(partial_marker=_prior_review_was_partial(...))`
   twice and asserts the marker survives both passes is sufficient.

### WR-12: `ReviewConfig.max_total_run_tokens` docstring states "4× max_tokens_per_call" but the actual default is a flat 500_000

**File:** `src/prevue/gate.py:28-29, 53`
**Issue:** The `ReviewConfig` class docstring documents
`max_total_run_tokens — whole-run ceiling (classify + Σ review calls); default 4×
max_tokens_per_call (A3 starting point)`. The field default is `Field(default=500_000, ...)`.
With the `max_tokens_per_call` default of `120000`, "4×" would be `480000`, not `500000`,
and the default is in fact a hardcoded constant that does not track `max_tokens_per_call`
at all (set `max_tokens_per_call: 200000` and the run cap stays `500000`, i.e. 2.5×, not
4×). The docstring describes a relationship the code does not implement. A consumer
reading the docstring will mis-budget; an operator tuning `max_tokens_per_call` will not
get the documented proportional run cap. `docs/configuration.md:104` and
`docs/ARCHITECTURE.md:135` both correctly state `500000`, so the in-code docstring is the
sole disagreeing source.
**Fix:** Change the docstring to "default 500_000 (A3 starting point); a flat constant,
not derived from max_tokens_per_call" — or, if the 4× relationship was intended, make the
default a computed validator (`default = 4 * max_tokens_per_call`) and keep the docstring.
Pick one so the model and the prose agree.

## Info

### IN-01: `merge_findings` module docstring still contradicts the implemented dedup key

**File:** `src/prevue/multicall.py:12-14` (vs function summary line 399, body line 454)
**Issue:** (Carried from prior IN-01, still unfixed.) The module docstring says merge
deduplicates "by `fingerprint(path, title)`", while the function summary (line 399) and
body (line 454) implement the richer `(fingerprint(path,title), line, side)` key.
`docs/ARCHITECTURE.md:64` documents the correct richer key, so the module docstring is now
the only source still stating the old key.
**Fix:** Update the module docstring (lines 12-14) to state the `(fingerprint, line, side)`
key, matching the function docstring and ARCHITECTURE.md.

### IN-02: `_group_tokens` fallback uses an undocumented magic number on an effectively dead branch

**File:** `src/prevue/multicall.py:225-227`
**Issue:** (Carried from prior IN-03, unfixed.) The greedy-merge proxy falls back to
`len(gfiles) * 1000` when `estimate_file_prompt_tokens` can't be imported. `1000` is an
unnamed magic number and the `except (ImportError, AttributeError)` branch is effectively
unreachable (pack.py imports the estimator unconditionally with no circular risk).
**Fix:** Import `estimate_file_prompt_tokens` at module top and drop the try/except, or name
the constant `_FALLBACK_TOKENS_PER_FILE = 1000` with a comment.

### IN-03: Local (non-Actions) consumer-skills fallback returns no disclosure when the skills dir is absent

**File:** `src/prevue/review.py:108-114` (consumer-root resolution)
**Issue:** (Carried from prior IN-04, unfixed.) Outside Actions with `PREVUE_CONSUMER_ROOT`
unset, the `GITHUB_WORKSPACE` fallback returns `(None, None)` with no note when
`.github/prevue/skills` is missing — asymmetric with the in-Actions branch that always
returns a note. Correct behavior, but a local misconfiguration produces zero disclosure.
**Fix:** Optionally emit a stderr debug line when the workspace fallback finds no skills dir,
for parity.

### IN-04: RED-state import shims remain in GREEN test modules

**File:** `tests/test_multicall.py:11-20`, `tests/test_importscan.py:11-18`,
`tests/test_selection.py:11-19`, `tests/test_llm_fallback.py:6-12`
**Issue:** (Carried from prior IN-05, unfixed.) Each module keeps the
`try: import … except ImportError: _MISSING` RED scaffold plus a `_require_module()` guard
called at the top of every test. Now that the modules exist these guards are inert noise and
weaken signal: a genuine future `ImportError` would `pytest.fail` with a "not yet
implemented" message rather than surfacing the real traceback.
**Fix:** Replace the scaffolds with direct top-level imports now that the phase is GREEN; let
a real `ImportError` fail collection normally.

### IN-05: `projected_calls` over-projection is documented only in the fix note, not the source

**File:** `src/prevue/review.py:893`
**Issue:** (Carried from prior IN-05/WR-01 follow-up, unfixed.) `projected_calls =
max(1, min(max_review_calls, len(packed_files)))` deliberately upper-bounds the call count;
the splitter can emit *fewer* calls after greedy merging, so the run-cap projection
systematically over-counts instruction overhead and may drop files (cap-repack) that would
in fact have fit. This is the safe direction, but the asymmetry lives only in the fix note,
which won't survive into the source tree.
**Fix:** Add a one-line comment at review.py:893 stating the projection intentionally
over-estimates calls (splitter merges may produce fewer), so the run cap is a safe upper
bound that may undershoot coverage rather than overshoot spend. No behavior change needed.

### IN-06: Guardrail-forced skills are mislabeled "routed" in the skill-source provenance line

**File:** `src/prevue/review.py:1177-1186`
**Issue:** (New.) `_skill_sources` attributes each matched skill to "keyword" / "llm" /
"routed". A skill force-loaded by `review.guardrail_skills` (via `_refresh_matched`'s
`guardrail_keys` path) that is below `KEYWORD_THRESHOLD`, not in a routed bundle, and not in
`llm_skill_names` falls into the `else` branch and is labeled `"routed"` in the sticky
`Skills:` line — even though it was loaded as an always-on guardrail, not by routing. This
is a disclosure-accuracy nit (display only; no behavior impact), but it can mislead an
operator auditing why a skill loaded.
**Fix:** Add a `"guardrail"` source: when `f"{s.bundle}/{s.filename}" in
review_cfg.guardrail_skills`, label the entry `"guardrail"` ahead of the `"routed"`
fallback.

---

_Reviewed: 2026-06-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
