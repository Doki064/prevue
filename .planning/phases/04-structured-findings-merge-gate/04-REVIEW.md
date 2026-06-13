---
phase: 04-structured-findings-merge-gate
reviewed: 2026-06-13T12:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - pyproject.toml
  - src/prevue/engines/parsing.py
  - src/prevue/models.py
  - src/prevue/engines/copilot_cli.py
  - src/prevue/github/positions.py
  - src/prevue/gate.py
  - src/prevue/github/comments.py
  - src/prevue/github/checks.py
  - src/prevue/github/client.py
  - src/prevue/review.py
  - .github/workflows/review.yml
findings:
  critical: 0
  warning: 5
  info: 2
  total: 7
status: flagged
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-13T12:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** flagged

## Summary

Reviewed Phase 4 implementation across parsing, gate policy, GitHub rendering, check-run merge gate, and `run_review` wiring. Core contracts (last-fence extraction, strict salvage, unidiff position sets, conclusion ladder, batched inline POST, completed-only check run) are implemented coherently and match plan intent. No critical security or crash bugs found in the happy path.

Five warnings remain: silent inline-review failure leaves misleading sticky placement labels; unhandled check-run API errors can red-X an otherwise successful review; file paths in engine prompts are not escaped in diff headers; `Finding` boundary validation is loose on `side`/`line`; inline comment titles are not markdown-escaped (table cells are). Two info items note redundant GitHub client construction and a suppressed type hint.

## Warnings

### WR-01: Inline POST failure leaves sticky claiming inline placement

**File:** `src/prevue/review.py:85-92`, `src/prevue/github/comments.py:215-242`
**Issue:** When `post_inline_review` returns `False` (422 or other `GithubException`), `run_review` ignores the return value and still posts a sticky whose findings table shows `💬 inline` badges for those findings. Consumers see inline placement in the summary but no inline comments on the diff — contradicts 04-RESEARCH Pitfall 2 guidance to fall back to summary-only on batch failure.
**Fix:** Capture the return value; on failure, rebuild `GateResult` (or a render-only overlay) that downgrades affected findings to `summary-only` before `upsert_sticky`, and log a single stderr line. Minimal v1 alternative: append a Metadata notice when inline POST fails.

### WR-02: `create_check_run` errors unhandled — job can red-X after successful review

**File:** `src/prevue/github/checks.py:41-47`, `src/prevue/review.py:93-98`
**Issue:** `conclude_review_check` and `conclude_skip_check` call `repo.create_check_run` with no try/except. A 403/422 from the Checks API (misconfigured permissions, rate limit, invalid SHA) propagates uncaught, failing the workflow even though inline review and sticky may have succeeded.
**Fix:** Wrap `create_check_run` in try/except `GithubException`, log sanitized status/message to stderr, and either re-raise only when check is mandatory or return a bool so `run_review` can document partial success. At minimum mirror `post_inline_review`'s swallow-and-log pattern for consistency.

### WR-03: File path not escaped in diff hunk prompt headers

**File:** `src/prevue/engines/copilot_cli.py:94-96`
**Issue:** Changed-file paths in the `## Changed files` section use `_escape_line` (JSON-encoded), but diff hunk headers embed raw `f.path` in `### {f.path}`. A path containing backticks or newlines (unlikely from GitHub but possible in adversarial PRs) can break the surrounding ` ```UNTRUSTED DATA ` fence and alter prompt structure seen by the engine.
**Fix:** Use `_escape_line(f.path)` or a dedicated header sanitizer for the `###` line, matching the escaping applied in the changed-files list.

### WR-04: `Finding` model lacks `side` Literal and positive `line` constraint

**File:** `src/prevue/models.py:33-40`
**Issue:** `side` is untyped `str` (not `Literal["RIGHT", "LEFT"]`) and `line` has no `Field(ge=1)`. Invalid sides are filtered by position logic today, but `line=0` or negative values pass strict validation and could reach GitHub if placeability logic ever loosens. Engine typos like `"right"` silently become position-fallback instead of salvage drops.
**Fix:**

```python
side: Literal["RIGHT", "LEFT"] = "RIGHT"
line: int = Field(ge=1)
```

Salvage path in `validate_findings` will then drop bad rows per D-03.

### WR-05: Inline comment title not markdown-escaped

**File:** `src/prevue/github/comments.py:37-44`
**Issue:** `render_inline_comment` injects `finding.title` raw into `**{finding.title}**`. Engine-emitted titles containing `**`, newlines, or `#` headings can break comment layout or inject spurious markdown sections. `_escape_table_cell` hardens table rows but is not applied here.
**Fix:** Sanitize title for inline use — e.g. strip/replace newlines and escape markdown metacharacters, or reuse a shared `_escape_inline_markdown(title)` helper.

## Info

### IN-01: Redundant GitHub client construction in `run_review`

**File:** `src/prevue/review.py:54`, `src/prevue/review.py:94`
**Issue:** `get_repo(ctx)` is called twice (skip path once; happy path once at check time), each constructing a new `Github(auth=...)`. Functional but wasteful and harder to mock consistently.
**Fix:** Resolve `repo = get_repo(ctx)` once after `load_pr_context()` and pass it to check helpers.

### IN-02: Suppressed type on `GateResult.conclusion`

**File:** `src/prevue/gate.py:135`
**Issue:** `conclusion=conclusion,  # type: ignore[arg-type]` masks a `str` → `Conclusion` mismatch. `conclude()` returns plain `str`; a future edit could return an invalid conclusion without static checking.
**Fix:** Annotate `conclude(...) -> Conclusion` or cast explicitly: `conclusion=cast(Conclusion, conclusion)`.

---

_Reviewed: 2026-06-13T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
