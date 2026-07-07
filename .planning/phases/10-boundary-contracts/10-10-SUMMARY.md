---
phase: 10-boundary-contracts
plan: "10"
subsystem: api
tags: [copilot-cli, opentelemetry, subprocess, engine-adapter, arg-max, pydantic]

# Dependency graph
requires:
  - phase: 10-boundary-contracts (10-09)
    provides: usage.py::_parse_copilot_otel flat-span OTEL JSONL parser (correct schema, but unreachable in production before this plan)
provides:
  - CliEngineSpec.argv_prompt_max_bytes + "stdin-or-argv" prompt_delivery mode
  - copilot-cli spec flipped to size-gated argv-or-stdin delivery (64 KiB ceiling)
  - cli_adapter.py._invoke "stdin-or-argv" branch implementing the size gate
  - Updated tests asserting the new size-gated contract + boundary/raw_args regression coverage
affects: [10-boundary-contracts (future UAT re-verification of gap 1), any future live-CI OTEL spot-check]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Size-gated dual-delivery prompt mode on a declarative CliEngineSpec (byte-length check chooses -p argv vs stdin per-call)"]

key-files:
  created: []
  modified:
    - src/prevue/engines/spec.py
    - src/prevue/engines/cli_adapter.py
    - tests/test_copilot_adapter.py
    - tests/test_engine_contract.py
    - docs/configuration.md

key-decisions:
  - "copilot-cli prompt_delivery flipped from stdin to size-gated stdin-or-argv with argv_prompt_max_bytes=65_536 (64 KiB) — reaches Copilot CLI 1.0.67's OTEL-emitting -p code path for small/medium PRs while preserving the Phase-1-proven stdin fallback (01-07 Errno 7 ARG_MAX crash) for anything at/over the ceiling"
  - "raw_args (ENGN-08/D-10) still land LAST in argv on both the new argv sub-branch and the stdin fallback branch — no change to the ordering contract"

requirements-completed: [PERF-03]

patterns-established:
  - "Size-gated delivery as declarative spec data (byte ceiling on CliEngineSpec), not a name-check in the adapter"

# Metrics
duration: 3min
completed: 2026-07-05
---

# Phase 10 Plan 10: Size-Gated Copilot -p/OTEL Delivery Summary

**copilot-cli's `CliEngineSpec` gains a `"stdin-or-argv"` prompt-delivery mode with a 64 KiB ceiling — small/medium PR prompts now go via `-p` (Copilot CLI 1.0.67's OTEL-emitting non-interactive code path), oversized prompts keep using the Phase-1-proven stdin fallback with zero ARG_MAX regression risk.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-05T09:44:56Z
- **Completed:** 2026-07-05T09:47:47Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Fixed the confirmed root cause of the recurring Copilot OTEL real-token-capture gap (10-UAT.md gap 1): plain stdin delivery never reached Copilot CLI's OTEL-emitting `-p` code path, regardless of the (correct) 10-09 parser fix.
- Added a size-gated `"stdin-or-argv"` delivery mode to `CliEngineSpec` (declarative, not a per-engine name-check), with `argv_prompt_max_bytes` as the ceiling knob.
- Preserved the Phase-1-proven ARG_MAX safety guarantee: prompts at or over the 64 KiB ceiling fall back to byte-for-byte identical stdin delivery, with a dedicated regression test.
- Updated all tests that hard-coded "copilot never uses `-p`" to the new size-gated contract, plus new boundary and `raw_args`-ordering regression tests.
- Documented the size-gated fallback in `docs/configuration.md`.

## Task Commits

Each task was committed atomically (TDD RED → GREEN cycle for Task 1):

1. **Task 1 (RED): Assert size-gated stdin-or-argv delivery contract** - `7b41854` (test)
2. **Task 1 (GREEN): Add size-gated stdin-or-argv prompt delivery for copilot-cli** - `7a93035` (feat)
3. **Task 2: Update docs to describe the size-gated OTEL capture fallback** - `846b071` (docs)

