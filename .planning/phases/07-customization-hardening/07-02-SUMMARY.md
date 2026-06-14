---
phase: 07-customization-hardening
plan: 02
subsystem: api
tags: [packing, tokens, diff, gate, disclosure]

requires:
  - phase: 07-01
    provides: RED tests and review budget config knobs
provides:
  - estimate_tokens bytes/4 estimator
  - pack_files greedy whole-file packer with label-rule weights
  - partial->neutral gate conclusion
  - run_review packing wired with skipped-file sticky disclosure
affects: [07-03, 07-04]

tech-stack:
  added: []
  patterns:
    - "Whole-file greedy pack keyed on canonical label weight + churn tiebreak"
    - "partial=True degrades would-be success to neutral (D-23)"
    - "No-fit oversized PR reuses neutral skip path (D-24)"

key-files:
  created:
    - src/prevue/engines/tokens.py
    - src/prevue/pack.py
  modified:
    - src/prevue/gate.py
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - tests/test_gate.py
    - tests/test_review_flow.py
    - tests/test_comments.py

key-decisions:
  - "make_file_weight re-runs GitIgnoreSpec per file — no ClassificationResult change"
  - "Skipped disclosure in ### Coverage with collapsible path list"

patterns-established:
  - "pack_files never splits mid-file; over-budget files go to skipped"
  - "ReviewRequest.diff and build_valid_lines use packed set only"

requirements-completed: [DIFF-03]

duration: 25min
completed: 2026-06-15
---

# Phase 7 Plan 02: DIFF-03 Packing Summary

**Token-budget whole-file packing with security-first weights, partial-coverage neutral verdict, and explicit skipped-file disclosure**

## Performance

- **Duration:** 25 min
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- `estimate_tokens` (bytes/4 round-up) and `pack_files` with `make_file_weight` from label_rules
- `conclude`/`apply_gate` honor `partial` — clean partial reviews never green-pass
- `run_review` packs before engine call; no-fit → neutral skip; sticky Coverage section lists skipped paths

## Task Commits

1. **Task 1: estimate_tokens + pack_files** - `4cc0ef1` (feat)
2. **Task 2: partial->neutral gate** - `c9692e9` (feat)
3. **Task 3: wire packing + disclosure** - `7e8de70` (feat)
4. **Lint/test dedupe** - `f266d61` (fix)

**Plan metadata:** `e7bc74b` (docs — initial), updated in this session

## Files Created/Modified

- `src/prevue/engines/tokens.py` — `estimate_tokens(text)` conservative bytes/4
- `src/prevue/pack.py` — `pack_files`, `make_file_weight` greedy whole-file packer
- `src/prevue/gate.py` — `partial` param on `conclude`/`apply_gate`
- `src/prevue/review.py` — pack step, packed diff to engine, partial gate, skip disclosure kwargs
- `src/prevue/github/comments.py` — Coverage section with skipped paths `<details>`
- `tests/test_*.py` — RED tests green; deduped duplicate scaffolds

## Decisions Made

None — followed plan as specified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Renamed weight factory import**
- **Found during:** Task 3 verification
- **Issue:** `review.py` imported `file_weight_factory` but pack module exports `make_file_weight`
- **Fix:** Aligned import and call site to `make_file_weight`
- **Files modified:** `src/prevue/review.py`
- **Committed in:** `f266d61`

**2. [Rule 1 - Bug] Duplicate test definitions**
- **Found during:** ruff F811 on test files
- **Issue:** `test_no_fit_neutral_skip` and `test_skipped_files_disclosure` defined twice
- **Fix:** Removed duplicate module-level copies; kept class/method versions
- **Files modified:** `tests/test_review_flow.py`, `tests/test_comments.py`
- **Committed in:** `f266d61`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** No scope creep; correctness and lint hygiene only.

## Issues Encountered

- `test_skills_merge.py` RED scaffolds (Plan 07-04) still fail — pre-existing, out of scope for 07-02
- Prior partial executor left `flow.py` and `loader.py` WIP — reverted as out-of-scope

## User Setup Required

None.

## Next Phase Readiness

- 07-03 (OUTP-04 token transparency) can read `engine_meta` and packed set from review flow
- 07-04 (SKIL-03 consumer merge) independent; packing does not touch loader

## Self-Check: PASSED

- FOUND: `src/prevue/engines/tokens.py`
- FOUND: `src/prevue/pack.py`
- FOUND: `src/prevue/gate.py`
- FOUND: `src/prevue/review.py`
- FOUND: `src/prevue/github/comments.py`
- FOUND commits: `4cc0ef1`, `c9692e9`, `7e8de70`, `f266d61`
- `pytest -q --ignore=tests/test_skills_merge.py`: 330 passed
- `ruff check src/prevue tests`: clean

---
*Phase: 07-customization-hardening*
*Completed: 2026-06-15*
