---
phase: 10-boundary-contracts
plan: "07"
subsystem: api
tags: [engine-adapter, cursor-cli, antigravity-cli, json-envelope, fail-closed]

# Dependency graph
requires:
  - phase: 10-boundary-contracts (plan 02)
    provides: CliEngineSpec.functional flag and stdout-json envelope-unwrap path (Claude Code)
  - phase: 10-boundary-contracts (plan 03)
    provides: usage.capture_usage dispatcher and per-strategy capture contract
provides:
  - cursor-cli requests --output-format json from cursor-agent and unwraps the result field via the existing stdout-json envelope path
  - cursor-cli usage_capture=stdout-json (replaces disconnected "none" strategy); still estimated=True but via the verified-correct code path
  - antigravity-cli functional=False — require_functional_adapter fails closed with NonFunctionalEngineError; get_adapter still resolves it
  - docs/configuration.md "Available engines" table no longer references the dead gemini-cli skeleton row
affects: [10-uat, 10-ship, future-cursor-usage-research]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reuse usage_capture=stdout-json purely for its JSON-envelope-unwrap + graceful-no-usage-block degrade, even when the engine's confirmed schema has no usage fields at all (cursor-cli)"
    - "functional=False as the closing mechanism for unconfirmed/blocked checkpoints rather than leaving functional=True with a silent failure mode"

key-files:
  created: []
  modified:
    - src/prevue/engines/spec.py
    - tests/test_engine_contract.py
    - tests/test_registry.py
    - tests/test_usage_capture.py
    - docs/configuration.md

key-decisions:
  - "cursor-cli requests --output-format json (was text) and usage_capture=\"stdout-json\" (was \"none\") — reuses the Claude envelope-unwrap path; token usage stays estimated=True since the verified envelope schema (type/subtype/is_error/duration_ms/duration_api_ms/result/session_id/request_id) has no usage fields"
  - "antigravity-cli functional=False — official Antigravity CLI docs confirm no headless/API-key auth mode for agy; require_functional_adapter now fails closed instead of shipping an unconfirmed checkpoint as functional=True"
  - "docs/configuration.md gemini-cli row replaced outright with antigravity-cli row (not added alongside) — gemini-cli no longer exists in the registry since the D-12 rename"

patterns-established:
  - "Gap-closure plans that flip a CliEngineSpec field re-run the full contract+registry+usage_capture test trio plus scripts/ci-local.sh as the closing verification gate"

requirements-completed: [PERF-03, ENGN-10]

# Metrics
duration: 5min
completed: 2026-06-30
---

# Phase 10 Plan 07: cursor-cli real JSON envelope + antigravity-cli fail-closed Summary

**cursor-cli now requests `--output-format json` from cursor-agent and reuses Claude's envelope-unwrap path (still estimated, now verified-correct); antigravity-cli flipped to `functional=False` so `require_functional_adapter` fails closed instead of shipping an unconfirmed headless-auth assumption.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-30T11:34:00Z
- **Completed:** 2026-06-30T11:39:07Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments

- Gap A closed: cursor-cli's `base_argv` now ends in `--output-format json` instead of `text`, and `usage_capture="stdout-json"` routes cursor-cli through the exact same envelope-unwrap (`_resolve_fence_source`) and graceful-no-usage-block degrade (`_parse_stdout_json`) logic already proven for claude-code-cli — no new parsing code, just correct spec routing.
- Gap B closed: antigravity-cli is now `functional=False`. `get_adapter("antigravity-cli")` still resolves (install/invoke mechanics unaffected), but `require_functional_adapter("antigravity-cli")` raises `NonFunctionalEngineError` listing only the three still-functional engines (copilot-cli, claude-code-cli, cursor-cli).
- `docs/configuration.md` "Available engines" table no longer carries the dead `gemini-cli` skeleton row (removed by the D-12 rename in Plan 02); replaced with an `antigravity-cli` row documenting the not-functional status and `ANTIGRAVITY_API_KEY` env var.
- Full TDD RED→GREEN cycle followed for Task 1 (tdd="true"): failing tests committed first, then the minimal spec change to turn them green.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: pin cursor-cli JSON envelope contract** - `9f34db1` (test)
2. **Task 1 GREEN: request real cursor-cli JSON envelope** - `432d1c7` (feat)
3. **Task 2: mark antigravity-cli non-functional, fail closed** - `8b45576` (fix)

