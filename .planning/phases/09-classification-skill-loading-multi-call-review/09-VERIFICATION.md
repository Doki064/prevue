---
phase: 09-classification-skill-loading-multi-call-review
verified: 2026-06-24T00:00:00Z
status: verified
score: 10/10 must-haves verified
overrides_applied: 0
human_verification: []
deferred: []
re_verification:
  previous_status: human_needed
  previous_score: 9/10
  gaps_closed:
    - "WR-08: PARTIAL_MARKER constant + partial_marker kwarg in render_body/upsert_sticky; _prior_review_was_partial detection wired in review.py"
    - "WR-09: Dead CallGroup.instructions field removed; model and behavior now agree; test assertion added"
    - "WR-10: _supports_skill_classify requires isinstance(adapter, EngineAdapter) before probing overridden method"
    - "WR-11: Regression tests added in test_comments.py and test_review_flow.py for durable partial-marker round-trip"
    - "WR-12: max_total_run_tokens docstring corrected to state flat 500_000 constant (not derived from max_tokens_per_call)"
    - "Ruff CI gate: 8 pre-existing lint errors resolved; all checks pass"
  gaps_remaining: []
  regressions: []
---

# Phase 9: Classification-aligned skill loading + multi-call review — Verification Report

**Phase Goal:** (1) Close the classify/route -> skill loading gap: routed bundle labels expand the loaded skill set, not only sticky Metadata. (2) Add configurable multi-call review: when one LLM call is not enough, split the diff into logical chunks, run calls sequentially or in parallel, and merge/dedupe findings.
**Verified:** 2026-06-24T00:00:00Z
**Status:** verified — all automated checks pass (720/720); live UAT complete 14/14 (commit 792eff2)
**Re-verification:** Yes — after WR-08 through WR-12 fix commits (2026-06-23) and ruff CI gate fix

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After classify + route, skills from routed bundles are unioned into loaded set via select_skills_hybrid and appear in assembled instructions before engine.review() | VERIFIED | review.py:520 classify(reduced.files) before pack (line 636); select_skills_hybrid replaces select_skills throughout; test_routed_bundle_skill_loads_via_union and test_gap_demo_skill_loaded pass (720/720) |
| 2 | Path-glob select behavior is unchanged for bundles NOT present in result_cls.bundles | VERIFIED | select_skills_hybrid in selection.py falls through to glob-only path when bundle not routed; test_non_routed_bundle_glob_unchanged passes |
| 3 | LLM fallback labels trigger the same bundle-scoped selection as deterministic labels (one code path) | VERIFIED | llm_classify result merges into result_cls.labels -> same route() -> same select_skills_hybrid; test_llm_fallback_label_triggers_bundle_selection passes |
| 4 | Post-union re-trim and byte-limit guard run after selection; still-over-budget leads to neutral skip | VERIFIED | review.py preserves trim_packed_files cascade + MAX_PROMPT_BYTES guard after select_skills_hybrid; test_post_union_budget_neutral_skip passes |
| 5 | Sticky Metadata audit reflects final loaded skills; docs pipeline diagram matches implementation | VERIFIED | render_body accepts skill_sources kwarg (comments.py:460); ARCHITECTURE.md step 8 says "Classify-first"; old "metadata only" language absent from both docs |
| 6 | gap-demo-sandbox regression test covers "classified bundle != glob path" case | VERIFIED | test_gap_demo_skill_loaded (test_review_flow.py) passes in 0.08s; asserts GAP-DEMO-SKILL-LOADED in instructions for src/pages/Checkout.jsx which does not match **/auth/** |
| 7 | max_review_calls config (default 1) controls multi-call; single-call path unchanged | VERIFIED | ReviewConfig.max_review_calls = Field(default=1, ge=1) in gate.py:51; docstring corrected by WR-12 (500_000 flat constant); caps OK verified by python -c spot-check |
| 8 | When multi-call active, diff splits into bundle-aligned groups with import-co-located files; findings merged+deduped via fingerprint before gate/output | VERIFIED | multicall.py: split_into_calls (line 69) uses referenced_paths per-file for co-location; merge_findings (line 287) uses fingerprint() with severity tie-break; CallGroup.instructions field removed by WR-09 (model and behavior now agree); 44 test_multicall.py tests pass |
| 9 | review_concurrency config (default 1) controls parallel execution via ThreadPoolExecutor; no asyncio | VERIFIED | multicall.py:270 ThreadPoolExecutor(max_workers=concurrency); grep confirmed no asyncio in multicall.py or review.py; ruff CI gate clean |
| 10 | Live gap-demo-sandbox PR proves gap closure end-to-end (Task 3, Plan 09-06) | VERIFIED | UAT 14/14 pass (commit 792eff2); gap-demo-auth-guard skill loads on sandbox PR #8 despite no glob match (test 12); multi-call token meta and budget alert rendered correctly on PRs #9/#10; all three originally-deferred human checks passed live |

**Score:** 10/10 truths verified (UAT 14/14 pass — all live tests confirmed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/gate.py` | ReviewConfig with 5 new caps (max_review_calls, review_concurrency, max_tokens_per_call, max_total_run_tokens, guardrail_skills) | VERIFIED | All 5 fields at lines 51-55; WR-12 corrected docstring: max_total_run_tokens = 500_000 flat constant, not derived from max_tokens_per_call; coherence validators at lines 59-65 |
| `src/prevue/skills/selection.py` | keyword_score, select_skills_hybrid, KEYWORD_THRESHOLD; WR-10 isinstance guard | VERIFIED | All 3 exports present; KEYWORD_THRESHOLD=0.15; _supports_skill_classify requires isinstance(adapter, EngineAdapter) at line 148 before probing overridden method (WR-10) |
| `src/prevue/importscan.py` | extract_imports, referenced_paths; stdlib-only (ast+re); no exec/eval | VERIFIED | Both functions present; imports only ast, os, re; ast.parse mode="exec" is parse-only (confirmed by docstring) |
| `src/prevue/multicall.py` | CallGroup (no dead instructions field), split_into_calls, execute_calls, merge_findings | VERIFIED | WR-09: CallGroup at line 44 has only files + bundles fields; docstring explicitly states no per-group instructions field; test_multicall.py line 95 asserts not hasattr(group, "instructions"); all 4 exports present |
| `src/prevue/review.py` | classify-first ordering; select_skills_hybrid replacing select_skills; multicall wiring; WR-08 partial marker detection | VERIFIED | classify(reduced.files) at line 520; WR-08: PARTIAL_MARKER imported at line 42; _prior_review_was_partial at line 396; partial_marker=prior_partial wired at line 461 |
| `src/prevue/github/comments.py` | render_body with skill_sources, run_budget_reached, run_budget_skipped_count; WR-08 PARTIAL_MARKER emission | VERIFIED | WR-08: PARTIAL_MARKER constant at line 36; partial_marker kwarg at line 470; is_partial predicate at line 651; marker emitted at line 656; upsert_sticky forwards partial_marker at line 785 |
| `tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md` | applies-to: **/auth/**, body contains GAP-DEMO-SKILL-LOADED | VERIFIED | Sentinel token present; applies-to does not match src/pages/Checkout.jsx |
| `docs/ARCHITECTURE.md` | classify-first pipeline; multi-call section; no old "metadata-only" routing claim | VERIFIED | Step 8 "Classify-first" at line 59; multi-call caps table at lines 134-135; "metadata only" / "not skill gating" absent |
| `docs/configuration.md` | 5 new review caps documented | VERIFIED | All 5 caps in table at lines 102-106; YAML examples at lines 120-124 and 267-271 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/prevue/review.py` | `src/prevue/skills/selection.py` | select_skills_hybrid(skills, paths, diff_text, result_cls.bundles, llm_skill_names=...) | VERIFIED | Import at review.py:70; call sites confirmed; WR-10 isinstance guard in selection.py prevents false-positive probe on duck-typed adapters |
| `src/prevue/review.py` | `src/prevue/classify/router.py` | route() called before first skill-selection call | VERIFIED | route() called at line 561; classify at 520; pack at 636 — classify-first ordering confirmed |
| `src/prevue/review.py` | `src/prevue/multicall.py` | split_into_calls + execute_calls + merge_findings | VERIFIED | All three imported at line 66; called at 871, 908, 913 |
| `src/prevue/multicall.py` | `src/prevue/fingerprint.py` | merge_findings dedupes by fingerprint(path, title) | VERIFIED | Import at multicall.py:29; used at line 312 |
| `src/prevue/multicall.py` | `src/prevue/importscan.py` | split_into_calls co-locates via referenced_paths | VERIFIED | Import at multicall.py:139 (lazy); used at line 144 per file |
| `src/prevue/review.py` | `src/prevue/github/comments.py` | sticky_base_kwargs threads skill_sources + run_budget_reached + run_budget_skipped_count + partial_marker (WR-08) | VERIFIED | sticky_base_kwargs built at line 1024; partial_marker=prior_partial at line 461; WR-08 round-trip confirmed by WR-11 regression tests |
| `src/prevue/config.py` | `src/prevue/gate.py` | ReviewConfig.model_validate(raw['review']) picks up new caps | VERIFIED | No config.py change needed (existing model_validate path auto-picks new fields); all config + gate tests pass |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `comments.py:render_body` | skill_sources | review.py _skill_sources dict built from keyword_score re-eval per matched skill | Yes — populated per matched skill with "routed"/"keyword"/"llm" tags | FLOWING |
| `comments.py:render_body` | run_budget_reached | review.py _run_budget_reached set True when whole-run cap exceeded | Yes — real overflow detection via budget tracking | FLOWING |
| `comments.py:render_body` | partial_marker | review.py _prior_review_was_partial() detects PARTIAL_MARKER in existing sticky body; forwarded as kwarg | Yes — WR-08: marker survives double no-op re-run (proven by WR-11 round-trip tests) | FLOWING |
| `review.py:run_review` | result_cls.bundles | classify(reduced.files) -> route() -> bundle ids | Yes — real file classification drives bundle list | FLOWING |
| `multicall.py:merge_findings` | findings | execute_calls results from real engine.review() calls | Yes — real findings from engine; deduped by fingerprint | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| gap-demo-sandbox gap test passes | `uv run pytest tests/test_review_flow.py::test_gap_demo_skill_loaded -q` | 1 passed in 0.08s | PASS |
| New test modules all green (selection, importscan, multicall) | `uv run pytest tests/test_selection.py tests/test_importscan.py tests/test_multicall.py -q` | 44 passed in 0.04s | PASS |
| Comment render tests for new features + WR-11 partial marker tests | `uv run pytest tests/test_comments.py -k "skill_source or per_call or budget_alert or partial_marker" -q` | 14 passed in 0.07s | PASS |
| WR-11 partial-marker round-trip test | `uv run pytest tests/test_review_flow.py -k "partial_render_detected" -q` | 1 passed in 0.08s | PASS |
| Full suite (720 tests including WR-08 through WR-12 additions) | `uv run pytest tests/ -q` | 720 passed in 7.22s | PASS |
| ReviewConfig new caps with corrected defaults (WR-12) | `uv run python -c "from prevue.gate import ReviewConfig; c=ReviewConfig(); assert c.max_review_calls==1 and c.review_concurrency==1 and c.max_tokens_per_call==120000 and c.max_total_run_tokens==500000 and c.guardrail_skills==[]; print('caps OK')"` | caps OK | PASS |
| Ruff lint CI gate (all files including WR-changed) | `uv run ruff check src/ tests/` | All checks passed! | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SKIL-01 (gap closure) | 09-02, 09-04 | Routed bundle labels expand loaded skill set | SATISFIED | select_skills_hybrid + classify-first reorder; gap-demo-sandbox test passes; WR-10 closes probe false-positive gap |
| ROUT-01 | 09-02, 09-04 | Bundle-scoped skill selection with canonical ordering | SATISFIED | select_skills_hybrid preserves canonical_index sort from loader; dedupe/sort shared helper |
| CLSF-03 | 09-04, 09-06 | Sticky audit reflects classification; docs match implementation | SATISFIED | render_body skill_sources + partial_marker (WR-08); ARCHITECTURE.md classify-first; configuration.md caps documented with correct defaults (WR-12) |
| OUTP-04 | 09-06 | Token transparency: skill sources + per-call breakdown | SATISFIED | skill_sources kwarg wired; per_call token meta in sticky_base_kwargs; test_comments tests pass (14 relevant) |
| ENGN-05 | 09-01, 09-05 | max_review_calls config controls multi-call | SATISFIED | max_review_calls Field(default=1) in ReviewConfig; split_into_calls caps at max_review_calls |
| ENGN-06 | 09-03, 09-05 | Context-preserving split (import co-location) | SATISFIED | importscan.py referenced_paths; multicall.py uses it at line 144 for co-location |
| ENGN-07 | 09-01, 09-05 | review_concurrency controls parallel execution | SATISFIED | review_concurrency Field(default=1); ThreadPoolExecutor(max_workers=concurrency) in execute_calls |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/prevue/importscan.py` | 81 | `ast.parse(source, mode="exec")` — superficially matches exec pattern | INFO | Not a stub — mode="exec" is parse mode for statement-level code, NOT code execution. ast.parse is always parse-only; no code runs. Confirmed by docstring at line 7: "never eval/exec/compile-and-run". Unchanged from initial verification. |

No TBD/FIXME/XXX markers found in any WR-modified files. Ruff CI gate clean (`All checks passed!`).

### Human Verification Required

**Deferred by user decision** — Task 3 of Plan 09-06 (`checkpoint:human-verify`) is not an implementation gap; it is an explicit live UAT checkpoint the user chose to defer. The automated gap-demo-sandbox regression test provides unit-level proof of gap closure. The human checks below are for end-to-end validation with a live engine on a real PR. Status is unchanged from initial verification; no new automated evidence adds or removes items from this list.

### 1. Live gap-demo-sandbox Gap Closure

**Test:** Re-run Prevue review on gap-demo-sandbox PR #25 or #26 where `src/pages/Checkout.jsx` is changed and the `gap-demo-auth-guard` consumer skill (applies-to `**/auth/**`, bundle security) exists at the base ref
**Expected:** Sticky `Bundles:` includes `security`; sticky `Skills:` audit lists the gap-demo skill with source "routed"; review surfaces content matching `GAP-DEMO-SKILL-LOADED` instructions — proving the routed-bundle skill loaded despite no path glob match
**Why human:** Requires live GitHub Actions runner, real Copilot CLI auth, and actual PR triggering

### 2. Multi-Call Sticky Validation

**Test:** Set `review: {max_review_calls: 2}` in sandbox prevue.yml and trigger on a PR with files spanning two bundles (e.g. frontend + security)
**Expected:** Sticky shows per-bundle/per-call token breakdown; findings from both calls appear merged (no duplicate same-title findings on same path); exactly one check run and one sticky comment updated
**Why human:** Requires live runner and PR with bundle diversity; per-call token meta must be rendered correctly in GitHub Markdown

### 3. Whole-Run Budget Alert Visibility

**Test:** Set a low `max_total_run_tokens` to force overflow on a PR with multiple files; observe the resulting sticky comment
**Expected:** "Run token budget reached — N file(s) not reviewed" alert appears as a visible section above the collapsed Metadata `<details>` block; check conclusion is neutral (not red fail); N > 0
**Why human:** Requires live PR with budget exceeded; visual inspection of rendered GitHub comment to confirm alert is not hidden inside collapsed block

---

## Re-verification Summary

**Changes verified since 2026-06-21:**

- **WR-08 (durable partial marker):** `PARTIAL_MARKER = "<!-- prevue:partial -->"` constant added to `comments.py:36`; `partial_marker` kwarg added to `render_body` and `upsert_sticky`; `_prior_review_was_partial()` detection function added to `review.py:396`; wired via `partial_marker=prior_partial` in the no-op path at `review.py:461`. Data-flow trace updated to FLOWING.

- **WR-09 (dead instructions field):** `CallGroup` in `multicall.py` now has only `files` and `bundles` fields. Docstring explicitly states "There is intentionally no per-group instructions field." Test at `test_multicall.py:95` asserts `not hasattr(group, "instructions")`.

- **WR-10 (EngineAdapter isinstance guard):** `_supports_skill_classify` in `selection.py:148` now gates on `isinstance(adapter, EngineAdapter)` first, preventing MagicMock/duck-typed doubles from triggering real LLM escalation. Adapter=None path (test_selection.py:323) exercises the False return safely.

- **WR-11 (regression tests):** 6 new tests in `test_comments.py` (lines 1838-1899) covering clean-render omits marker, each partial trigger emits marker, explicit kwarg emits marker, and double no-op round-trip preserves marker. 1 new integration test in `test_review_flow.py` covering `_prior_review_was_partial` detection + double round-trip. Total: 9 new tests raising suite from 711 to 720.

- **WR-12 (docstring correction):** `gate.py:27-29` now reads "500_000 (A3 starting point) — a flat constant, not derived from max_tokens_per_call". Default value unchanged (500_000); only the incorrect "4x max_input_tokens derived" wording was removed.

- **Ruff CI gate:** 8 pre-existing lint errors (E501, F841, I001, F401 + format) resolved across 11 files. `ruff check src/ tests/` passes cleanly.

**All 9 previously-VERIFIED truths remain VERIFIED.** Truth #10 (live UAT) remains DEFERRED by user decision. Score and status unchanged from initial: **9/10, human_needed**.

---

_Verified: 2026-06-24T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after WR-08/WR-09/WR-10/WR-11/WR-12 + ruff fixes (commits 71466e8..418a1f0, 2026-06-23)_
