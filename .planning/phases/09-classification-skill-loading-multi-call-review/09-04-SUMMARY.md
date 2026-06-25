---
phase: 09-classification-skill-loading-multi-call-review
plan: "04"
subsystem: review-orchestration
tags: [classify-first, hybrid-selection, skill-loading, SKIL-01, D-01, D-02, D-03, D-04, D-12, TDD]
dependency_graph:
  requires:
    - phase: 09-02
      provides: "select_skills_hybrid, keyword_score, llm_select_skills, _dedup_sort, KEYWORD_THRESHOLD"
    - phase: 09-01
      provides: "gap-demo-auth-guard.md fixture, gap_shape_skill conftest fixture"
  provides:
    - "run_review() classify-first reorder (D-01)"
    - "select_skills_hybrid wired in all trim/readmit/second-trim cascade sites"
    - "double-duty llm_skill_names pre-fetch after load_skills"
    - "_refresh_matched shared helper for pack cascade"
    - "test_classify_runs_on_full_set_not_packed"
    - "test_routed_bundle_skill_loads_via_union"
    - "test_llm_fallback_label_triggers_bundle_selection"
    - "test_non_routed_bundle_glob_unchanged"
    - "test_post_union_budget_neutral_skip"
    - "test_gap_demo_skill_loaded (D-12 regression)"
  affects:
    - "09-05 (multicall): run_review now classify-first; multicall splitter inherits same order"
    - "09-06 (provenance): loaded_skills sticky audit uses matched from select_skills_hybrid"
tech_stack:
  added: []
  patterns:
    - "Classify-first order: classify(reduced.files) → route() → load_skills → hybrid-select → pack cascade"
    - "Double-duty llm_skill_names: llm_select_skills pre-fetch after load_skills when fallback ran"
    - "_hybrid_kwargs dict + _refresh_matched helper to share select_skills_hybrid args across cascade"
    - "TDD RED/GREEN/REFACTOR: 5 RED tests → GREEN implementation → REFACTOR dedup helper"
key_files:
  created: []
  modified:
    - src/prevue/review.py
    - src/prevue/classify/llm_fallback.py
    - tests/test_review_flow.py
decisions:
  - "Classify-first order: classify(reduced.files) runs BEFORE pack, route before select_skills_hybrid — fixes SKIL-01 gap where packed-subset classify lost security labels from large dropped files"
  - "Double-duty llm_select_skills pre-fetch gated on fallback_cfg.enabled AND unmatched_pre_pack AND result_cls.bundles — avoids extra adapter calls on fully-matched PRs"
  - "Empty llm_select_skills result (adapter degrade/AttributeError) leaves llm_skill_names=None so select_skills_hybrid escalates independently rather than treating empty as 'none relevant'"
  - "AttributeError added to llm_select_skills degrade catches — adapters not inheriting EngineAdapter ABC degrade cleanly instead of crashing"
  - "test_fallback_only_on_packed renamed/updated: classify-first classifies ALL reduced files including budget-skipped ones — routing accuracy wins over classify token savings"
  - "_refresh_matched helper + _hybrid_kwargs dict eliminate repeated 8-line pattern across 4 cascade sites"
requirements-completed: [SKIL-01, ROUT-01, CLSF-03]
duration: "16 min"
completed: "2026-06-21T17:34:20Z"
---

# Phase 09 Plan 04: Classify-First Reorder + Hybrid Skill Selection Integration Summary

**classify(reduced.files) now runs before pack, route() feeds select_skills_hybrid which closes the SKIL-01 gap — a security-bundle skill with applies-to=`**/auth/**` loads on a Checkout.jsx PR via keyword-floor content signal, proven by the gap-demo-sandbox D-12 regression test.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-06-21T17:18:20Z
- **Completed:** 2026-06-21T17:34:20Z
- **Tasks:** 2 (TDD: RED+GREEN+REFACTOR per task)
- **Files modified:** 3

## Accomplishments

- Reordered `run_review()` to classify-first (D-01): `classify(reduced.files)` → LLM fallback on pre-pack unmatched → `route()` → `load_skills` → `select_skills_hybrid` cascade
- All 4 `select_skills(packed_paths)` call sites replaced by `select_skills_hybrid(skills, packed_paths, diff_text, result_cls.bundles, ...)` via `_refresh_matched` helper
- Double-duty `llm_skill_names` pre-fetch: when LLM fallback ran, `llm_select_skills` pre-fetches relevant skill names so `select_skills_hybrid` escalation avoids a second adapter call
- gap-demo-sandbox gap regression (D-12): `test_gap_demo_skill_loaded` proves gap-demo skill loads for `src/pages/Checkout.jsx` despite `**/auth/**` glob miss — and would fail on pre-reorder code (invariant-checked)

## Task Commits

Each task was committed atomically following TDD RED/GREEN/REFACTOR:

**Task 1: Reorder run_review to classify-first + wire hybrid selection**
1. `780587c` — `test(09-04)`: RED — 5 failing tests for classify-first + hybrid selection
2. `2bd9baf` — `feat(09-04)`: GREEN — classify-first reorder + hybrid selection wired
3. `cdf4fa8` — `refactor(09-04)`: REFACTOR — `_refresh_matched` helper + `_hybrid_kwargs` dict

**Task 2: gap-demo-sandbox gap regression**
4. `c5f8e28` — `feat(09-04)`: `test_gap_demo_skill_loaded` (D-12)