**Plan metadata:** committed separately per final_commit step

_TDD task 1 produced 2 commits (test → feat) per the RED/GREEN cycle; task 2 was a single atomic commit (no tdd flag, but tests/docs updated within it per plan)._

## Files Created/Modified

- `src/prevue/engines/spec.py` - cursor-cli `base_argv` → `--output-format json`, `usage_capture` → `"stdout-json"`; antigravity-cli `functional` → `False`; citation comments for both verified findings
- `tests/test_engine_contract.py` - argv assertions updated to `json`; new `test_cursor_json_envelope_unwraps_result_field` regression test; `FUNCTIONAL` list now filters on `spec.functional` (3 engines, not 4)
- `tests/test_registry.py` - `test_antigravity_cli_is_functional` → `test_antigravity_cli_is_registered_but_not_functional`; `test_require_functional_adapter_resolves_antigravity` → `test_require_functional_adapter_rejects_antigravity` asserting `NonFunctionalEngineError`
- `tests/test_usage_capture.py` - `test_fallback_estimated_cursor` now uses `_FakeSpec("stdout-json")` against the real `cursor_envelope.json` fixture (no usage block), still asserts `None`
- `docs/configuration.md` - replaced stale `gemini-cli` row with `antigravity-cli` row in the "Available engines" table

## Decisions Made

- Reused `usage_capture="stdout-json"` for cursor-cli purely for its envelope-unwrap mechanics, not because cursor-cli actually reports real tokens — the confirmed envelope schema has no usage fields, so the result is always `None` → caller estimates via bytes/4, exactly as before, but now via the verified-correct code path instead of the disconnected `"none"` strategy.
- Kept `antigravity-cli` registered (not removed) with `functional=False` so `get_adapter` and install/invoke mechanics are unaffected — only the functional gate (`require_functional_adapter`) changes, matching the D-03 mechanism Phase 10 already built for exactly this situation.
- `tests/fixtures/usage/cursor_envelope.json` was left unchanged — it already had no `usage` block, matching the confirmed real schema, so no fixture edit was needed (only the `_FakeSpec` literal in the consuming test changed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed substring-containment bug in own new registry test assertion**
- **Found during:** Task 2 (test_require_functional_adapter_rejects_antigravity)
- **Issue:** Initial assertion `assert "antigravity-cli" not in message` failed because the error message's subject clause (`Engine 'antigravity-cli' is registered but not yet functional`) legitimately contains the substring `antigravity-cli`, even though the "choose one of:" functional-engines list correctly excludes it.
- **Fix:** Split the message on `"choose one of:"` and assert containment/exclusion against only the functional-engines list segment.
- **Files modified:** tests/test_registry.py
- **Verification:** `uv run pytest tests/test_registry.py -x -q` passes
- **Committed in:** 8b45576 (Task 2 commit)

**2. [Scope boundary] Removed stray `prevue-result.json` test artifact from working tree**
- **Found during:** Post-task verification (pytest full run, scripts/ci-local.sh)
- **Issue:** An existing (pre-existing, unrelated to this plan) test in the suite writes `prevue-result.json` to the repo root as a side effect and it is not in `.gitignore`. This surfaced as an untracked file after each `pytest` run.
- **Fix:** Deleted the stray file each time it appeared; did not modify the test or `.gitignore` (out of scope for this plan — pre-existing behavior unrelated to Gap A/Gap B).
- **Files modified:** none (file deleted, not committed)
- **Verification:** `git status --short` clean of untracked files before each commit

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug in own test code, 1 scope-boundary cleanup of a pre-existing unrelated artifact)
**Impact on plan:** Both trivial and contained to test correctness / working-tree hygiene. No scope creep into Gap A/Gap B implementation.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both UAT gaps from `10-UAT.md` (Phase 10 Boundary Contracts live verification) are closed: cursor-cli's token-usage path is now provably correct (verified envelope schema, not a stale assumption), and antigravity-cli fails closed instead of silently shipping an unconfirmed headless-auth bet.
- Full local CI (`scripts/ci-local.sh`) passes: 795 tests, ruff check, ruff format --check, actionlint, zizmor — no new findings.
- No blockers for phase closure; this was the final gap-closure plan in the 10-boundary-contracts phase's gap-fix sequence.

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-30*
