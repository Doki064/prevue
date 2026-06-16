---
phase: 08-incremental-stateful-review-lifecycle
plan: "09"
subsystem: github/comments
tags: [gap-closure, gfm, inline-comments, incremental-disclaimer, life-02]
dependency_graph:
  requires: ["08-08"]
  provides: ["GFM-safe INLINE_MARKER", "backward-compat legacy marker detection", "incremental scope disclaimer"]
  affects: ["src/prevue/github/comments.py", "tests/test_comments.py"]
tech_stack:
  added: []
  patterns:
    - "LEGACY_INLINE_MARKER constant for backward-compat dual-detection"
    - "Deterministic disclaimer constant (_INCREMENTAL_SCOPE_DISCLAIMER) for incremental sticky Review prose"
    - "TDD RED/GREEN cycle for gap #5 disclaimer feature"
key_files:
  modified:
    - src/prevue/github/comments.py
    - tests/test_comments.py
decisions:
  - "GFM emphasis `_posted by Prevue_` replaces HTML `<sub>posted by Prevue</sub>` as INLINE_MARKER — GitHub inline review comments support GFM only, so raw HTML was rendering literally (gap #2)"
  - "LEGACY_INLINE_MARKER retained as constant for backward-compatible detection — live PRs (e.g. #23) carry old-format comments that must still be detected for carry-forward/dedupe/resolve"
  - "Dual detection in _is_prevue_inline_comment: new GFM marker OR legacy HTML marker, combined with trusted-actor gate (T-08-09-01 mitigated)"
  - "Disclaimer text is a module-level deterministic constant, not derived from engine output — prevents LLM injection into the scope framing (T-08-09-02 mitigated)"
  - "scope and carried_open_count params default to None/0 — all existing callers remain unaffected"
metrics:
  duration: 5min
  completed: "2026-06-15"
  tasks: 2
  files: 2
---

# Phase 08 Plan 09: GFM Inline Marker + Incremental Scope Disclaimer Summary

**One-liner:** GFM-safe `_posted by Prevue_` inline footer with backward-compat legacy detection, plus deterministic incremental scope + carried-finding disclaimer in the sticky Review section.

## What Was Built

### Task 1: GFM-safe inline marker with backward-compatible detection (gap #2)

Changed `INLINE_MARKER` from the HTML `<sub>posted by Prevue</sub>` to the GFM emphasis `_posted by Prevue_`. GitHub inline review comments render GFM only, so the old HTML was displaying as a literal raw tag on PR #23 and any other PR with Prevue inline comments.

Added `LEGACY_INLINE_MARKER = "<sub>posted by Prevue</sub>"` and updated `_is_prevue_inline_comment` to detect a comment body containing **either** the new GFM marker **or** the legacy HTML marker. This keeps carry-forward, dedupe, and resolve working on PRs that already have comments stamped with the old marker (e.g. live PR #23). The trusted-actor gate (`_is_trusted_sticky_actor`) is unchanged — dual detection does not relax that gate.

`render_inline_comment` continues to append `INLINE_MARKER` (now the GFM form), so newly posted comments use the GFM footer going forward.

Updated the render assertion in `TestRenderInlineComment` to expect the new marker. Added `TestInlineMarkerDetection` with 6 tests covering: new GFM marker detected, legacy sub detected, no-marker body rejected, constant value assertions, and render confirmation.

### Task 2: Deterministic incremental scope + carried-finding disclaimer (gap #5) — TDD

Added two module-level deterministic constants:
- `_INCREMENTAL_SCOPE_DISCLAIMER`: a blockquote noting the review is scoped to files changed since the last reviewed commit and that prior open findings on unchanged files are carried forward
- `_INCREMENTAL_CARRIED_CLAUSE`: a clause appended when `carried_open_count > 0`, stating the count of prior open findings that may be on files outside this incremental diff

Added optional `scope: str | None = None` and `carried_open_count: int = 0` parameters to `render_body`. When `scope == "incremental"`, the Review section content is prefixed with the deterministic disclaimer (plus carried clause if count > 0) before the HTML-neutralized engine summary. When `scope` is `"full"` or `None` (default), behavior is completely unchanged — all existing callers are unaffected.

TDD RED commit (`4ad947e`) added 6 failing tests in `TestRenderBodyIncrementalDisclaimer`. GREEN commit (`0577d61`) implemented the feature making all 6 pass. No REFACTOR phase needed.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| d60e1ac | feat | GFM-safe INLINE_MARKER + backward-compatible legacy detection (task 1) |
| 4ad947e | test | RED: add failing disclaimer tests (task 2) |
| 0577d61 | feat | GREEN: deterministic incremental scope disclaimer in render_body (task 2) |

## Tests

All 100 tests in `tests/test_comments.py` pass. New tests added:

- `TestInlineMarkerDetection` (6 tests): GFM marker detected, legacy HTML detected, no-marker rejected, constant value assertions, render uses GFM
- `TestRenderBodyIncrementalDisclaimer` (6 tests): scope disclaimer present, carried count mentioned, zero-count no clause, full/default no disclaimer, deterministic text

## Deviations from Plan

### Pre-existing Ruff Warnings (Out of Scope)

Pre-existing `I001` (import sort) and `E501` (line too long) warnings in `comments.py` were present before this plan and confirmed pre-existing via `git stash` check. Not fixed per scope boundary rule — logged to deferred items.

No other deviations.

## Threat Surface Scan

| Threat | Status |
|--------|--------|
| T-08-09-01: Spoofing via broadened marker detection | Mitigated — dual detection still requires trusted-actor gate AND marker; no relaxation of `_is_trusted_sticky_actor` |
| T-08-09-02: Tampering via disclaimer prepend | Mitigated — disclaimer is a deterministic constant; engine summary still `_neutralize_html`-wrapped |
| T-08-09-03: GFM marker breakout | Accepted — `_posted by Prevue_` is plain GFM emphasis with no executable surface |

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- [x] `src/prevue/github/comments.py` exists and was modified
- [x] `tests/test_comments.py` exists and was modified
- [x] Commit d60e1ac exists (task 1)
- [x] Commit 4ad947e exists (task 2 RED)
- [x] Commit 0577d61 exists (task 2 GREEN)
- [x] `uv run pytest tests/test_comments.py -q` exits 0 (100 passed)
- [x] `INLINE_MARKER = "_posted by Prevue_"` present in comments.py
- [x] `LEGACY_INLINE_MARKER` present in comments.py (exactly 1 HTML occurrence)
- [x] `scope` and `carried_open_count` params in `render_body` signature