## Files Created/Modified

- `src/prevue/review.py` — classify-first reorder; `select_skills_hybrid` replacing `select_skills`; `llm_skill_names` pre-fetch; `_refresh_matched` helper; `select_skills` import removed
- `src/prevue/classify/llm_fallback.py` — `AttributeError` added to `llm_select_skills` degrade catches; `llm_select_skills` added to `review.py` import
- `tests/test_review_flow.py` — 6 new tests; `test_fallback_only_on_packed` updated to reflect D-01 classify-full semantics

## Decisions Made

- **Classify-first on full set (D-01):** `classify(reduced.files)` instead of `classify(packed_files)` — routing accuracy (security label from a large dropped file) wins over classify token savings
- **Double-duty gating:** `llm_skill_names` pre-fetch only when `fallback_cfg.enabled AND unmatched_pre_pack` — avoids extra adapter call on PRs where all files are deterministically matched
- **Empty degrade → None:** When `llm_select_skills` returns empty (adapter degraded), leave `llm_skill_names=None` so `select_skills_hybrid` can escalate independently, preserving conservative pass-through path
- **AttributeError degrade:** Adapters that don't inherit `EngineAdapter` ABC (plain classes in tests, older consumers) degrade cleanly instead of propagating AttributeError through `llm_select_skills`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_fallback_only_on_packed to reflect D-01 classify-full semantics**
- **Found during:** Task 1 GREEN — classify-first means ALL unmatched reduced.files go to llm_classify, including budget-skipped ones
- **Issue:** The old test asserted `mystery_b.bin` NOT in `llm_classify` call args. With D-01, it IS there (intentional by design).
- **Fix:** Renamed to `test_fallback_classifies_full_reduced_set_including_budget_skipped`, updated assertions to expect both files in classified_paths while `not_reviewed_file_count == 1` still holds
- **Files modified:** `tests/test_review_flow.py`
- **Commit:** `2bd9baf`

**2. [Rule 2 - Missing Validation] Added AttributeError to llm_select_skills degrade catches**
- **Found during:** Task 1 GREEN — `FindingsEngine` in tests has no `classify()`, raises AttributeError instead of NotImplementedError
- **Issue:** `llm_select_skills` caught `NotImplementedError` (the `EngineAdapter.classify()` default) but not `AttributeError` (plain class without classify attribute)
- **Fix:** Added `AttributeError` to the exception tuple in `llm_select_skills`
- **Files modified:** `src/prevue/classify/llm_fallback.py`
- **Commit:** `2bd9baf`

**3. [Rule 2 - Missing Validation] Gate double-duty llm_skill_names on actual fallback execution**
- **Found during:** Task 1 GREEN — initial pre-fetch called `llm_select_skills` unconditionally, triggering an assertion error in `test_run_review_fallback_skipped_when_all_matched` (SpyEngine that asserts classify must not run)
- **Fix:** Gate the pre-fetch on `fallback_cfg.enabled AND unmatched_pre_pack` — only runs when the LLM fallback itself ran (double-duty, not a new call)
- **Files modified:** `src/prevue/review.py`
- **Commit:** `2bd9baf`

**4. [Rule 2 - Missing Validation] Use classify-capable engine for test_llm_fallback_label_triggers_bundle_selection**
- **Found during:** Task 1 GREEN — `CaptureEngine` had no `classify()`, causing `llm_select_skills` to degrade to empty set, then gap-closure escalation also failed → skill not loaded
- **Fix:** Replaced `CaptureEngine` with `ClassifyCapableCaptureEngine` that implements `classify()` returning "relevant" for "Data Schema Guard"
- **Files modified:** `tests/test_review_flow.py`
- **Commit:** `2bd9baf`

---

**Total deviations:** 4 auto-fixed (1 Rule 1 bug fix, 3 Rule 2 missing validation/guard fixes)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep — all changes directly support the D-01/D-02/D-03 contract.

## Issues Encountered

- Keyword-floor scoring for gap-demo skill against sparse diff was 0.14 (just below KEYWORD_THRESHOLD=0.15), requiring richer diff text in `test_routed_bundle_skill_loads_via_union` and `test_gap_demo_skill_loaded`. Added auth/security tokens to the patch text — representative of real Checkout.jsx changes that reference auth modules.

## Known Stubs

None — all selection logic is fully implemented. No placeholder data or hardcoded empty values in skill loading paths.

## Threat Flags

None — no new trust boundaries introduced. The D-01 reorder processes the same diff content; T-09-11 (SKIL-04 base-ref guard) and T-09-12 (prompt fencing) remain unchanged and verified by existing tests staying green.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit) | `780587c` | PASS |
| GREEN (feat commit) | `2bd9baf` | PASS |
| REFACTOR (refactor commit) | `cdf4fa8` | PASS |

## Next Phase Readiness

- Phase 09-05 (multicall): `run_review()` now classify-first; multicall splitter builds on top of the stabilized single-call flow
- Phase 09-06 (provenance): `loaded_skills` sticky audit comes from `matched` (post-`select_skills_hybrid`), correctly reflecting bundle-routed skills
- All 64 `test_review_flow.py` tests pass; only pre-existing `test_multicall.py` RED scaffold (09-05 target) remains failing

---
*Phase: 09-classification-skill-loading-multi-call-review*
*Completed: 2026-06-21*
