---
phase: 09-classification-skill-loading-multi-call-review
plan: "06"
subsystem: sticky-audit-docs
tags: [sticky, skill-provenance, per-call-tokens, budget-alert, D-10, D-11, OUTP-04, CLSF-03, TDD]
dependency_graph:
  requires:
    - phase: 09-04
      provides: "classify-first reorder; matched from select_skills_hybrid"
    - phase: 09-05
      provides: "per_call token breakdown in engine_meta; run_budget_skipped; multi-call merge"
  provides:
    - "render_body skill_sources kwarg — annotates Skills line with routed/keyword/llm source"
    - "render_body per_call token breakdown — per-bundle token line when >= 2 calls"
    - "render_body run_budget_reached alert — prominent, before Metadata heading (D-10/T-09-20)"
    - "review.py: _skill_sources built via keyword_score per matched skill"
    - "review.py: _run_budget_reached + not_reviewed_run_budget threaded to sticky_base_kwargs"
    - "review.py: per_call list from engine_meta threaded to token_meta"
    - "test_sticky_multicall_token_meta (OUTP-04/D-11)"
    - "ARCHITECTURE.md classify-first pipeline; multi-call section with 5-cap table"
    - "configuration.md routing drives skill loading (not metadata-only); 5 new caps documented"
  affects:
    - "Live UAT (Task 3 checkpoint): confirm gap-demo skill loads + multi-call token meta in sticky"
tech_stack:
  added: []
  patterns:
    - "skill_sources dict: skill name → 'routed'/'keyword'/'llm'; built via keyword_score re-eval post-selection"
    - "per_call: list of {bundle, review} dicts from engine_meta['per_call']; renders when len >= 2"
    - "run_budget_alert: standalone section before Metadata <details>, not inside collapsed block"
    - "T-09-19: skill names escaped via _escape_table_cell in annotated Skills line"
key_files:
  created: []
  modified:
    - src/prevue/github/comments.py
    - src/prevue/review.py
    - tests/test_comments.py
    - tests/test_review_flow.py
    - docs/ARCHITECTURE.md
    - docs/configuration.md
decisions:
  - "skill_sources built via keyword_score re-eval: recompute threshold per matched skill post-selection; LLM double-duty names → 'llm'; below-threshold in routed bundle → 'routed'; crossed threshold → 'keyword'"
  - "per_call renders only when len >= 2 (single-call path: no breakdown noise, unchanged)"
  - "run_budget_alert is a standalone section before Metadata <details>; separate from per-call budget skips"
  - "ARCHITECTURE.md: classify-first pipeline replaces pack-first; route drives skill loading not metadata-only"
  - "configuration.md: routing rewritten to reflect SKIL-01 gap closure and bundle-scoped hybrid selection"
requirements-completed: [OUTP-04, CLSF-03]
duration: "11 min"
completed: "2026-06-21T18:11:21Z"
---

# Phase 09 Plan 06: Sticky Audit Extensions + Docs Update Summary

Sticky now discloses final loaded skills with their selection source (routed/keyword/llm), shows per-bundle/per-call token meta on multi-call runs, and renders a prominent whole-run budget-reached alert outside the collapsed Metadata block; ARCHITECTURE.md and configuration.md updated to match the classify-first + multi-call pipeline.

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-21T17:59:59Z
- **Completed:** 2026-06-21T18:11:21Z
- **Tasks:** 2 auto + 1 deferred (live UAT — user decision)
- **Files modified:** 6

## Accomplishments

### Task 1: Sticky skill-source provenance + per-call token meta + prominent budget alert (D-10/D-11)

**`src/prevue/github/comments.py` — `render_body` extended with 3 new kwargs:**

1. **`skill_sources: dict[str, str] | None`** — maps skill name → selection source ("routed"/"keyword"/"llm"). When present, annotates each skill entry in the Skills metadata line: e.g. `Gap Demo Auth Guard (security, consumer) [routed]`. T-09-19: skill names escaped via `_escape_table_cell`. Absent → backward compatible (no change to existing output).

2. **`token_meta["per_call"]` rendering** — when `per_call` list has ≥2 entries, a `Per-call tokens:` line is added to the metadata, e.g. `Per-call tokens: security 800 · frontend 700`. Single-call (0 or 1 entry) → unchanged Tokens line.

3. **`run_budget_reached: bool` + `run_budget_skipped_count: int`** — when the whole-run cap dropped files, a standalone `### Coverage` alert section is rendered **before** the Metadata `<details>` heading (T-09-20 compliance). Alert text: "**Run token budget reached — N file(s) not reviewed.**" Distinct from per-call packing skips.

**`src/prevue/review.py` — threaded into `sticky_base_kwargs`:**
- `_skill_sources` built via `keyword_score()` re-eval per matched skill against final `packed_files`; `llm_skill_names` set → "llm", below-threshold routed → "routed", crossed threshold → "keyword"
- `_run_budget_reached` / `not_reviewed_run_budget` initialized before the whole-run cap block; `_run_budget_reached=True` set when overflow occurs
- `per_call` list extracted from `result.engine_meta["per_call"]` and threaded into `token_meta`
- Imported `KEYWORD_THRESHOLD`, `keyword_score` from `prevue.skills.selection`