_No REFACTOR commit — the GREEN implementation was already clean (`ruff format` applied inline, no behavior change)._

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `src/prevue/engines/spec.py` - `CliEngineSpec.argv_prompt_max_bytes` field; `prompt_delivery` Literal extended with `"stdin-or-argv"`; copilot-cli entry flipped to `prompt_delivery="stdin-or-argv", argv_prompt_max_bytes=65_536`; supersession comment rewritten to cite the 10-10 debug-session finding instead of the stale 10-09 narrative
- `src/prevue/engines/cli_adapter.py` - New `elif spec.prompt_delivery == "stdin-or-argv":` branch in `_invoke`: computes `len(prompt.encode("utf-8"))`, appends `-p` + prompt when under the ceiling (no stdin `input`), else falls through to the identical stdin-delivery shape used by the `"stdin"` branch; `raw_args` still appended last on both sub-branches
- `tests/test_copilot_adapter.py` - Rewrote `test_command_uses_s_and_no_ask_user_without_allow_tool`, renamed `test_prompt_passed_via_stdin_not_argv` → `test_oversized_prompt_falls_back_to_stdin_not_argv`, renamed `test_captured_review_prompt_carries_contract_via_stdin` → `test_captured_review_prompt_carries_contract_via_argv`; removed the now-redundant `test_stdin_mode_matches_documented_non_interactive_flags` assertions folded into the rewritten command test; added `test_argv_prompt_max_bytes_boundary` and `test_raw_args_still_last_on_both_delivery_branches`; fixed `test_bad_fence_then_good_retry_sets_retried` (unlisted in the plan but broken by the same behavior change — captures the prompt from `cmd` when `input` is `None`)
- `tests/test_engine_contract.py` - Updated `test_vendor_argv`'s copilot-cli branch to assert `-p` in `cmd` and `input is None`; updated `test_bad_then_good_sets_retried`'s prompt-capture logic to check the tempfile branch (`-f`) before the generic `-p` check (cursor-agent's own base_argv already contains a literal `-p` flag unrelated to prompt delivery — this ordering bug was caught and fixed during RED verification)
- `docs/configuration.md` - Copilot OTEL paragraph now documents both fallback triggers: the new 64 KiB argv size ceiling and OTEL file unavailability

## Decisions Made

- **64 KiB ceiling (`argv_prompt_max_bytes=65_536`) on copilot-cli only**: an order of magnitude below typical ARG_MAX floors (~1-2 MB) and well below the pre-existing `MAX_PROMPT_BYTES` (1 MB) ceiling where the 01-07 crash actually occurred — wide safety margin while covering the common small/medium PR case.
- **Declarative spec flag, not a name-check**: `stdin-or-argv` + `argv_prompt_max_bytes` live on `CliEngineSpec` so the size-gate mechanism could apply to any future CLI engine, consistent with the existing D-01/D-12 pattern (`argv_pty_wrap`, `secret_env_aliases`) of avoiding `spec.name ==` branches in `cli_adapter.py`.
- **Ordering placement**: the new branch sits between `"stdin"` and `"tempfile-arg"` in `_invoke`, per the plan's guidance, without reordering the other three existing branches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `test_bad_fence_then_good_retry_sets_retried` (not in the plan's rewrite list) broken by the delivery-mode change**
- **Found during:** Task 1 GREEN verification (`uv run pytest tests/test_copilot_adapter.py`)
- **Issue:** This test asserted the retry-call's `input` kwarg was non-`None` — true under stdin-only delivery, but the small sample retry prompt now also fits under `argv_prompt_max_bytes` and is delivered via `-p`, so `input` is `None`.
- **Fix:** Read the prompt from `cmd[cmd.index("-p") + 1]` when `input is None`, matching the pattern already established by the plan's Test 3.
- **Files modified:** `tests/test_copilot_adapter.py`
- **Verification:** `uv run pytest tests/test_copilot_adapter.py -q` green.
- **Committed in:** `7a93035` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed a test ordering bug introduced during my own RED-phase edit to `test_bad_then_good_sets_retried` in `test_engine_contract.py`**
- **Found during:** Task 1 RED verification
- **Issue:** My first RED edit checked `"-p" in cmd_list` before the tempfile (`-f`) branch. `cursor-cli`'s `base_argv` (`cursor-agent -p --output-format json`) already contains a literal `-p` flag unrelated to prompt delivery, so the check falsely matched cursor-cli and captured the wrong argv element as the "prompt", making the retry-prompt-differs assertion fail (`test_bad_then_good_sets_retried[cursor-cli]`).
- **Fix:** Reordered the capture-channel `elif` chain to check `-f` (tempfile) before the generic `-p` check.
- **Files modified:** `tests/test_engine_contract.py`
- **Verification:** Re-ran the RED suite; only the intended 6 copilot-related failures remained, `cursor-cli` passed.
- **Committed in:** `7b41854` (Task 1 RED commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs surfaced by/during this change, fixed at the shared point rather than patched around).
**Impact on plan:** Both fixes were necessary for correctness of the test suite; no scope creep — no other files touched.

## Issues Encountered

- `bash scripts/ci-local.sh` stops at the `ruff check .` step (pre-existing, unrelated `E501` in `tests/test_pricing.py:147`, introduced by an earlier commit `fbabe40` on this branch, not touched by this plan's file set). Logged to `.planning/phases/10-boundary-contracts/deferred-items.md` per the executor's scope-boundary rule rather than fixed here. The `pytest --cov=prevue -q` step inside `ci-local.sh` (828 passed) and the scoped/full `pytest -q` runs, plus `ruff check`/`ruff format --check` on every file this plan touched, are all green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The size-gated delivery mechanism is implemented and unit-tested (small-prompt argv path, oversized-prompt stdin fallback, exact-boundary inclusivity, `raw_args` ordering on both branches).
- **Not verifiable from this environment (per the plan's `<verification>` section):** a live GitHub Actions run on a real sandbox PR with a real `COPILOT_GITHUB_TOKEN`, confirming the sticky comment's Tokens line shows `estimated=False` end-to-end for a small-diff PR. This remains a fresh `human_needed` UAT item — the plan explicitly warns this exact gap has recurred twice after being marked "verified," so the next verification pass should insist on live-CI evidence (a PR with diff content under ~50 KB) before closing gap 1 again.

## Self-Check: PASSED
