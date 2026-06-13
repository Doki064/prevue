---
phase: 04-structured-findings-merge-gate
plan: 02
subsystem: engines
tags: [pydantic, copilot-cli, json-fence, retry-then-degrade, tdd, engn-03]

requires:
  - phase: 04-structured-findings-merge-gate
    provides: Wave 0 RED scaffolds in test_findings_parsing.py and unidiff dep
provides:
  - engines/parsing.py with extract_json_fence and validate_findings (strict salvage)
  - Finding.severity Literal + ReviewResult.degraded/dropped_findings defaults
  - OUTPUT_CONTRACT prompt section (D-15 rubric, D-22 4C, fence-at-end)
  - CopilotCliAdapter retry-then-degrade loop with _invoke hard-failure isolation
affects: [04-03, 04-04, 04-05]

tech-stack:
  added: []
  patterns:
    - "Last-fence parse + strip all decoy fences from prose"
    - "One bounded retry on fence errors only; salvage never retries"
    - "Degraded ReviewResult never raises EngineFailure"

key-files:
  created:
    - src/prevue/engines/parsing.py
  modified:
    - src/prevue/models.py
    - src/prevue/engines/copilot_cli.py
    - tests/test_findings_parsing.py
    - tests/test_copilot_adapter.py
    - tests/test_models.py

key-decisions:
  - "Strip all ```json fences from prose while parsing only the last fence (decoy defense beyond RESEARCH single-splice)"
  - "Fully-dropped salvage (0 valid of N>0) sets degraded=True to avoid false-green empty results"
  - "Retry hard failure degrades with attempt-1 prose instead of raising"

patterns-established:
  - "Pure parsing in engines/parsing.py; retry/degrade policy in adapter only"
  - "engine_meta retried always; parse_error only on fence-degrade paths"

requirements-completed: [ENGN-03]

duration: 35min
completed: 2026-06-13
---

# Phase 4 Plan 02: Engine JSON Contract Summary

**Schema-validated findings via prose+fence parsing, one bounded retry, strict salvage, and degraded ReviewResult on parse failure — hard failures still raise EngineFailure**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-13T05:00:00Z
- **Completed:** 2026-06-13T05:35:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `engines/parsing.py` GREEN: last-fence extraction, strict `Finding.model_validate(strict=True)` salvage
- `models.py` tightened: `Literal["error","warning","info"]` severity; additive `degraded`/`dropped_findings` defaults
- Copilot prompt carries trusted OUTPUT_CONTRACT (JSON fence-at-end, D-15 rubric, D-22 4C bar)
- `CopilotCliAdapter.review()` refactored: `_invoke` preserves D-09 red-run; retry-then-degrade on fence errors

## Task Commits

1. **Task 1: Tighten models + parsing.py GREEN** - `45a115e` (feat)
2. **Task 2: OUTPUT_CONTRACT tests** - `a9e8818` (test)
3. **Task 2: OUTPUT_CONTRACT implementation** - `faf535e` (feat)
4. **Task 3: Retry-then-degrade tests** - `a7a9fae` (test)
5. **Task 3: Retry-then-degrade loop** - `830c012` (feat)

## Files Created/Modified

- `src/prevue/engines/parsing.py` — `FENCE_RE`, `extract_json_fence`, `validate_findings`
- `src/prevue/models.py` — severity Literal; ReviewResult degraded/dropped_findings
- `src/prevue/engines/copilot_cli.py` — OUTPUT_CONTRACT, `_invoke`, `_build_retry_prompt`, retry loop
- `tests/test_models.py` — Literal rejection + default field tests
- `tests/test_copilot_adapter.py` — TestOutputContract, TestRetryThenDegrade; success-path fence fixtures

## Decisions Made

- Strip **all** json fences from prose (not only the parsed last match) so decoy fences never leak into sticky summary
- All-invalid salvage marks `degraded=True` with `dropped_findings=N` (Open Question 1 resolution)
- Retry subprocess hard failure returns degraded result using attempt-1 prose (never crash)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Strip all decoy fences from prose**
- **Found during:** Task 1 (extract_json_fence GREEN)
- **Issue:** RESEARCH single-splice left earlier decoy ```json blocks in prose; test_last_fence_wins failed
- **Fix:** Remove every regex match from prose in reverse order; parse payload from last match only
- **Files modified:** src/prevue/engines/parsing.py
- **Committed in:** 45a115e

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for D-01 decoy defense; no scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ENGN-03 adapter contract complete; 04-03 can wire gate policy over validated findings
- 138 tests green (excluding positions/gate/checks RED scaffolds)

## Self-Check: PASSED

- FOUND: src/prevue/engines/parsing.py
- FOUND: src/prevue/models.py
- FOUND: src/prevue/engines/copilot_cli.py
- FOUND: tests/test_findings_parsing.py
- FOUND: tests/test_copilot_adapter.py
- FOUND: tests/test_models.py
- FOUND: 45a115e, a9e8818, faf535e, a7a9fae, 830c012

---
*Phase: 04-structured-findings-merge-gate*
*Completed: 2026-06-13*
