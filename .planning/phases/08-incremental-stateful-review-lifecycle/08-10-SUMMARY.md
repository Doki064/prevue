---
phase: 08-incremental-stateful-review-lifecycle
plan: 10
subsystem: infra
tags: [github-actions, cursor-cli, engine-adapter, workflow, subprocess, cwd-isolation, noop-optimization]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: sticky marker with head SHA (parse_marker_sha / MARKER_WITH_SHA) used by pre-flight step

provides:
  - cursor-agent invoked with cwd=PREVUE_CONSUMER_ROOT when env var set (gap #3 closed)
  - pre-flight noop step in reusable workflow gating engine CLI install on same-SHA re-run (gap #4 closed)

affects:
  - any future engine adapter plans (establish cwd-isolation pattern for subprocess.run)
  - workflow YAML tests (test_workflow_yaml.py guards updated)

tech-stack:
  added: []
  patterns:
    - "cwd-isolation: engine adapters resolve PREVUE_CONSUMER_ROOT and pass cwd= to subprocess.run; None fallback for local dev"
    - "noop-gate: workflow pre-flight step uses gh CLI (read-only GITHUB_TOKEN) to read sticky SHA; gates expensive setup behind same-SHA compare"

key-files:
  created: []
  modified:
    - src/prevue/engines/cursor_cli.py
    - .github/workflows/prevue-review.yml
    - tests/test_engine_contract.py
    - tests/test_workflow_yaml.py

key-decisions:
  - "Engine CLI install only (not checkout/uv sync) skipped on noop — prevue review step still runs to refresh marker/check via _finish_noop_review path which does not invoke the engine"
  - "Spoofed sticky marker worst-case: install skipped but review step still runs and re-derives state from live diff; fail-safe by design (T-08-10-03 accepted)"
  - "Pre-flight uses GITHUB_TOKEN read scope only (no new permissions); permissions block unchanged"
  - "PREVUE_CONSUMER_ROOT unset → cwd=None (no regression for local/dev invocation)"
  - "grep -oP with hex-only character class constrains STICKY_SHA to safe characters before any comparison or echo"

requirements-completed: [LIFE-01]

duration: 6min
completed: 2026-06-15
---

# Phase 08 Plan 10: Cursor cwd isolation + workflow noop pre-flight Summary

**cursor-agent subprocess.run gains cwd=PREVUE_CONSUMER_ROOT isolation (gap #3) and a pre-flight step in prevue-review.yml skips engine CLI install on same-SHA noop re-runs (gap #4)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-15T18:43:45Z
- **Completed:** 2026-06-15T18:49:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Fixed gap #3: `cursor_cli.py._invoke` now passes `cwd=PREVUE_CONSUMER_ROOT` to `subprocess.run`; review prose scoped to the consumer repo rather than the `.prevue` framework checkout
- Fixed gap #4: added `preflight` step (id=`preflight`) before `Install engine CLI` in `prevue-review.yml`; step fetches existing sticky comment via `gh api`, extracts `head=<sha>` marker, writes `noop=true|false` to `GITHUB_OUTPUT`; Install engine CLI step gated on `steps.preflight.outputs.noop != 'true'`
- Added 2 new tests in `test_engine_contract.py` (cwd=consumer root when env set, cwd=None when unset) and 3 new tests in `test_workflow_yaml.py` (preflight precedes install, install gated, no contents:write/secrets:inherit); all 53 tests pass

## Task Commits

1. **Task 1: Isolate cursor-agent to consumer repo cwd (gap #3)** - `2368b7d` (feat, TDD RED→GREEN)
2. **Task 2: Pre-flight noop SHA compare gating engine CLI install (gap #4)** - `e3e3316` (feat)

## Files Created/Modified

- `src/prevue/engines/cursor_cli.py` - Resolves `PREVUE_CONSUMER_ROOT` in `_invoke`; passes `cwd=` to `subprocess.run` (None when env unset)
- `.github/workflows/prevue-review.yml` - Adds `preflight` step before Install engine CLI; gates install with `if: steps.preflight.outputs.noop != 'true'`
- `tests/test_engine_contract.py` - Two new cursor cwd tests
- `tests/test_workflow_yaml.py` - Three new reusable workflow YAML guard tests

## Decisions Made

**Install-skip scope: engine CLI only, not checkout + uv sync**

The plan gave permission to skip either just the engine CLI install or the full heavy setup. Decision: skip **engine CLI install only** and keep checkout + uv sync running on noop. Rationale: `prevue review` still runs on every call (including noop) to refresh the sticky marker and check status via `_finish_noop_review`. That step requires the Python environment (uv sync) to be present. Skipping the engine CLI install alone saves ~20-30s of the ~40s overhead while keeping the noop path correct.

**Pre-flight uses read-only gh CLI, no new permission scope**

`gh api repos/.../issues/.../comments` uses `GITHUB_TOKEN` with `pull-requests: read` (covered by the existing `pull-requests: write` scope). No new permission entry needed in the workflow `permissions:` block.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preflight comment text contained "prevue review" string matching existing test guard**

- **Found during:** Task 2 (workflow YAML implementation)
- **Issue:** An inline comment in the preflight `run:` block said "A spoofed marker only affects install-skip; prevue review still runs" — the substring `"prevue review"` caused `test_single_prevue_review_invocation_in_reusable` to find 2 step runs instead of 1
- **Fix:** Rephrased the comment to "the review step still runs" (no substring match)
- **Files modified:** `.github/workflows/prevue-review.yml`
- **Verification:** `uv run pytest tests/test_workflow_yaml.py -q` exits 0 (22 passed)
- **Committed in:** `e3e3316` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Minimal — comment text only, no logic change.

## Issues Encountered

None beyond the auto-fixed deviation above.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The pre-flight step uses the existing `GITHUB_TOKEN` read path. Security review of the `grep -oP` extraction confirms `STICKY_SHA` is constrained to `[0-9a-f]{7,40}` before any use in shell comparisons or echo — no injection vector from comment body content.

## Next Phase Readiness

- Gaps #3 and #4 from 08-VERIFICATION.md closed
- All 53 tests in `test_engine_contract.py` + `test_workflow_yaml.py` pass
- Phase 08 gap closure plans (08-08, 08-09, 08-10) all complete; VERIFICATION.md gaps #1-#4 now addressed

---

## Self-Check: PASSED

- `src/prevue/engines/cursor_cli.py` — exists, contains `PREVUE_CONSUMER_ROOT` and `cwd`
- `.github/workflows/prevue-review.yml` — exists, contains `id: preflight` and `steps.preflight.outputs.noop`
- `tests/test_engine_contract.py` — exists, new cwd tests present
- `tests/test_workflow_yaml.py` — exists, new preflight/noop/permissions tests present
- Commits `2368b7d` and `e3e3316` verified in git log
- `uv run pytest tests/test_engine_contract.py tests/test_workflow_yaml.py -q` — 53 passed

*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-15*