**TDD**: 11 new tests in `tests/test_comments.py` (3 test classes); all RED → GREEN → backward compat verified.

### Task 2: Multi-call sticky integration test + docs pipeline update (CLSF-03)

**`tests/test_review_flow.py`:**
- `test_sticky_multicall_token_meta`: 2-call run via `_upsert_sticky_with_retry` capture; asserts `per_call` present in `token_meta`, aggregate `review` tokens non-negative, `loaded_skills` is a list

**`docs/ARCHITECTURE.md`:**
- System overview: classify-first language replacing "selects matching skills by path glob"
- Mermaid diagram: classify → SKL[skills/ hybrid selector] → PKG → MC[multicall.py] flow
- ASCII layer map: classify before skills; multicall.py added
- Data flow steps 8-16: reordered — classify-first (step 8), load+select skills (step 9), pack (step 10), multi-call split (step 11), engine review (step 12), findings merge+dedupe (step 13 NEW), lifecycle merge (14), gate (15), publish (16)
- Directory rationale: "route for metadata only" removed; replaced with classify-first + gap-closure guard description
- New section "Multi-call review" with 7-row caps table and whole-run budget-reached behavior documented

**`docs/configuration.md`:**
- Quick reference: `routing` row updated to "drives hybrid skill selection"
- Routing section: "Does not gate skill loading" removed; replaced with B+D hybrid selection explanation (routed vs non-routed bundle paths)
- Review section: 5 new rows (`max_review_calls`, `max_tokens_per_call`, `max_total_run_tokens`, `review_concurrency`, `guardrail_skills`) with defaults and descriptions
- Full example: 5 new review caps added with defaults

### Task 3: Live gap-demo-sandbox gap-closure + multi-call UAT (DEFERRED)

Deferred by user decision — implementation complete; live UAT to be run separately.

The classifier transient outage blocked execution of the live sandbox test at checkpoint time. The user approved closing out the implementation phase now and deferring live UAT. All implementation work (Tasks 1 and 2) is complete and committed. UAT can be run independently against the gap-demo-sandbox sandbox repo at any time to confirm gap-demo skill loads and multi-call token meta appear in the sticky comment.

## Task Commits

Each auto task was committed atomically:

1. `b92b18d` — `test(09-06)`: RED — 11 failing tests for skill-source provenance, per-call token meta, prominent budget alert
2. `0133a09` — `feat(09-06)`: GREEN — implement all 3 render_body extensions + review.py threading
3. `abcd784` — `feat(09-06)`: multi-call sticky integration test + docs pipeline update (CLSF-03)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written. The implementation followed the plan's spec exactly.

The nested `def _skill_with_source(entry)` helper inside `render_body` is a minor local pattern decision — it avoids a lambda and keeps the escape call readable. Not a deviation.

## Known Stubs

None — all sticky audit extensions are fully implemented. The skill-source provenance, per-call token meta, and budget-reached alert all wire through to actual data from 09-04/09-05 production code.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-09-19 mitigated | `src/prevue/github/comments.py` | Skill names in `skill_sources` escaped via `_escape_table_cell` in annotated Skills line |
| T-09-20 mitigated | `src/prevue/github/comments.py` | `run_budget_alert` section rendered BEFORE `<details>` block; test asserts `alert_pos < metadata_pos` |

No new trust boundaries introduced beyond the plan's threat model.

## Self-Check

- [x] `src/prevue/github/comments.py` exists — FOUND
- [x] `src/prevue/review.py` exists — FOUND
- [x] `tests/test_comments.py` exists — FOUND
- [x] `tests/test_review_flow.py` exists — FOUND
- [x] `docs/ARCHITECTURE.md` exists — FOUND
- [x] `docs/configuration.md` exists — FOUND
- [x] RED commit `b92b18d` exists — FOUND
- [x] GREEN commit `0133a09` exists — FOUND
- [x] Task 2 commit `abcd784` exists — FOUND
- [x] `uv run pytest tests/test_comments.py -k "skill_source or per_call or budget_alert" -x -q` → 11 passed — VERIFIED
- [x] `uv run pytest -q` → 711 passed — VERIFIED
- [x] `uv run ruff check src/prevue/github/comments.py src/prevue/review.py` → clean — VERIFIED
- [x] `grep -n "metadata only\|not skill gating\|Does not gate skill" docs/ARCHITECTURE.md docs/configuration.md` → 0 matches — VERIFIED
- [x] `grep -q "max_review_calls" docs/configuration.md` → PASS — VERIFIED
- [x] `grep -qi "classify" docs/ARCHITECTURE.md` → PASS — VERIFIED

## Self-Check: PASSED
