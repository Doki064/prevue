---
phase: 07-customization-hardening
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - src/prevue/config.py
  - src/prevue/engines/tokens.py
  - src/prevue/gate.py
  - src/prevue/github/comments.py
  - src/prevue/pack.py
  - src/prevue/review.py
  - src/prevue/skills/loader.py
  - src/prevue/skip.py
  - tests/test_comments.py
  - tests/test_config.py
  - tests/test_gate.py
  - tests/test_injection_adversarial.py
  - tests/test_pack.py
  - tests/test_review_flow.py
  - tests/test_skip.py
  - tests/test_skills_merge.py
  - tests/test_tokens.py
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: clean
review_rounds: 3
---

# Phase 7: Code Review Report

**Reviewed:** 2026-06-15 (final pass)
**Depth:** standard
**Status:** clean — all critical/warning findings resolved; Info backlog only

## Summary

Three review rounds covered Phase 7 customization/hardening. All critical and warning
findings are fixed and regression-tested. `uv run pytest` => full suite green (348+ tests).

**Final state:** no open blockers or warnings. Four Info items remain as intentional backlog
(dead branch, wrapper indirection, magic numbers, unused alias).

## Review history

| Round | Date | Scope | Outcome |
|-------|------|-------|---------|
| 1 | 2026-06-14 | Initial review — config loader, packing, gate, sticky, skills, `run_review` | 1 critical (CR-01 symlink/containment), 6 warnings (WR-01..06), 4 info |
| 2 | 2026-06-14 | Re-review after Round 1 fixes (`65f7045..f4a329b`) | 1 critical (stale test asserting pre-CR-01 contract), 2 warnings (missing regression tests) |
| 3 | 2026-06-14 | Re-review after Round 2 fixes (`39fd893..45bddc2`) | 1 warning (partial-degrade billing path untested) |

All Round 1–3 findings were fixed. See `07-REVIEW-FIX.md` for commit-level detail.

## Resolved findings (archive)

### Round 1 — initial review

**CR-01:** `resolve_consumer_config_path` did not resolve symlinks; no-root relative branch
returned unresolved path with no containment check. **Fixed:** single resolved-path invariant
with anchoring root (`f2cf1a2`).

**WR-01:** Duplicated `..` guards between resolver and `load_config`. **Fixed:** containment
only in resolver (`65f7045`).

**WR-02:** Classify tokens billed on full degrade. **Fixed:** bill only when
`produced_real_labels` (`182d5e8`).

**WR-03:** Skill byte cap counted frontmatter, not loaded body. **Fixed:** measure
`post.content` (`3b8979f`).

**WR-04:** Skill cap drop order non-deterministic. **Fixed:** sorted `iterdir()` (`a1c7123`).

**WR-05:** `pr.title` / `login` None crashes. **Fixed:** defensive coercion (`3afe3da`).

**WR-06:** Redundant `PREVUE_ENGINE` re-read in `run_review`. **Fixed:** use `config.engine`
only (`f4a329b`).

### Round 2 — re-review after Round 1 fixes

**CR-01 (test):** `test_run_review_load_config_default_path` asserted stale relative path.
**Fixed:** hermetic test with resolved absolute path (`39fd893`).

**WR-01:** No regression test for classify billing on full degrade. **Fixed:** paired tests
zero vs non-zero classify tokens (`923c7ba`).

**WR-02:** No regression test for None title/login skip guards. **Fixed:** `test_skip.py`
cases (`45bddc2`).

### Round 3 — re-review after Round 2 fixes

**WR-01:** Partial-degrade fallback billing path untested end-to-end. **Fixed:**
`test_run_review_partial_degrade_bills_routes_and_retains_general` (`71d8394`).

## Info (backlog — not blocking)

### IN-01: Dead branch condition in `render_body` Skills line

**File:** `src/prevue/github/comments.py:149`
**Issue:** `elif classification is not None:` nested inside `if classification is not None:` —
always true when reached.
**Fix:** Replace with plain `else:`.

### IN-02: `_estimate_classify_tokens` wrapper adds indirection with no behavior

**File:** `src/prevue/review.py:58-59`
**Issue:** Forwards to imported `estimate_classify_tokens` with no added logic.
**Fix:** Call directly, or document as test patch seam.

### IN-03: Magic numbers for skill caps lack named constants

**File:** `src/prevue/config.py:54-56`
**Issue:** `65536`, `262144`, `50` inline; 64 KiB / 256 KiB intent not expressed.
**Fix:** Promote to module-level named constants.

### IN-04: `build_prompt = _build_prompt` alias is an unused public re-export

**File:** `src/prevue/engines/prompt.py:93`
**Issue:** Callers use `_build_prompt` directly; alias can drift.
**Fix:** Remove alias or migrate callers to public name.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
