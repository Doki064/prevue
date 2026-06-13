---
phase: 06-reusable-workflow-hybrid-classification
plan: 03
subsystem: classification
tags: [pytest, engine-adapter, llm-fallback, hybrid-classification, workflow_call]

requires:
  - phase: 06-reusable-workflow-hybrid-classification
    provides: load_config single-read, EngineAdapter.classify() ABC, unmatched paths signal
provides:
  - Copilot/Claude/Cursor classify() subprocess implementations
  - llm_classify() with degrade-to-general + disclosure
  - run_review wired to load_config + per-file fallback + sticky disclosure
affects:
  - 06-04-skip-pipeline

tech-stack:
  added: []
  patterns:
    - "parse_classify_response validates canonical labels, drops unknowns (Pitfall 6)"
    - "llm_classify zero-token when unmatched empty; best-effort degrade on failure (D-12)"
    - "run_review reuses same adapter instance for fallback (D-10)"

key-files:
  created:
    - src/prevue/classify/llm_fallback.py
  modified:
    - src/prevue/engines/copilot_cli.py
    - src/prevue/engines/claude_code_cli.py
    - src/prevue/engines/cursor_cli.py
    - src/prevue/engines/prompt.py
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_engine_contract.py
    - tests/test_llm_fallback.py
    - tests/test_review_flow.py

key-decisions:
  - "llm_classify(unmatched_paths, adapter, *, model=None) -> tuple[dict[str,str], str | None]"
  - "Disclosure rendered on sticky Metadata line via classification_disclosure kwarg (Open Question 3 lock)"
  - "PREVUE_CONFIG_PATH default .github/prevue.yml in run_review (D-07)"
  - "Degrade label map uses {general: (llm fallback failed)} provenance string"

patterns-established:
  - "CLASSIFY_TIMEOUT_SECONDS=60 for cheap classification calls"
  - "Fallback merge: path->label success vs {general: glob} degrade shapes"

requirements-completed: [WKFL-03, CLSF-02]

duration: 15min
completed: 2026-06-14
---

# Phase 6 Plan 3: Hybrid LLM Fallback Summary

**Per-file LLM fallback via engine classify(), degrade-to-general on failure, run_review single-read config wiring**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-14T00:00:00Z
- **Completed:** 2026-06-14T00:15:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Copilot/Claude/Cursor `classify()` spawn CLI with fenced label prompt, 60s timeout, canonical label validation
- `llm_classify()` sends only unmatched paths; empty list → zero adapter calls; failures degrade to `general` + disclosure
- `run_review` uses `load_config(consumer_path)` once; fallback reuses selected adapter; disclosure in sticky Metadata

## Task Commits

1. **Task 1: Per-engine classify() + contract suite** - `97ec94b` (feat)
2. **Task 2: llm_classify degrade-to-general** - `54808eb` (feat)
3. **Task 3: Wire fallback into run_review** - `199bdd6` (feat)

## Files Created/Modified

- `src/prevue/classify/llm_fallback.py` — `llm_classify()` orchestrator with D-12 degrade path
- `src/prevue/engines/prompt.py` — `parse_classify_response()`, `CLASSIFY_TIMEOUT_SECONDS`
- `src/prevue/engines/copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py` — `classify()` implementations
- `src/prevue/review.py` — single-read config, fallback hook, label merge, disclosure threading
- `src/prevue/github/comments.py` — `classification_disclosure` on Metadata line
- `tests/test_engine_contract.py` — parametrized classify() + Gemini NotImplementedError
- `tests/test_llm_fallback.py` — GREEN CLSF-02 contract tests
- `tests/test_review_flow.py` — default config path, fallback skip/fire, load_config invalidation

## Locked Signatures (Open Questions 1 & 3)

| Symbol | Signature / Location |
|-------|---------------------|
| `llm_classify` | `(unmatched_paths: list[str], adapter: EngineAdapter, *, model: str \| None = None) -> tuple[dict[str, str], str \| None]` |
| Disclosure rendering | `upsert_sticky(..., classification_disclosure=...)` → `render_body` Metadata line |

## Decisions Made

- Tests updated from `degraded: bool` to `disclosure: str | None` return (plan behavior block)
- RecordingAdapter/FailingAdapter implement stub `review()` for ABC compliance in unit tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ABC compliance in llm_fallback test adapters**
- **Found during:** Task 2
- **Issue:** `RecordingAdapter`/`FailingAdapter` missing abstract `review()` blocked test collection
- **Fix:** Added stub `review()` raising NotImplementedError
- **Files modified:** `tests/test_llm_fallback.py`
- **Committed in:** `54808eb`

**2. [Rule 3 - Blocking] Import sort in review.py and test_llm_fallback.py**
- **Found during:** Verification
- **Issue:** ruff I001 on modified import blocks
- **Fix:** `ruff check --fix`
- **Committed in:** task commits (pre-commit clean)

---

**Total deviations:** 2 auto-fixed (both blocking)
**Impact on plan:** Required for test execution and ruff gate. No scope creep.

## Known Stubs

| File | Symbol | Reason |
|------|--------|--------|
| `tests/test_skip.py` | `prevue.skip.should_skip` | Plan 06-04 |

## Issues Encountered

- Full `pytest --cov=prevue` fails on `test_skip.py` import (RED scaffold for 06-04); 293 other tests pass

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 06-04 can add `should_skip` hook after config load; fallback + disclosure already wired
- Live sandbox verification remains for 06-04 checkpoint

## Self-Check: PASSED

- `src/prevue/classify/llm_fallback.py` FOUND
- Commits `97ec94b`, `54808eb`, `199bdd6` verified in git log

---
*Phase: 06-reusable-workflow-hybrid-classification*
*Completed: 2026-06-14*
