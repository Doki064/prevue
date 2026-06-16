---
phase: 08-incremental-stateful-review-lifecycle
plan: 03
subsystem: github
tags: [marker-sha, decide-scope, incremental, gate, d-01, d-02, d-03, d-11, tdd]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: "compare fixtures + fingerprint helper (08-01)"
provides:
  - parse_marker_sha/render_marker + MARKER_WITH_SHA (D-01)
  - decide_scope ancestry classifier + fetch_diff_in_scope (D-02/D-03)
  - ReviewConfig incremental/resolve_outdated/max_known_issues knobs (D-11 input contract)
affects:
  - 08-04 (known-issues cap uses max_known_issues)
  - 08-05 (resolve_outdated knob)
  - 08-06 (run_review wires marker→scope→open-set gate)

tech-stack:
  added: []
  patterns:
    - "Marker SHA: hex-bound regex before compare; legacy head-less → None → full review"
    - "decide_scope: repo.compare status + merge_base==last_sha for incremental; else full"
    - "Open-set gate: caller union(new, carried) − resolved via fingerprint(); apply_gate unchanged"

key-files:
  created: []
  modified:
    - src/prevue/github/comments.py
    - src/prevue/github/diff.py
    - src/prevue/gate.py
    - tests/test_comments.py
    - tests/test_diff.py
    - tests/test_gate.py

key-decisions:
  - "_is_prevue_sticky uses _MARKER_RE anchored at body start — startswith(MARKER) misses head= suffix"
  - "Open-set dedupe via fingerprint(path, title) at caller assembly — no Finding.fingerprint field"
  - "Compare mock regex allows ?page=1 for PyGithub pagination on repo.compare"

patterns-established:
  - "fetch_diff_in_scope: compare identifies file set; pr.get_files() supplies full base..head patches"
  - "ReviewConfig lifecycle knobs load through existing load_config review block (no loader change)"

requirements-completed: []

duration: 18min
completed: 2026-06-15
---

# Phase 8 Plan 03: Marker SHA, decide_scope, Gate Open-Set Summary

**SHA-only sticky marker round-trip, repo.compare ancestry classifier with fail-safe full fallback, and ReviewConfig lifecycle knobs feeding D-11 open-set gate input**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-15T12:35:00Z
- **Completed:** 2026-06-15T12:53:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Marker SHA read/write with hex-bound `_MARKER_RE`; legacy head-less markers parse to None (full review)
- `decide_scope` classifies full/incremental/noop from `repo.compare` status and merge-base ancestry; force-push falls back to full
- `fetch_diff_in_scope` filters `pr.get_files()` to in-scope paths with full PR patches (not compare micro-diff)
- `ReviewConfig` gains `incremental`, `resolve_outdated`, `max_known_issues`; open-set gate tests prove no false-green over carried errors

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: Marker SHA read/write (D-01)** — RED `3597268`, GREEN `290568b` (feat)
2. **Task 2: decide_scope + incremental fetch (D-02/D-03)** — RED `d575c0b`, GREEN `a086aa6` (feat)
3. **Task 3: Gate open-set + config knobs (D-11)** — RED `5762047`, GREEN `303af23` (feat)

**Plan metadata:** `6770f52` (docs: complete plan)

## Files Created/Modified

- `src/prevue/github/comments.py` — `MARKER_WITH_SHA`, `_MARKER_RE`, `parse_marker_sha`, `render_marker`; `_is_prevue_sticky` regex anchor
- `src/prevue/github/diff.py` — `decide_scope`, `fetch_diff_in_scope`
- `src/prevue/gate.py` — `incremental`, `resolve_outdated`, `max_known_issues` on `ReviewConfig`
- `tests/test_comments.py` — `TestMarkerSha` (6 cases)
- `tests/test_diff.py` — decide_scope branches + incremental patch test (7 cases)
- `tests/test_gate.py` — `TestGateOpenSet` + config knob tests (7 cases)

## Decisions Made

- `_is_prevue_sticky` now requires `_MARKER_RE` match at body start — plan assumed `startswith(MARKER)` tolerated `head=` but MARKER includes closing `-->` before the suffix
- Open-set exclusion uses `fingerprint(path, title)` at caller assembly time; `Finding` model unchanged (Plan 06 caller owns union)
- No `config.py` loader change — `ReviewConfig.model_validate(raw["review"])` already surfaces new knobs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _is_prevue_sticky for head-bearing markers**
- **Found during:** Task 1 (Marker SHA)
- **Issue:** `startswith(MARKER)` rejects `<!-- prevue:sticky head=<sha> -->` because MARKER ends with `-->` before the head segment
- **Fix:** Anchor `_MARKER_RE.search(body).start() == 0` instead of prefix startswith
- **Files modified:** `src/prevue/github/comments.py`
- **Committed in:** `290568b`

**2. [Rule 3 - Blocking] Compare mock regex allows PyGithub pagination query**
- **Found during:** Task 2 (decide_scope tests)
- **Issue:** `repo.compare` requests include `?page=1`; strict `/?$` regex did not match
- **Fix:** Append `(?:\?.*)?$` to compare URL mock pattern
- **Files modified:** `tests/test_diff.py`
- **Committed in:** `d575c0b`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both required for correct marker detection and testability. No scope creep.

## Issues Encountered

None beyond deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-04 can consume `max_known_issues` for known-issues list fencing
- Plan 08-06 wires marker read → `decide_scope` → open-set `apply_gate`; LIFE-01 not complete until that orchestration lands
- `config.py` single-read path verified green with new review knobs

## Self-Check: PASSED

- FOUND: `.planning/phases/08-incremental-stateful-review-lifecycle/08-03-SUMMARY.md`
- FOUND: `3597268` (test marker)
- FOUND: `290568b` (feat marker)
- FOUND: `d575c0b` (test decide_scope)
- FOUND: `a086aa6` (feat decide_scope)
- FOUND: `5762047` (test gate)
- FOUND: `303af23` (feat gate)

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
