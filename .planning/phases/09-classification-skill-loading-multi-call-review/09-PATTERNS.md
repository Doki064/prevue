# Phase 9: Classification-aligned Skill Loading — Pattern Map

**Mapped:** 2026-06-17
**Files analyzed:** 6 (loader, review orchestration, comments render, existing tests, docs)
**Analogs found:** 6 / 6 — pure extension of Phase 3/7 patterns; no greenfield subsystems

> Phase 9 is a surgical seam insert: one new loader helper + ~30 lines in `run_review()` after `route()`. Copy dedupe/sort from `select_skills`, re-trim from the existing pre-classify loop, second byte guard mirrors the first.

## File Classification

| File | Role | Closest Analog | Match Quality |
|------|------|--------------|---------------|
| `src/prevue/skills/loader.py` (MOD) | service | `select_skills()` dedupe/sort (`loader.py:145-162`) | exact — extend |
| `src/prevue/review.py` (MOD) | orchestrator | pre-classify trim/readmit block (`review.py:546-601`) | exact — mirror after route |
| `src/prevue/github/comments.py` (MOD) | view | Metadata `Bundles:` line (`comments.py:489-491`) | exact — add disclosure |
| `tests/test_skills_loader.py` (MOD) | unit | existing `select_skills` tests | exact |
| `tests/test_review_flow.py` (MOD) | integration | `test_run_review_filtered_diff_and_classification_metadata` | exact |
| `docs/ARCHITECTURE.md` (MOD) | doc | pipeline step 10-11 (`ARCHITECTURE.md:60-61`) | exact |

## Pattern Assignments

### `union_routed_skills()` — new helper in `loader.py`

**Analog:** `select_skills()` dedupe + sort (`loader.py:147-162`).

**Contract (D-01/D-02/D-03):**
```python
def union_routed_skills(
    glob_matched: list[Skill],
    all_skills: list[Skill],
    routed_bundles: list[str] | set[str],
) -> list[Skill]:
    """Union glob-selected skills with all skills from routed bundles (D-02).

    Non-routed bundles contribute only via glob_matched (D-03).
    Dedupe by bundle/filename; sort by (canonical_index(bundle), filename).
    """
```

**Dedupe key:** `f"{skill.bundle}/{skill.filename}"` — same as `select_skills` (`loader.py:156-159`).

**Sort key:** `(canonical_index(s.bundle), s.filename)` — same as `select_skills` (`loader.py:161`).

**Bundle expansion:** `[s for s in all_skills if s.bundle in routed_bundles]` appended to glob_matched before dedupe.

**Empty routed_bundles:** return `glob_matched` unchanged (no-op).

---

### `run_review()` post-route insert — `review.py`

**Analog:** pre-classify trim loop (`review.py:546-601`).

**Insert point:** immediately after `result_cls.bundles = route(...)` (~713), **before** `ReviewRequest` / `engine.review()` (~722).

**Sequence (D-01/D-06/D-07):**
1. Save `glob_matched = matched` (pre-union list for audit delta).
2. `matched = union_routed_skills(matched, skills, result_cls.bundles)` (D-02).
3. `skill_ratios = _skill_ratios(skills, matched)` — refresh numerators (denominators unchanged per D-08).
4. `instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)`.
5. `packed_files, post_union_trim = trim_packed_files(packed_files, instructions=..., budget_tokens=available, weight=weight)`.
6. If trim dropped paths: update `skipped_files` / `skipped_paths` / `skipped_reason`; re-glob `select_skills(skills, packed paths)`, re-union with same `result_cls.bundles` (D-03).
7. If `skipped_files`: `readmit_files(packed_files, skipped_files, instructions=..., available_tokens=available, weight=weight)` — mirror pre-classify (`review.py:569-576`).
8. After readmit: re-glob `select_skills`, re-union routed bundles, refresh `skill_ratios` + `instructions`.
9. Second `trim_packed_files` pass if readmit grew instructions (`review.py:587-601`).
10. Second `MAX_PROMPT_BYTES` probe via `build_prompt(ReviewRequest(...))` — mirror pre-classify guard (`review.py:650-672`); neutral skip if over (D-07).
11. Pass post-union `matched` to `loaded_skills` sticky kwarg (`review.py:784-788`).

