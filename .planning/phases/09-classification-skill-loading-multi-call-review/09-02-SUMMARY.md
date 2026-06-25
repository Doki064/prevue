---
phase: 09-classification-skill-loading-multi-call-review
plan: "02"
subsystem: hybrid-skill-selection
tags: [selection, keyword-floor, gap-closure-guard, llm-escalation, TDD, SKIL-01, D-02]
dependency_graph:
  requires:
    - src/prevue/skills/loader.py (select_skills, Skill model, dedupe/sort pattern)
    - src/prevue/classify/llm_fallback.py (degrade-on-exception contract)
    - src/prevue/classify/models.py (canonical_index, CANONICAL_LABEL_ORDER)
    - src/prevue/engines/base.py (EngineAdapter.classify port)
    - tests/test_selection.py (RED scaffold from 09-01)
  provides:
    - src/prevue/skills/selection.py (keyword_score, select_skills_hybrid, KEYWORD_THRESHOLD, _dedup_sort)
    - src/prevue/classify/llm_fallback.py (llm_select_skills)
  affects:
    - src/prevue/skills/loader.py (select_skills now delegates to shared _dedup_sort)
    - tests/test_selection.py (fleshed out from RED scaffold to full suite)
    - tests/test_llm_fallback.py (TestLlmSelectSkills added)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN/REFACTOR cycle
    - Jaccard content signal + pathspec path signal (0.7/0.3 weighted keyword floor)
    - Gap-closure guard (below-threshold routed skill escalation — never silent drop)
    - Double-duty LLM reuse (llm_skill_names from classify fallback → selection)
    - Degrade-on-exception pattern (mirrors _classify_batch — empty set on any error)
    - Shared _dedup_sort helper (canonical_index(bundle), filename ordering)
key_files:
  created:
    - src/prevue/skills/selection.py
  modified:
    - src/prevue/classify/llm_fallback.py
    - src/prevue/skills/loader.py
    - tests/test_selection.py
    - tests/test_llm_fallback.py
decisions:
  - "KEYWORD_THRESHOLD=0.15 with Jaccard 0.7/path_signal 0.3 weighting — strong content overlap alone crosses threshold; weak content + path match also crosses"
  - "Gap-closure guard pass-through: no adapter + no llm_skill_names = conservatively include all routed below-threshold skills (prefer over-loading to silent drop)"
  - "_dedup_sort shared between select_skills and select_skills_hybrid — loader.py imports from selection.py"
  - "llm_select_skills reuses adapter.classify port with skill names as synthetic paths + relevant/irrelevant labels — avoids new adapter method, mirrors degrade contract"
  - "Lazy import of llm_select_skills inside select_skills_hybrid function body — avoids circular import at module level"
metrics:
  duration: "6 min"
  completed: "2026-06-21T17:04:00Z"
  tasks: 3
  files: 5
---

# Phase 09 Plan 02: Hybrid Skill Selection (D-02 SKIL-01) Summary

Deterministic keyword floor with LLM escalation gap-closure guard closes the SKIL-01 regression: a routed bundle's relevant-but-low-keyword-score skill is never silently dropped — it escalates to the LLM (or passes through conservatively) instead.

## What Was Built

### Task 1 (RED): Flesh Out Test Scaffolds

Extended the existing RED scaffolds from Plan 09-01 with full behavior coverage:

**tests/test_selection.py** (14 tests across 2 classes):
- `TestKeywordScore`: 5 tests covering high-overlap above-threshold, zero-overlap below-threshold, non-negative guarantee, applies-to path contribution, zero adapter calls assertion
- `TestSelectSkillsHybrid`: 9 tests covering keyword floor selection, gap-closure guard (no adapter), gap-demo-sandbox shape via llm_skill_names, non-routed drop, empty bundles keyword-only, canonical sort order, deduplication, empty skills, return type

**tests/test_llm_fallback.py** — added `TestLlmSelectSkills` (5 tests):
- Returns set of strings, prompt excludes skill body (T-09-05), degrade on NotImplementedError, degrade on EngineFailure, empty skills returns empty set

All 14+5=19 new test functions were failing with ImportError (RED gate passed).

Commit: `0ddbd09`

### Task 2 (GREEN): Implement Hybrid Selection Module

**src/prevue/skills/selection.py** — new module:
- `KEYWORD_THRESHOLD = 0.15` — deterministic, zero-token threshold
- `_tokenize(text)` — lower-case word tokens (len>=2), regex-based, frozenset
- `keyword_score(skill, paths, diff_text) -> float` — Jaccard content signal (skill name+description tokens vs diff tokens) weighted 0.7, plus pathspec applies-to path signal weighted 0.3; returns float in [0, 1]; zero adapter calls
- `_dedup_sort(skills) -> list[Skill]` — deduplicates by bundle/filename key, sorts by (canonical_index(bundle), filename); shared ordering helper
- `select_skills_hybrid(skills, paths, diff_text, bundles, *, adapter, llm_skill_names, model)` — keyword floor pass, then gap-closure guard for below-threshold routed skills; resolves via llm_skill_names (double-duty) → adapter call → conservative pass-through; dedupes and sorts

