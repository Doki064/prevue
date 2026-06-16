---
phase: "08"
phase_name: "incremental-stateful-review-lifecycle"
status: "clean"
depth: "standard"
files_reviewed: 4
files_reviewed_list:
  - src/prevue/review.py
  - src/prevue/github/comments.py
  - src/prevue/engines/cursor_cli.py
  - .github/workflows/prevue-review.yml
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
reviewed_at: "2026-06-15T19:40:35Z"
---

# Phase 08 (gap-closure 08-08..08-10): Code Review Report (Pass 1/3)

**Reviewed:** 2026-06-15T19:40:35Z
**Depth:** standard
**Files Reviewed:** 4 (gap-closure scope: 08-08, 08-09, 08-10)
**Status:** clean

## Summary

Gap-only re-review run after workflow preflight update. No Critical/Warning findings remain in scope.

Validated outcomes:

- `src/prevue/github/comments.py`: `upsert_sticky` forwards `scope` and `carried_open_count` to `render_body`; incremental disclaimer path is reachable.
- `src/prevue/review.py`: `_open_set_findings` now gates rephrase suppression by `current_locs`, preserving severity escalations.
- `.github/workflows/prevue-review.yml`: preflight sticky lookup now uses `gh api --paginate` with `per_page=100`, so same-SHA noop detection is no longer limited to first page.
- `tests/test_reusable_workflow_yaml.py`: added static guard requiring pagination in preflight sticky lookup.

## Pass 1 Findings

No active findings (CR/WR/IN): 0.

_Reviewed: 2026-06-15T19:40:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Scope: gap-closure plans 08-08, 08-09, 08-10_
_Iteration: 1 of 3 (auto mode, stopped early: clean)_

---

## Prior Review Iterations (reference)

The following sections from the prior review cycle (iterations 1-3, pre-gap-closure) are preserved below for traceability. All findings in those iterations were previously marked resolved.

---

# Phase 08: Code Review Report (Iteration 3 — Final Re-Review)

**Reviewed:** 2026-06-15T10:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** clean

## Summary

This is the final re-review after two fix passes (10 total fixes applied across iterations 1 and 2). All previously flagged issues are resolved. No regressions were introduced and no new defects were found.

The three warnings from iteration 2 (WR-01, WR-02, WR-03) were addressed as follows:

**WR-01 (post_inline_review current_fingerprints uses gate.inline — iteration 2 fix):** Verified resolved at `comments.py:749-750`. The code now uses `gate.placed` (all tracked findings regardless of placement budget):
```python
current_fingerprints = {
    fingerprint(pf.finding.path, pf.finding.title) for pf in gate.placed
}
```
This correctly prevents resolving threads for findings that are still active but demoted to `summary-only`. The test `test_post_inline_resolve_outdated_integration` exercises this path.

**WR-02 (`_thread_id_by_location` key includes `side` — iteration 2 fix):** Verified resolved. `REVIEW_THREADS_QUERY` now includes `side` in the node fields (`graphql.py:26`). `fetch_review_threads` stores `"side": node.get("side")` (`graphql.py:89`). `_thread_id_by_location` keys on `(path, line, side)` with a `"RIGHT"` default when `side` is null (`comments.py:105-119`). The fixture `graphql_review_threads.json` includes `"side": "RIGHT"` on both thread nodes and the test at `test_comments.py:1127-1148` verifies the 3-tuple lookup returns the correct thread ID.

**WR-03 (`_finish_noop_review` empty `valid_lines` — iteration 2 fix):** Verified resolved. An explicit comment was added to `review.py:193-198` explaining that passing `{}` is intentional in the noop path because `gate.inline` and `gate.placed` are never rendered there, and documenting the prerequisite for any future extension.

**IN-01 (key shape asymmetry undocumented — iteration 2 fix):** The fix to WR-02 makes both `_thread_id_by_location` and `_existing_prevue_inline_by_location` use `(path, line, side)` 3-tuples, eliminating the asymmetry entirely. The docstring addition noted in IN-01 is no longer needed.

**All 10 fixes across both iterations verified correct. No remaining issues.**

---

_Reviewed: 2026-06-15T10:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 3 of 3 (final --auto pass)_

---

## Iteration 1 — Initial Review (2026-06-15T14:30:00Z)

**Files reviewed:** 24 | **Status:** findings | **Depth:** standard

### CR-01 | `resolve_outdated_prior_findings` unguarded — GraphQL fetch failure crashes job after engine run

**File:** `src/prevue/github/comments.py:174`, `src/prevue/review.py:534-542`
**Severity:** Critical

`run_review` calls `resolve_outdated_prior_findings` with no exception handler. `fetch_review_threads` inside can raise `KeyError` (`GITHUB_TOKEN`), `requests.RequestException`, `requests.HTTPError`, `GraphQLError`, or a `KeyError` from an unexpected response shape. `derive_prior_findings` wraps the identical call in `try/except Exception`; `resolve_outdated_prior_findings` does not. When the exception propagates, the job fails after the engine has already run — no sticky comment, no check run posted. Consumer docs claim 403 is "best-effort skipped"; that is only true for the resolve mutation, not the fetch query.

