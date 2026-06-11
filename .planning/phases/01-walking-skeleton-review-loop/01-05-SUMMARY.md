---
phase: 01-walking-skeleton-review-loop
plan: 05
subsystem: api
tags: [copilot-cli, subprocess, engine-adapter, tdd, security]

requires:
  - phase: 01-walking-skeleton-review-loop
    provides: pydantic ReviewRequest/ReviewResult contract (Plan 03)
  - phase: 01-walking-skeleton-review-loop
    provides: D-12 spike findings — zero-tool prose, github_pat_ prefix (Plan 01)
provides:
  - EngineAdapter ABC (ENGN-01 locked shape)
  - CopilotCliAdapter with zero-tool headless subprocess invocation
  - CopilotAuthError and EngineFailure typed exceptions
  - _build_prompt with UNTRUSTED DATA fencing (D-07)
affects:
  - 01-06 orchestration CLI
  - 01-07 secure workflow wrapper

tech-stack:
  added: []
  patterns:
    - "P2: ports-and-adapters engine seam — adapter never posts to GitHub"
    - "Zero-tool Copilot: copilot -p ... -s --no-ask-user, no --allow-tool"
    - "github_pat_ auth guard before subprocess (A2 spike confirmed)"
    - "Fail-closed: timeout/non-zero/empty → EngineFailure (D-09/D-10)"

key-files:
  created:
    - src/prevue/engines/base.py
    - src/prevue/engines/copilot_cli.py
    - tests/test_copilot_adapter.py
  modified: []

key-decisions:
  - "Zero --allow-tool flags per spike A1 — diff inline in prompt"
  - "Auth guard locks to github_pat_ prefix per spike A2"
  - "Token redaction in EngineFailure stderr snippets (T-05)"

patterns-established:
  - "Engine adapter as only AI-vendor-aware component"
  - "TDD RED→GREEN with monkeypatched subprocess for failure paths"

requirements-completed: [ENGN-01, ENGN-02]

duration: 15min
completed: 2026-06-12
---

# Phase 01 Plan 05: Copilot Engine Adapter Summary

**Pluggable EngineAdapter ABC with zero-tool CopilotCliAdapter — fenced diff prompt, github_pat_ auth guard, fail-closed errors**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-11T20:10:45Z
- **Completed:** 2026-06-12
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 3

## Accomplishments

- `EngineAdapter` ABC with `review(ReviewRequest) -> ReviewResult` locked ENGN-01 shape
- `CopilotCliAdapter` shells out to `copilot -p ... -s --no-ask-user` with 300s timeout
- `_build_prompt` fences diff as UNTRUSTED DATA; excludes PR title/body (D-07)
- Auth guard rejects missing/`ghp_` tokens; all failure paths raise typed exceptions
- 15 unit tests covering prompt, auth, timeout, non-zero exit, empty stdout, success

## Task Commits

1. **Task 1: RED — prompt composition, auth guard, failure-path tests** - `264df00` (test)
2. **Task 2: GREEN — EngineAdapter ABC + CopilotCliAdapter** - `bcd3247` (feat)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `src/prevue/engines/base.py` — `EngineAdapter` ABC port
- `src/prevue/engines/copilot_cli.py` — `CopilotCliAdapter`, `_build_prompt`, auth/failure handling
- `tests/test_copilot_adapter.py` — 15 tests with monkeypatched subprocess

## Decisions Made

- Applied spike A1: zero `--allow-tool` flags (inline diff in prompt)
- Applied spike A2: `github_pat_` prefix guard for fine-grained PAT
- Added `_sanitize_stderr()` to redact token from error messages (T-05 mitigation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Token redaction in EngineFailure messages**
- **Found during:** Task 2 (GREEN implementation)
- **Issue:** Truncated stderr could echo `COPILOT_GITHUB_TOKEN` if CLI leaked it in error output
- **Fix:** Added `_sanitize_stderr()` replacing token with `[REDACTED]` before raising `EngineFailure`
- **Files modified:** `src/prevue/engines/copilot_cli.py`
- **Verification:** `test_nonzero_exit_truncates_stderr_and_never_echoes_token` passes
- **Committed in:** `bcd3247` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 security)
**Impact on plan:** Required for T-05 threat mitigation; no scope creep.

## Issues Encountered

None — all 15 tests pass on first GREEN iteration after token redaction fix.

## Next Phase Readiness

- Plan 06 (orchestration CLI) can wire fetch → adapter → sticky comment
- Plan 07 (workflow wrapper) can invoke `uv run prevue review` with adapter in place

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*

## Self-Check: PASSED

- FOUND: src/prevue/engines/base.py
- FOUND: src/prevue/engines/copilot_cli.py
- FOUND: tests/test_copilot_adapter.py
- FOUND: 264df00
- FOUND: bcd3247