**src/prevue/classify/llm_fallback.py** — extended with `llm_select_skills`:
- `_RELEVANT_LABEL = "relevant"`, `_IRRELEVANT_LABEL = "irrelevant"` constants
- `llm_select_skills(candidate_skills, adapter, *, model) -> set[str]` — passes skill names as synthetic "paths" to adapter.classify with relevant/irrelevant label set; filters to "relevant" names; degrades to empty set on NotImplementedError/AuthError/EngineFailure/TimeoutExpired/JSONDecodeError/ValueError

All 24 tests green. Ruff clean.

Commit: `4ed7691`

### Task 3 (REFACTOR): Shared Dedup/Sort Ordering

- `loader.py select_skills` now delegates final dedup+sort to `_dedup_sort` from `selection.py`
- Removed now-unused `canonical_index` import from `loader.py`
- Single canonical ordering helper — `select_skills` and `select_skills_hybrid` cannot diverge

Full suite: 30 failed (exactly the sibling RED scaffolds test_importscan.py + test_multicall.py), 659 passed. No regressions.

Commit: `969bc60`

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `tests/test_selection.py` passes (was RED in 09-01) | PASS (14 tests green) |
| Gap-closure guard test PASSES | PASS (`test_below_threshold_routed_skill_escalates_not_drops`) |
| Drop-non-routed test PASSES | PASS (`test_below_threshold_non_routed_skill_dropped`) |
| `keyword_score` makes zero adapter calls (spy test) | PASS (`test_makes_zero_adapter_calls`) |
| `llm_select_skills` prompt excludes skill body | PASS (`test_prompt_excludes_skill_body`) |
| select_skills_hybrid output ordering = select_skills ordering | PASS (`test_output_sorted_by_canonical_index_then_filename` + shared helper) |
| Full suite green except sibling RED scaffolds | PASS (30 fail = importscan + multicall RED only) |

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit) | `0ddbd09` | PASS |
| GREEN (feat commit) | `4ed7691` | PASS |
| REFACTOR (refactor commit) | `969bc60` | PASS |

## Deviations from Plan

**1. [Rule 2 - Missing Validation] Conservative pass-through escalation when no adapter and no llm_skill_names**
- **Found during:** Task 2 GREEN — the plan said "separate name+desc-only escalation call when an adapter is available, else keyword-floor-only" but with no adapter the correct behavior is ambiguous for the gap-closure guarantee
- **Issue:** Keyword-floor-only without an adapter would silently drop a routed security skill if it scored below threshold — violating the "never drop silently" contract from the plan's truths
- **Fix:** When `adapter=None` and `llm_skill_names=None`, conservatively include all below-threshold routed skills (pass-through). This is the correct escalation degrade: prefer over-loading to silent drop of security skills.
- **Files modified:** `src/prevue/skills/selection.py`
- **Commit:** `4ed7691`

**2. [Rule 2 - Architecture] _build_skill_select_prompt removed as unused**
- **Found during:** Task 2 GREEN — initial implementation wrote a `_build_skill_select_prompt` helper but the actual `llm_select_skills` reuses the `adapter.classify()` port (passing skill names as synthetic paths), making the separate prompt builder redundant
- **Fix:** Removed the unused helper, keeping the implementation simpler and avoiding the `INSTRUCTION_REASSERTION` import dependency
- **Files modified:** `src/prevue/classify/llm_fallback.py`
- **Commit:** `4ed7691`

## Known Stubs

None — all selection logic is fully implemented. No placeholder data or hardcoded empty values in selection paths.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-09-05 | src/prevue/classify/llm_fallback.py | `llm_select_skills` sends only name+description to adapter; test asserts body sentinel absent from prompt |
| mitigated: T-09-06 | src/prevue/skills/selection.py | Gap-closure guard: below-threshold routed skills escalate (never drop); `test_below_threshold_routed_skill_escalates_not_drops` enforces this |

## Self-Check

- [x] `src/prevue/skills/selection.py` exists and exports `keyword_score`, `select_skills_hybrid`, `KEYWORD_THRESHOLD` — FOUND
- [x] `src/prevue/classify/llm_fallback.py` exports `llm_select_skills` — FOUND
- [x] `src/prevue/skills/loader.py` imports `_dedup_sort` from selection — FOUND
- [x] RED commit `0ddbd09` — FOUND
- [x] GREEN commit `4ed7691` — FOUND
- [x] REFACTOR commit `969bc60` — FOUND
- [x] 24 tests pass in test_selection.py + test_llm_fallback.py — VERIFIED
- [x] Ruff clean on all modified files — VERIFIED

## Self-Check: PASSED
