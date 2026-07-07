---
phase: 10-boundary-contracts
plan: "11"
subsystem: engines
tags: [copilot-cli, otel, telemetry, token-usage, testing]

# Dependency graph
requires:
  - phase: 10-boundary-contracts (plan 10)
    provides: stdin-or-argv size-gated prompt delivery reaching Copilot's OTEL-emitting -p path
provides:
  - otel_path construction that never pre-creates the leaf path on disk (file or directory) before Copilot's subprocess runs
  - Regression test guarding against a fourth recurrence of this exact bug
affects: [10-UAT, copilot-otel-real-capture-recurrence debug log]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Unique-but-non-touching path construction: os.path.join(base_dir, f'{uuid.uuid4().hex}.ext') instead of tempfile.mkdtemp when the consumer of the path (an external subprocess/exporter) requires the exact leaf path to not already exist"

key-files:
  created: []
  modified:
    - src/prevue/engines/cli_adapter.py
    - tests/test_copilot_adapter.py
    - .planning/debug/copilot-otel-real-capture-recurrence.md
    - .planning/phases/10-boundary-contracts/10-UAT.md

key-decisions:
  - "otel_path built via os.path.join(base_otel_dir, f'{uuid.uuid4().hex}.jsonl') instead of tempfile.mkdtemp(dir=base_otel_dir) — preserves WR-01 per-call isolation without pre-occupying the exact leaf path Copilot's real file exporter needs to create itself"
  - "10-UAT.md gap 1 status stays 'failed' (not flipped to resolved) — this exact gap has failed live verification twice before on code-level evidence alone; one more live GitHub Actions run is required"

patterns-established:
  - "Non-filesystem-touching unique path construction for paths consumed by an external process's own file-creation logic"

requirements-completed: [PERF-03]

# Metrics
duration: 6min
completed: 2026-07-06
---

# Phase 10 Plan 11: Fix THIRD recurrence of Copilot OTEL real-token-capture gap Summary

**cli_adapter.py's review() no longer pre-creates the per-call OTEL path as a directory via tempfile.mkdtemp — it now builds a unique file-shaped path with os.path.join + uuid4 hex, leaving the exact leaf path non-existent so Copilot's real file exporter can create it as a regular file**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-06T06:33:00Z
- **Completed:** 2026-07-06T06:38:58Z
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- Fixed the THIRD recurrence of the Copilot CLI real-token-usage gap: `otel_path` is now constructed without touching the filesystem at the exact leaf path, matching the real CI-pinned Copilot CLI 1.0.67 file exporter's requirement that the configured path not already exist
- Added a regression guard (`assert not os.path.exists(p)`) to `TestOtelPerCallIsolation` so a future change cannot silently reintroduce pre-creating the OTEL path
- Confirmed zero regressions across the full 835-test suite
- Recorded the fix in both the debug log and 10-UAT.md's gap 1 entry, correctly withholding `resolved` status pending live re-verification

## Task Commits

Each task was committed atomically:

1. **Task 1: Stop pre-creating the OTEL path as a directory; regression-guard it** - `9c62bba` (fix)
2. **Task 2: Full suite regression check + update debug/UAT session status** - `7d3420d` (docs)

**Plan metadata:** (this commit)

## Files Created/Modified
- `src/prevue/engines/cli_adapter.py` - `review()`'s otel_path now built via `os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")` instead of `tempfile.mkdtemp(dir=base_otel_dir)`; added `import uuid`
- `tests/test_copilot_adapter.py` - `TestOtelPerCallIsolation`: renamed and updated `test_two_calls_get_distinct_otel_paths` (regression guard: path never pre-exists, ends in `.jsonl`); renamed and updated `test_makedirs_oserror_degrades_to_job_wide_dir_instead_of_crashing` (patches `os.makedirs` instead of the now-unused `tempfile.mkdtemp`)
- `.planning/debug/copilot-otel-real-capture-recurrence.md` - Appended `## Fix Applied (2026-07-06)` section recording the diff shape and verification
- `.planning/phases/10-boundary-contracts/10-UAT.md` - Appended `fix_update_2026-07-06_FOURTH_ROUND` field to gap 1

## Decisions Made
- Kept the fix to exactly one line of production logic per the plan — `os.makedirs(base_otel_dir, exist_ok=True)` and the `try/except OSError` degrade structure were left unchanged, only the `otel_path` assignment line changed
- Did not touch `usage.py` — `_parse_copilot_otel`'s existing `path.is_dir()`/`else` branch already handles a file-shaped path correctly, confirmed by the full test suite passing with zero modifications there

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Code-level fix is complete and verified (unit + full suite). This is explicitly NOT the end of the gap: per the plan's own success criteria and the project's established verification discipline for this specific recurring gap, `10-UAT.md` gap 1 remains `status: failed` until one more live GitHub Actions run against a real PR (real `COPILOT_GITHUB_TOKEN`) confirms the sticky comment shows real (non-`~est`) token counts end-to-end. That live re-verification is the next required step before this gap can be closed.

---
*Phase: 10-boundary-contracts*
*Completed: 2026-07-06*

## Self-Check: PASSED

All created/modified files exist on disk; all task commit hashes (9c62bba, 7d3420d) and this summary's commit (3a7450e) found in git log.
