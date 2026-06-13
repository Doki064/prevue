---
phase: 06-reusable-workflow-hybrid-classification
plan: 01
subsystem: infra
tags: [pytest, pydantic, yaml, engine-adapter, classification, workflow_call]

requires:
  - phase: 05-multi-engine-adapter-support
    provides: EngineAdapter ABC, registry, prompt fencing patterns
provides:
  - load_config() single-read .github/prevue.yml bundle (PrevueConfig)
  - SkipConfig / FallbackConfig typed sections with extra=forbid
  - EngineAdapter.classify() default-raising capability (D-11)
  - build_classify_prompt() with UNTRUSTED DATA fencing
  - ClassificationResult.unmatched per-file no-glob signal (D-09)
  - Wave 0 RED scaffolds for skip, llm fallback, reusable workflow YAML
affects:
  - 06-02-reusable-workflow
  - 06-03-llm-fallback
  - 06-04-skip-pipeline

tech-stack:
  added: []
  patterns:
    - "Single yaml.safe_load feeds all prevue.yml sections (D-08)"
    - "classify() concrete default-raising method on EngineAdapter (not abstract)"
    - "Per-file unmatched list preserved alongside PR-level general fallback"

key-files:
  created:
    - src/prevue/config.py
    - tests/test_config.py
    - tests/test_skip.py
    - tests/test_llm_fallback.py
    - tests/test_reusable_workflow_yaml.py
  modified:
    - src/prevue/engines/base.py
    - src/prevue/engines/prompt.py
    - src/prevue/classify/classifier.py
    - src/prevue/classify/models.py

key-decisions:
  - "PrevueConfig fields: ruleset, review, skip, fallback, engine — load_config(consumer_path) returns this bundle"
  - "SkipConfig: review_bots[], skip_labels default ['skip-review'], skip_title_patterns[]"
  - "FallbackConfig: enabled default True, model optional str | None"
  - "Engine precedence: PREVUE_ENGINE env > prevue.yml engine.name > DEFAULT_ENGINE"
  - "Ruleset built from single-read raw dict via merge_rules — no second file read"

patterns-established:
  - "Config section models use pydantic extra=forbid (fail-closed on consumer typos)"
  - "build_classify_prompt reuses _escape_line + ~~~UNTRUSTED DATA fence from review prompt"

requirements-completed: [WKFL-03, CLSF-02]

duration: 12min
completed: 2026-06-13
---

# Phase 6 Plan 1: Foundation Summary

**Single-read prevue.yml config loader, EngineAdapter.classify() port, unmatched-path signal, and Wave 0 RED test scaffolds for downstream slices**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-13T18:51:00Z
- **Completed:** 2026-06-13T19:03:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- `load_config()` reads `.github/prevue.yml` once into `PrevueConfig` (ruleset + review + skip + fallback + engine); absent file → all defaults; section typos fail closed
- `EngineAdapter.classify()` added as default-raising concrete method; `build_classify_prompt()` fences untrusted paths
- `ClassificationResult.unmatched` carries per-file paths with no glob match while preserving PR-level `{general}` fallback
- Four Wave 0 RED test files created with names matching `06-VALIDATION.md`; `test_config.py` green, others remain RED for plans 06-02/03/04

## Task Commits

1. **Task 1: Wave 0 RED scaffolds** - `9af8ff0` (test)
2. **Task 2: classify() ABC + prompt + unmatched paths** - `9151db8` (feat)
3. **Task 3: Single-read config loader** - `81d69b1` (feat)

**Style fix:** `ada521a` (style — ruff hygiene in RED scaffolds)

## Files Created/Modified

- `src/prevue/config.py` — `PrevueConfig`, `SkipConfig`, `FallbackConfig`, `load_config()`
- `src/prevue/engines/base.py` — `EngineAdapter.classify()` default raises `NotImplementedError`
- `src/prevue/engines/prompt.py` — `build_classify_prompt()` with closed label set + path fencing
- `src/prevue/classify/models.py` — `ClassificationResult.unmatched: list[str]`
- `src/prevue/classify/classifier.py` — per-file match tracking + unmatched collection
- `tests/test_config.py` — WKFL-03 config loader contract (green)
- `tests/test_skip.py` — NOIS-01 skip contract (RED — awaits 06-04)
- `tests/test_llm_fallback.py` — CLSF-02 fallback contract (RED — awaits 06-03)
- `tests/test_reusable_workflow_yaml.py` — WKFL-01/02/04 YAML guards (RED — awaits 06-02)

## Locked Config Field Names (Claude's Discretion)

| Model | Fields | Defaults |
|-------|--------|----------|
| `PrevueConfig` | `ruleset`, `review`, `skip`, `fallback`, `engine` | absent file → built-in ruleset + section defaults |
| `SkipConfig` | `review_bots`, `skip_labels`, `skip_title_patterns` | `[]`, `["skip-review"]`, `[]` |
| `FallbackConfig` | `enabled`, `model` | `True`, `None` |
| `load_config` | `(consumer_path: str \| None = None) -> PrevueConfig` | path defaults to `.github/prevue.yml` |

## Decisions Made

- Ruleset section parsed from the same `raw` dict as other sections (no second `path.read_text()` via `load_ruleset(consumer_path)`)
- Classifier tracks per-file `matched_any` independently of PR-level label union (D-09 signal without breaking D-03 general fallback)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed per-file unmatched tracking in classifier**
- **Found during:** Task 2
- **Issue:** Initial implementation treated `label in labels` (from another file) as a match for the current file
- **Fix:** Check each file against all specs; set label only when not yet assigned; append path when no spec matches
- **Files modified:** `src/prevue/classify/classifier.py`
- **Committed in:** `9151db8`

**2. [Rule 3 - Blocking] Ruff hygiene in RED scaffolds**
- **Found during:** Plan verification
- **Issue:** Import sort, unused import, line length in new test files blocked `ruff check .`
- **Fix:** Sorted imports, removed unused `pytest`, wrapped long line, formatted `test_config.py`
- **Files modified:** `tests/test_skip.py`, `tests/test_llm_fallback.py`, `tests/test_config.py`
- **Committed in:** `ada521a`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking lint)
**Impact on plan:** Both required for correctness and success-criteria ruff gate. No scope creep.

## Known Stubs

| File | Symbol | Reason |
|------|--------|--------|
| `tests/test_skip.py` | `prevue.skip.should_skip` | Implemented in plan 06-04 |
| `tests/test_llm_fallback.py` | `prevue.classify.llm_fallback.llm_classify` | Implemented in plan 06-03 |
| `tests/test_reusable_workflow_yaml.py` | `.github/workflows/prevue-review.yml` | Created in plan 06-02 |

## Issues Encountered

None beyond auto-fixed deviations above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plans 06-02/06-03/06-04 can wire against fixed `PrevueConfig`, `classify()`, and `unmatched` contracts
- `test_skip.py`, `test_llm_fallback.py`, `test_reusable_workflow_yaml.py` remain RED as intended green targets

## Self-Check: PASSED

- All key files present on disk
- Commits `9af8ff0`, `9151db8`, `81d69b1`, `ada521a` verified in git log

---
*Phase: 06-reusable-workflow-hybrid-classification*
*Completed: 2026-06-13*