**Do NOT move classify before pack** (D-01, deferred full reorder).

**Remove stale comment** at `review.py:717-719` ("no re-check is needed") — replaced by step 8.

---

### Sticky audit — `comments.py`

**Analog:** existing `Bundles:` metadata line (`comments.py:489-491`).

**D-08 addition:** optional `routed_bundle_skills: list[str] | None` kwarg on `render_body` / `upsert_sticky`. When non-empty, append:
```
Routed bundle skills: security, frontend
```
(sorted by `canonical_index`). `Bundles:` line stays (label→bundle routing audit). `Skills:` line lists final loaded skill names (unchanged). `skill_ratios` denominators still from full merged `load_skills()` set.

---

### Integration test pattern — gap-demo-sandbox gap (D-09)

**Analog:** `test_run_review_filtered_diff_and_classification_metadata` (`test_review_flow.py:363`) — CaptureEngine captures `req.instructions`.

**Fixture shape:**
- Consumer skill `gap-demo-auth-guard` in `tests/fixtures/skills/consumer/security/` with `applies_to: ["**/auth/**"]` and distinctive body token `GAP-DEMO-SKILL-LOADED`.
- Packed path `src/pages/Checkout.jsx` (no `auth` segment).
- Patch `classify()` return or rules so `security` label routes; `route()` yields `security` bundle.
- Assert `GAP-DEMO-SKILL-LOADED` in `captured["req"].instructions` and skill name in `loaded_skills`.

**LLM fallback variant (D-04):** patch `llm_classify` to add `data` label on unmatched path; assert data-bundle skill loads despite no path glob match.

---

### Docs pipeline step — `ARCHITECTURE.md`

**Current (wrong after fix):** step 11 says `route()` is "metadata only (not skill gating)" (`ARCHITECTURE.md:61`).

**Updated sequence:**
```
10. Select skills (glob) + assemble + trim/readmit
11. Classify packed set + optional LLM fallback + route
12. Union routed-bundle skills → re-assemble → re-trim → byte guard
13. Engine review
```

`configuration.md` routing section (`configuration.md:70`) must drop "Does not gate skill loading" for routed bundles; clarify path-glob for non-routed, bundle-union for routed.

## Pitfalls (from RESEARCH + CONTEXT)

| # | Pitfall | Mitigation |
|---|---------|------------|
| 1 | Double-counting skills | Dedupe `bundle/filename` in union helper |
| 2 | Post-union trim drops paths but routed skills vanish | Re-union after trim; routed bundles immune to glob re-select |
| 3 | skill_ratios stale after union | Recompute `_skill_ratios` after final `matched` |
| 4 | Pre-classify byte guard passes, post-union fails | Second `MAX_PROMPT_BYTES` check before `engine.review()` (D-07) |
| 5 | `general` bundle routes but doesn't exist | Union no-ops for missing bundle skills |
| 6 | Demo PR needs classify rule, not just union | Test fixture must assign `security` label; union alone insufficient |

## Test Matrix → Plan Mapping

| Case | Plan | Test file |
|------|------|-----------|
| A Backend-only `.py` unchanged | 09-02 | `test_review_flow.py` |
| B Security skill, path no auth, routed security | 09-03 | `test_review_flow.py` (D-09) |
| C Frontend only, no security union | 09-02 | `test_skills_loader.py` + flow |
| D LLM adds label → union | 09-02 | `test_review_flow.py` |
| E Budget exhaustion → neutral skip | 09-02 | `test_review_flow.py` |
| Union dedupe/sort unit | 09-01 | `test_skills_loader.py` |
