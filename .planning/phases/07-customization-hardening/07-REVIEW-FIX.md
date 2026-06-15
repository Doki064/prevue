---
phase: 07-customization-hardening
fixed_at: 2026-06-14T21:55:00Z
review_path: .planning/phases/07-customization-hardening/07-REVIEW.md
review_rounds: 3
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-06-14 (rounds 1–3 complete)
**Source review:** `07-REVIEW.md`
**Final suite:** 347+ passed (full green after Round 3)

**Summary:**
- Review rounds: 3
- Critical/warning findings fixed: 11
- Info findings (IN-01..IN-04): intentionally out of scope (`critical_warning` batch)
- Skipped: 0

---

## Fix Round 1 — config, loader, review orchestration

**Scope:** CR-01, WR-01..WR-06 from initial review
**Commits:** `f2cf1a2`, `65f7045`, `182d5e8`, `3b8979f`, `a1c7123`, `3afe3da`, `f4a329b`

### CR-01: Config path validation — symlink/containment

**Files:** `src/prevue/config.py`
**Commit:** `f2cf1a2`
**Fix:** Rewrote `resolve_consumer_config_path` — resolved path is single containment
invariant; root anchors via `PREVUE_CONSUMER_ROOT` / `GITHUB_WORKSPACE` / cwd.

### WR-01: Duplicated path-traversal guards

**Files:** `src/prevue/config.py`
**Commit:** `65f7045`
**Fix:** Removed redundant `".." in path.parts` from `load_config`; resolver is sole source.

### WR-02: Classify tokens on full degrade

**Files:** `src/prevue/review.py`
**Commit:** `182d5e8`
**Fix:** Bill classify tokens only when `produced_real_labels` is truthy.

### WR-03: Skill cap counted frontmatter

**Files:** `src/prevue/skills/loader.py`
**Commit:** `3b8979f`
**Fix:** Parse frontmatter first; cap on `post.content` bytes.

### WR-04: Non-deterministic skill cap ordering

**Files:** `src/prevue/skills/loader.py`
**Commit:** `a1c7123`
**Fix:** Sorted `iterdir()` and skill file iteration by name.

### WR-05: None title/login skip crashes

**Files:** `src/prevue/skip.py`
**Commit:** `3afe3da`
**Fix:** `pr.title or ""`; `getattr(pr.user, "login", None)` with unknown-bot path.

### WR-06: Redundant engine re-resolution

**Files:** `src/prevue/review.py`
**Commit:** `f4a329b`
**Fix:** `get_adapter(config.engine)` — precedence single-sourced in `_resolve_engine`.

---

## Fix Round 2 — test contract + regression coverage

**Scope:** CR-01 test failure, missing WR-02/WR-05 regression tests
**Commits:** `39fd893`, `923c7ba`, `45bddc2`
**Suite before:** 342 passed, 1 failed (stale config-path assertion)

### CR-01: Stale `load_config` path assertion

**Files:** `tests/test_review_flow.py`
**Commit:** `39fd893`
**Fix:** Hermetic test — anchor `PREVUE_CONSUMER_ROOT` to `tmp_path`; assert resolved
absolute path passed to `load_config`.

### WR-01: Classify billing regression tests

**Files:** `tests/test_review_flow.py`
**Commit:** `923c7ba`
**Fix:** `test_run_review_classify_tokens_zero_on_full_degrade` and
`test_run_review_classify_tokens_nonzero_on_real_labels`.

### WR-02: Skip None guards regression tests

**Files:** `tests/test_skip.py`
**Commit:** `45bddc2`
**Fix:** `test_none_title_does_not_crash`, `test_bot_with_none_login_skips_as_unknown`.

**Suite after:** 347 passed.

---

## Fix Round 3 — partial-degrade billing path

**Scope:** WR-01 partial-degrade end-to-end coverage
**Commit:** `71d8394`

### WR-01: Partial-degrade fallback billing untested

**Files:** `tests/test_review_flow.py`
**Commit:** `71d8394`
**Fix:** Added `test_run_review_partial_degrade_bills_routes_and_retains_general` — asserts:
- `token_meta["classify"] > 0`
- real label routed via inversion
- `GENERAL_LABEL` retained as `FALLBACK_PARTIAL_GLOB` (pop does not fire)
- `classification_disclosure` forwarded to `upsert_sticky`

---

## Out of scope (Info backlog)

Not addressed in any fix round: IN-01 (dead branch), IN-02 (wrapper indirection),
IN-03 (magic numbers), IN-04 (`build_prompt` alias). Re-run with `fix_scope: all` to include.

---

_Fixed: 2026-06-14_
_Fixer: Claude (gsd-code-fixer)_