**Fix:** Wrap `fetch_review_threads` in try/except at the top of `resolve_outdated_prior_findings`; return `set()` on failure.

---

### CR-02 | Open-set deduplication uses `(path, line)` — wrong suppression across diff sides

**File:** `src/prevue/review.py:153,158`
**Severity:** Critical

`_open_set_findings` and `_dedupe_findings_by_location` key on `(path, line)`, ignoring `side`. A current RIGHT-side finding at line 10 suppresses a prior LEFT-side finding at the same line. The prior disappears silently from the open set; `inline_location_key` everywhere else is `(path, line, side)`. No test covers the LEFT-vs-RIGHT case.

**Fix:** Change both functions to use `(path, line, side)` as the location key.

---

### WR-01 | Byte-limit guard excludes known-issues bytes

**File:** `src/prevue/review.py:336-337,441`
**Severity:** Warning

The guard calls the module-level imported `build_prompt` (line 26), which has no `known_issues`. The actual engine prompt is built with the monkey-patched version that injects them. On near-limit incremental runs, the actual bytes sent can exceed `MAX_PROMPT_BYTES`.

**Fix:** Pass `known_issues=known_items` to the guard's `build_prompt` call; move `known_items` construction before the guard.

---

### WR-02 | GraphQL pagination infinite loop when `endCursor` is null with `hasNextPage=true`

**File:** `src/prevue/github/graphql.py:88-91`
**Severity:** Warning

If `hasNextPage: true` is returned with `endCursor: null`, `cursor` becomes `None`, is excluded from the next request, and the same page is fetched forever until the 6-hour Actions timeout.

**Fix:** Break the pagination loop with a stderr warning when `cursor` is falsy but `hasNextPage` is true.

---

### WR-03 | Double `fetch_review_threads` round-trip on every review run

**File:** `src/prevue/review.py:497,535`
**Severity:** Warning

With default config, `run_review` fetches review threads twice independently. Data from the first call is discarded before the second.

**Fix:** Extract `_derive_prior_findings_with_threads` returning `(priors, threads)`; pass threads into `resolve_outdated_prior_findings` to skip the second fetch.

---

### WR-04 | `_severity_escalated` treats unparseable prior severity as escalation target

**File:** `src/prevue/github/comments.py:211-216`
**Severity:** Warning

Returns `True` when `parse_severity_from_body` returns `None`. Any comment with an unrecognized badge triggers an edit on every run, violating D-06.

**Fix:** Return `False` when prior severity is unparseable.

---

### WR-05 | Global monkey-patch of `build_prompt` leaks state and is ineffective

**File:** `src/prevue/review.py:513-526`
**Severity:** Warning

`run_review` monkey-patches `prevue.engines.prompt.build_prompt` at module level. Engine adapters that imported `build_prompt` by name at load time are unaffected. Creates test pollution risk if `finally` is skipped.

**Fix:** Add `known_issues` and `max_known_issues` to `ReviewRequest`; pass them directly to `build_prompt` in `flow.review_with_retry`.

---

### IN-01 | `fetch_review_threads` fetches thread body text no caller reads

**File:** `src/prevue/github/graphql.py:76-86` — Info only.

### IN-02 | No test for LEFT-side prior surviving against RIGHT-side current at same line

**File:** `tests/test_review_flow.py` — Info only.

### IN-03 | `docs/consumer-setup.md` documents 403 as best-effort but omits fetch failure risk

**File:** `docs/consumer-setup.md:118` — Info only.

---

## Iteration 2 — Re-Review (2026-06-15T12:00:00Z)

**Files reviewed:** 18 | **Status:** issues_found | **Depth:** standard

All 7 previously-flagged issues confirmed fixed. No regressions. Three new warnings found.

### WR-01 | `post_inline_review` computes `current_fingerprints` from `gate.inline` subset

**File:** `src/prevue/github/comments.py:743-750`
**Severity:** Warning

When `resolve_outdated=True`, uses `gate.inline` (budget-capped) for `current_fingerprints`. A finding demoted to `summary-only` due to `max_inline_comments` is absent, so `resolve_outdated_prior_findings` treats it as "gone" and incorrectly resolves the thread. The `run_review` call site avoids this via `resolve_outdated=False`, but the public API contract is wrong.

**Fix:** Use `gate.placed` instead of `gate.inline`.

---

### WR-02 | `_thread_id_by_location` uses `(path, line)` — silent collision on different-side threads

**File:** `src/prevue/github/comments.py:105-113`
**Severity:** Warning

Two threads at same file+line on different sides silently overwrite each other. `REVIEW_THREADS_QUERY` did not request `side`.

**Fix:** Add `side` to `REVIEW_THREADS_QUERY`; change `_thread_id_by_location` to key on `(path, line, side)`.

---

### WR-03 | `_finish_noop_review` passes `valid_lines={}` — all priors land on `position-fallback`

**File:** `src/prevue/review.py:190-194`
**Severity:** Warning

Harmless currently (gate is verdict-only in noop path), but a latent footgun if the path is extended to render a sticky from `gate.placed`.

**Fix:** Add a comment documenting the intent.

---

### IN-01 | Key shape asymmetry between `_thread_id_by_location` (2-tuple) and `_existing_prevue_inline_by_location` (3-tuple) undocumented — Info only.
