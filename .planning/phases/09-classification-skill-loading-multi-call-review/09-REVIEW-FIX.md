---
phase: 09-classification-skill-loading-multi-call-review
fixed_at: 2026-06-23T00:00:00Z
review_path: .planning/phases/09-classification-skill-loading-multi-call-review/09-REVIEW.md
iteration: 3
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-06-23
**Source review:** .planning/phases/09-classification-skill-loading-multi-call-review/09-REVIEW.md
**Iteration:** 3

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-11: The WR-08 durable partial-marker fix ships with no regression test

**Files modified:** `tests/test_comments.py`, `tests/test_review_flow.py`
**Commit:** f0d5ba2
**Applied fix:** Added two layers of regression coverage for the WR-08 durable
partial-marker round-trip.
1. `tests/test_comments.py::TestRenderBodyPartialMarker` — unit tests asserting
   `render_body(...)` emits `PARTIAL_MARKER` for each partial trigger
   (`not_reviewed_file_count`, `run_budget_reached` + count, `skipped_paths`, and bare
   `partial_marker=True`), omits it on a clean render, and that the marker survives a
   re-feed across two consecutive no-op renders.
2. `tests/test_review_flow.py::TestPartialMarkerNoopRoundTrip` — integration tests that
   drive the real `render_body` to build a partial sticky body and feed it back through
   the real `_prior_review_was_partial(pr)` (via the `read_newest_trusted_sticky_body`
   patch point), reproducing the original 3-step break (partial review → no-op #1 →
   no-op #2) and proving the partial signal survives both no-ops so `neutral` is never
   silently upgraded to `success`.
All 8 new tests pass.

### WR-12: `ReviewConfig.max_total_run_tokens` docstring states "4× max_tokens_per_call" but the default is a flat 500_000

**Files modified:** `src/prevue/gate.py`
**Commit:** f3f55bb
**Applied fix:** Updated the `ReviewConfig` docstring for `max_total_run_tokens` to read
"default 500_000 (A3 starting point) — a flat constant, not derived from
max_tokens_per_call", matching the field default (`Field(default=500_000, ...)`) and the
already-correct `docs/configuration.md` and `docs/ARCHITECTURE.md`. Chose the
docstring-correction option (over a computed `4 *` validator) because the flat 500_000
default is the value the rest of the documentation already commits to.

---

_Fixed: 2026-06-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3_
