---
phase: 09-classification-skill-loading-multi-call-review
plan: "01"
subsystem: gate-config-test-scaffolds
tags: [ReviewConfig, multi-call, caps, test-scaffolds, RED, gap-fixture]
dependency_graph:
  requires: []
  provides:
    - ReviewConfig.max_review_calls
    - ReviewConfig.review_concurrency
    - ReviewConfig.max_tokens_per_call
    - ReviewConfig.max_total_run_tokens
    - ReviewConfig.guardrail_skills
    - tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md
    - tests/test_selection.py (RED scaffold)
    - tests/test_importscan.py (RED scaffold)
    - tests/test_multicall.py (RED scaffold)
  affects:
    - src/prevue/config.py (ReviewConfig picked up via model_validate)
    - all consumers of ReviewConfig
tech_stack:
  added: []
  patterns:
    - pydantic model_validator (after) for coherence validation
    - RED scaffold pattern with try/except ImportError guard
key_files:
  created:
    - tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md
    - tests/test_selection.py
    - tests/test_importscan.py
    - tests/test_multicall.py
  modified:
    - src/prevue/gate.py
    - tests/test_config.py
    - tests/conftest.py
decisions:
  - "Flat ReviewConfig caps (not nested multicall: sub-model) — parity with existing knobs, extra=forbid preserved (RESEARCH Open Question 2)"
  - "Per-call > run-ceiling coherence validator added to _validate_token_budget"
  - "output_reserve_tokens <= max_tokens_per_call validated in addition to <= max_input_tokens"
  - "gap_shape_skill conftest fixture loads from disk fixture to stay in sync"
metrics:
  duration: "7 min"
  completed: "2026-06-21T16:53:00Z"
  tasks: 3
  files: 7
---

# Phase 09 Plan 01: ReviewConfig Caps + Wave 0 Foundation Summary

Five backward-compatible multi-call/run caps added to ReviewConfig with coherence validators, a gap-demo-sandbox gap-shape fixture, and three RED test scaffolds pinning the Wave 2+ API contracts.

## What Was Built

### Task 1: Five Multi-Call/Run Caps in ReviewConfig (D-09)

Added to `src/prevue/gate.py` `ReviewConfig`:

| Field | Default | Constraint | Purpose |
|-------|---------|------------|---------|
| `max_review_calls` | 1 | ge=1 | ENGN-05: call-count cap; default 1 = single-call path |
| `review_concurrency` | 1 | ge=1 | ENGN-07: parallel cap; default 1 = sequential |
| `max_tokens_per_call` | 120000 | ge=1, le=250000 | D-09: per-call input ceiling |
| `max_total_run_tokens` | 480000 | ge=1 | D-09: whole-run ceiling (classify + Σ calls) |
| `guardrail_skills` | [] | list[str] | D-07: always-on per-call skill keys |

Extended `_validate_token_budget` with two additional coherence checks:
- `max_tokens_per_call <= max_total_run_tokens` (incoherent per-call ceiling)
- `output_reserve_tokens <= max_tokens_per_call` (per-call reserve sanity)

All 58 existing gate/config tests stayed green.

### Task 2: Config Parse Tests for New Caps

Added four test functions to `tests/test_config.py`:
- `test_review_cap_all_new_fields_round_trip`: all five caps load from prevue.yml
- `test_review_cap_defaults_when_no_review_block`: defaults when no review: block
- `test_review_cap_invalid_max_review_calls_raises_via_load_config`: ge=1 via public path
- `test_review_cap_per_call_above_run_ceiling_raises_via_load_config`: coherence via public path

Flat-field decision comment citing RESEARCH Open Question 2 added inline.

### Task 3: Gap-Shape Fixture and RED Scaffolds

**Gap-shape fixture** (`tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md`):
- Frontmatter: `name: Gap Demo Auth Guard`, `description: Verify authorization guards on checkout and payment flows.`, `applies-to: ["**/auth/**"]`
- Body contains `GAP-DEMO-SKILL-LOADED` sentinel token
- Validates as a Skill model instance; bundle=security; gap shape: applies-to does NOT match `src/pages/Checkout.jsx` but bundle IS routed

**conftest fixture**: `gap_shape_skill()` returns a Skill loaded from the gap-shape fixture for unit tests needing the gap shape without disk I/O.

**RED scaffolds** (all fail with ImportError, zero xfail/skip):
- `tests/test_selection.py`: 10 tests for `keyword_score`, `select_skills_hybrid`, `KEYWORD_THRESHOLD` from `prevue.skills.selection` (Plan 09-02 API)
- `tests/test_importscan.py`: 10 tests for `extract_imports`, `referenced_paths` from `prevue.importscan` (Plan 09-03 API)
- `tests/test_multicall.py`: 20 tests for `CallGroup`, `split_into_calls`, `execute_calls`, `merge_findings` from `prevue.multicall` (Plan 09-05 API)

## Verification

```
uv run pytest tests/test_gate.py tests/test_config.py -x -q
# → 62 passed

uv run pytest -q
# → 40 failed (exactly the three new scaffold files), 640 passed

uv run ruff check src/prevue/gate.py src/prevue/config.py
# → All checks passed
```

## Deviations from Plan

**1. [Rule 2 - Missing Validation] Added output_reserve_tokens <= max_tokens_per_call coherence check**
- **Found during:** Task 1 — the plan specified `output_reserve_tokens <= max_tokens_per_call` in the docstring description but didn't explicitly call it out as a validator
- **Issue:** Without this check, a consumer could set `output_reserve_tokens=100000` and `max_tokens_per_call=50000` — semantically incoherent (reserve larger than budget)
- **Fix:** Added third coherence check in `_validate_token_budget` after the per-call > run-ceiling check
- **Files modified:** `src/prevue/gate.py`
- **Commit:** 61f2047

## Known Stubs

None — this plan adds caps and test scaffolds only; no business logic stubs introduced.

## Threat Flags

No new threat surface introduced. The new caps are consumer-controlled config values that flow through the existing `ReviewConfig.model_validate` path with `extra="forbid"` — T-09-01 and T-09-02 mitigations (ge=1 floors and extra-key rejection) are implemented as specified.

## Self-Check

- [x] `src/prevue/gate.py` exists and contains `max_review_calls` — FOUND
- [x] `tests/fixtures/skills/consumer/security/gap-demo-auth-guard.md` exists — FOUND
- [x] `tests/test_selection.py` exists — FOUND
- [x] `tests/test_importscan.py` exists — FOUND
- [x] `tests/test_multicall.py` exists — FOUND
- [x] Task 1 commit 61f2047 — FOUND
- [x] Task 2 commit 3143d45 — FOUND
- [x] Task 3 commit 83431c0 — FOUND

## Self-Check: PASSED
