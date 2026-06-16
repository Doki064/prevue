---
phase: 08-incremental-stateful-review-lifecycle
fixed_at: 2026-06-15T12:30:00Z
review_path: .planning/phases/08-incremental-stateful-review-lifecycle/08-REVIEW.md
iterations: 2
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 08: Code Review Fix Report

**Final status:** all_fixed | **Iterations:** 2 | **Total fixed:** 10 / 10

---

## Iteration 1 Fixes (2026-06-15T15:10:00Z)

**Findings in scope:** 7 | **Fixed:** 7 | **Skipped:** 0

### CR-01: `resolve_outdated_prior_findings` unguarded — GraphQL fetch failure crashes job

**Files:** `src/prevue/github/comments.py`
**Commit:** `e844a68`

Added `try/except Exception` guard around `fetch_review_threads` at the top of `resolve_outdated_prior_findings`. On any exception, logs to stderr and returns `set()`, matching the pattern in `derive_prior_findings`. Also added `threads: list[dict] | None = None` parameter as prerequisite for WR-03.

---

### CR-02: Open-set deduplication uses `(path, line)` — wrong suppression across diff sides

**Files:** `src/prevue/review.py`
**Commit:** `07de877`

Updated `_dedupe_findings_by_location` and `_open_set_findings` to use `(path, line, side)` as the location key. A prior at `(path, line, LEFT)` is no longer silently dropped when a current finding exists at `(path, line, RIGHT)`.

---

### WR-01: Byte-limit guard excludes known-issues bytes

**Files:** `src/prevue/review.py`
**Commit:** `20b66e9`

Moved `priors` and `known_items` construction before the byte-limit guard. Updated the guard to call `build_prompt(prompt_probe, known_issues=known_items, max_known_issues=review_cfg.max_known_issues)` so the known-issues block is included in the byte count.

---

### WR-02: GraphQL pagination infinite loop when `endCursor` is null

**Files:** `src/prevue/github/graphql.py`
**Commit:** `4ce77b2`

Added a guard after extracting `endCursor`: if `cursor` is falsy when `hasNextPage` is true, logs a warning to stderr and breaks the loop.

---

### WR-03: Double `fetch_review_threads` round-trip

**Files:** `src/prevue/github/comments.py`, `src/prevue/review.py`
**Commit:** `bea14a4`

Extracted `_derive_prior_findings_with_threads` returning `(list[PriorFinding], list[dict])`. `run_review` calls it and passes the threads to `resolve_outdated_prior_findings` via `threads=fetched_threads`, halving GraphQL round-trips on default config.

---

### WR-04: `_severity_escalated` treats unparseable prior severity as escalation target

**Files:** `src/prevue/github/comments.py`, `tests/test_comments.py`
**Commit:** `422cdc2`

Changed `_severity_escalated` to return `False` when `parse_severity_from_body` returns `None`, per D-06. Updated test bodies to use parseable badge format so escalation tests still fire correctly.

---

### WR-05: Global monkey-patch of `build_prompt` leaks state and is ineffective

**Files:** `src/prevue/models.py`, `src/prevue/engines/flow.py`, `src/prevue/review.py`, `tests/test_review_flow.py`, `tests/test_comments.py`, `tests/test_engine_flow.py`
**Commit:** `2ed1f85`

Added `known_issues` and `max_known_issues` fields to `ReviewRequest`. `flow.review_with_retry` now passes them directly to `build_prompt`. Removed the monkey-patch block entirely. All 459 tests pass.

---

## Iteration 2 Fixes (2026-06-15T12:30:00Z)

**Findings in scope:** 3 | **Fixed:** 3 | **Skipped:** 0

### WR-01: `post_inline_review` computes `current_fingerprints` from `gate.inline` subset

**Files modified:** `src/prevue/github/comments.py`
**Commit:** bd7c919
**Applied fix:** Changed `fingerprint(f.path, f.title) for f in gate.inline` to
`fingerprint(pf.finding.path, pf.finding.title) for pf in gate.placed` so that findings
demoted to `summary-only` (budget-capped) are included in `current_fingerprints` when
`resolve_outdated=True`. This ensures `resolve_outdated_prior_findings` does not
incorrectly treat still-active summary-only findings as "gone".

---

### WR-02: `_thread_id_by_location` uses `(path, line)` key — silent collision on same-line different-side threads

**Files modified:** `src/prevue/github/graphql.py`, `src/prevue/github/comments.py`,
`tests/fixtures/graphql_review_threads.json`
**Commit:** c51dc5e
**Applied fix:**
- Added `side`, `startLine`, and `startSide` fields to `REVIEW_THREADS_QUERY` in graphql.py.
- Updated `fetch_review_threads` to include `"side": node.get("side")` in the returned dict.
- Changed `_thread_id_by_location` signature and implementation to key on `(path, line, side)`
  (3-tuple) with a `"RIGHT"` default when `side` is absent, preventing silent last-write-wins
  collision when two threads occupy the same file+line on different diff sides.
- Updated both lookup call sites (`_derive_prior_findings_with_threads` at the thread_ids.get
  call and `resolve_outdated_prior_findings` at its thread_ids.get call) to pass
  `(path, line, side)` keys — `side` is already available from the 3-tuple key returned by
  `_existing_prevue_inline_by_location`.
- Updated `tests/fixtures/graphql_review_threads.json` to include `side`, `startLine`, and
  `startSide` fields matching the expanded GraphQL response shape.

---

### WR-03: `_finish_noop_review` calls `apply_gate` with empty `valid_lines={}` — latent footgun undocumented

**Files modified:** `src/prevue/review.py`
**Commit:** 5545930
**Applied fix:** Added an explanatory comment above the `apply_gate` call in
`_finish_noop_review` documenting that `valid_lines={}` is intentional: in the noop path
the gate is verdict-only (conclusion + severity counts), `gate.inline` and `gate.placed`
are never rendered, so all priors landing on `position-fallback` is harmless. The comment
also warns future contributors to build `valid_lines` from the diff before extending this
path to render a sticky from `gate.placed`.

---

## Skipped Issues

None.

---

_Fixed: 2026-06-15T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
