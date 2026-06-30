---
phase: 10-boundary-contracts
verified: 2026-06-30T11:57:37Z
status: human_needed
score: 14/15 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 12/13
  gaps_closed:
    - "antigravity-cli is marked functional=False because the official Antigravity CLI docs confirm no non-interactive/API-key auth mode exists; selecting it for review fails closed with NonFunctionalEngineError listing the still-functional engines"
    - "cursor-cli invokes cursor-agent with --output-format json (not text), and its JSON envelope is unwrapped via the result field before fence parsing"
    - "cursor-cli's token usage is honestly estimated (estimated=True, bytes/4) via the verified-correct stdout-json envelope path instead of the disconnected none strategy"
    - "Consumer-facing docs no longer claim antigravity-cli is selectable for review; gemini-cli dead row replaced with antigravity-cli not-functional row"
    - "run_review emits machine-readable output to $GITHUB_OUTPUT (live-confirmed in UAT test 3 on a real sandbox PR, not just unit-tested)"
  gaps_remaining:
    - "Copilot OTEL WARNING-3 real-token spot-check (UAT test 2) — blocked, no COPILOT_GITHUB_TOKEN available in this session"
  regressions: []
human_verification:
  - test: "Copilot OTEL WARNING-3 real-token spot-check"
    expected: "With engine: copilot-cli on a sandbox repo, the sticky Tokens line shows review WITHOUT the ~est label (estimated=False), confirming COPILOT_OTEL_FILE_EXPORTER_PATH wiring from Plan 05 enables real OTEL capture in CI"
    why_human: "Requires a live CI run with a real COPILOT_GITHUB_TOKEN secret and the real Copilot CLI subprocess writing OTEL spans; UAT test 2 was explicitly blocked (no token available in the verification session) — this is unresolved, not failed, and cannot be closed without the credential"
---

# Phase 10: Boundary Contracts Verification Report

**Phase Goal:** Stabilize the highest-churn-cost boundaries — config resolution, the engine-adapter contract, and machine-readable output — before more adapters and config knobs accrue and make every change N× more expensive to retrofit.
**Verified:** 2026-06-30T11:57:37Z
**Status:** human_needed
**Re-verification:** Yes — after gap-closure plan 10-07 (commits 9f34db1..4dbe3b1), following live UAT (10-UAT.md) that surfaced 2 gaps in the originally-passed phase.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One concrete CliEngineAdapter implements review/classify/classify_skills once for all CLI engines | VERIFIED (regression check) | `src/prevue/engines/cli_adapter.py:28` `class CliEngineAdapter(EngineAdapter)`; `uv run pytest tests/test_engine_contract.py -q` = 48 passed (was 46; +1 new cursor envelope test, +1 functional-filter behavior) |
| 2 | Registry auto-populates by iterating CLI_ENGINE_SPECS — no manual import+dict edit per engine | VERIFIED (regression check) | `registry.py:20`: `ENGINES = {spec.name: spec for spec in CLI_ENGINE_SPECS}`; 4 specs present |
| 3 | Adding a CLI engine is one CliEngineSpec data entry | VERIFIED (regression check) | `spec.py:91` `CLI_ENGINE_SPECS` tuple, 4 entries unchanged in count |
| 4 | Config resolution order (workflow input > prevue.yml > defaults) is declared, documented, and tested | VERIFIED (regression check) | `config.py:43` `CONFIG_PRECEDENCE = "workflow input > .github/prevue.yml > built-in defaults"`; `uv run pytest tests/test_config_precedence.py -q` = passed |
| 5 | engine.raw_args is a list[str] appended after framework argv; a shell string is rejected | VERIFIED (regression check) | `config.py:126` `_validate_raw_args` rejects string; `uv run pytest tests/test_raw_args.py -q` = passed |
| 6 | Per-role models resolve: models.<role> else engine.model else engine default | VERIFIED (regression check) | `uv run pytest tests/test_model_roles.py -q` = passed |
| 7 | compute_cost applies cache-aware formula; vendored pricing snapshot; no runtime fetch | VERIFIED (regression check) | `src/prevue/pricing/__init__.py` present; `uv run pytest tests/test_pricing.py` included in full suite run |
| 8 | run_review emits a compact machine-readable output to $GITHUB_OUTPUT — actually wired, not orphaned | VERIFIED | `emit_machine_output` called at `review.py:215`, `review.py:463`, `review.py:1313` (3 call sites, was 0 at initial verification); **live-confirmed** in UAT test 3 (10-UAT.md): real sandbox PR showed `$GITHUB_OUTPUT` compact keys set, `prevue-result.json` artifact (1055 bytes) downloaded with `schema_version="1.0"` |
| 9 | cursor-cli invokes cursor-agent with --output-format json (not text); JSON envelope unwrapped via result field before fence parsing | VERIFIED | `spec.py:140`: `base_argv=("cursor-agent", "-p", "--output-format", "json")`; `flow.py:294` `_resolve_fence_source` keys on `spec.usage_capture == "stdout-json"`, now true for cursor-cli (`spec.py:146`); new test `test_cursor_json_envelope_unwraps_result_field` (test_engine_contract.py:260) asserts `result.degraded is False`, 1 finding parsed from a mocked envelope `{"result": "<fenced>"}` — PASS |
| 10 | cursor-cli's estimated=True token usage is now backed by a verified envelope-schema fact, not a stale research note | VERIFIED | `spec.py:122-133` code comment cites official Cursor CLI docs schema (no usage fields) and clarifies tokscale reads a separate web billing API, not cursor-agent stdout; `test_fallback_estimated_cursor` (test_usage_capture.py:83) calls `capture_usage(_FakeSpec("stdout-json"), cursor_envelope_fixture)` and asserts `result is None` — PASS |
| 11 | antigravity-cli is marked functional=False; require_functional_adapter fails closed with NonFunctionalEngineError listing only functional engines | VERIFIED | `spec.py:170`: `functional=False`; `registry.py:56-62` raises `NonFunctionalEngineError` when `not spec.functional`; live exec: `require_functional_adapter('antigravity-cli')` raised `"Engine 'antigravity-cli' is registered but not yet functional; choose one of: copilot-cli, claude-code-cli, cursor-cli"` — antigravity-cli correctly excluded from the list |
| 12 | get_adapter('antigravity-cli') still resolves despite functional=False (no regression to install/invoke mechanics) | VERIFIED | Live exec: `get_adapter('antigravity-cli')` returned `CliEngineAdapter antigravity-cli`; `test_antigravity_cli_is_registered_but_not_functional` PASS |
| 13 | require_functional_adapter is actually used at the engine-selection call site, not just defined | VERIFIED | `review.py:559`: `engine = adapter or require_functional_adapter(config.engine)` — production code path, not orphaned |
| 14 | Consumer-facing docs no longer claim antigravity-cli is selectable for review; state the headless-auth blocker | VERIFIED | `docs/configuration.md:245`: `antigravity-cli` row reads "Registered, not functional — no headless/non-interactive auth exists for the agy CLI per official docs; review attempts fail closed with a clear error"; `grep -c gemini-cli docs/configuration.md` = 0 (dead row removed); `grep gemini-cli\|antigravity-cli docs/GETTING-STARTED.md docs/consumer-setup.md` = 0 matches (no stale references) |
| 15 | A human verifies a live Antigravity review on a sandbox PR before declaring it production-functional | SUPERSEDED — no longer applicable | The original truth required human sign-off before declaring antigravity-cli functional. The gap-closure plan resolved this by NOT declaring it functional — `functional=False` makes the human-verify checkpoint moot; the system now fails closed honestly instead of requiring an unclosed approval gate. Treated as resolved by design change, not deferred. |

**Score:** 14/14 applicable truths verified (truth #15 superseded by design — counted as resolved)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/spec.py` | cursor-cli `--output-format json` + `usage_capture="stdout-json"`; antigravity-cli `functional=False` | VERIFIED | Both fields confirmed at lines 140, 146, 170 with citation comments |
| `src/prevue/engines/registry.py` | `require_functional_adapter` fails closed on antigravity-cli | VERIFIED | Lines 43-63; confirmed via live exec raising `NonFunctionalEngineError` |
| `src/prevue/review.py` | `emit_machine_output` wired into `run_review` | VERIFIED | 3 call sites (215, 463, 1313); UAT-confirmed live |
| `tests/test_engine_contract.py` | cursor json argv + envelope-unwrap regression test; FUNCTIONAL list filters on `spec.functional` | VERIFIED | `FUNCTIONAL = sorted(name for name, spec in ENGINES.items() if spec.functional)` line 25; new test at line 260 |
| `tests/test_registry.py` | antigravity registered-but-not-functional tests | VERIFIED | `test_antigravity_cli_is_registered_but_not_functional`, `test_require_functional_adapter_rejects_antigravity` present and passing |
| `tests/test_usage_capture.py` | cursor fallback test uses stdout-json strategy | VERIFIED | `test_fallback_estimated_cursor` uses `_FakeSpec("stdout-json")` |
| `docs/configuration.md` | antigravity-cli row replaces dead gemini-cli row | VERIFIED | Line 245; gemini-cli 0 occurrences |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/prevue/engines/flow.py` | `src/prevue/engines/spec.py` | `_resolve_fence_source` keys on `spec.usage_capture == "stdout-json"` | WIRED | flow.py:294; now applies to both claude-code-cli and cursor-cli |
| `src/prevue/engines/registry.py` | `src/prevue/engines/spec.py` | `require_functional_adapter` checks `spec.functional` | WIRED | registry.py:56; live exec confirms raise |
| `src/prevue/review.py` | `src/prevue/engines/registry.py` | `require_functional_adapter(config.engine)` at engine-selection site | WIRED | review.py:559 — not orphaned, actual production call site |
| `src/prevue/review.py` | `$GITHUB_OUTPUT` | `emit_machine_output` writes compact key=value lines | WIRED (regression fixed + UAT-confirmed) | review.py:1313 inside run_review; UAT test 3 confirmed live in real CI run |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/prevue/engines/spec.py` (cursor-cli) | `base_argv` subprocess invocation | `cursor-agent -p --output-format json` | Yes — confirmed live in UAT test 3 (real `cursor-agent` JSON envelope parsed, sticky comment posted) | FLOWING |
| `src/prevue/engines/usage.py` via `flow.py` | cursor-cli usage capture | `_resolve_fence_source` + `capture_usage` on real envelope | Returns `None` by design (verified-no-usage-fields); falls back to bytes/4 estimate — UAT test 3 showed `~est 1508` live | FLOWING (honest estimate, not a stub) |
| `src/prevue/engines/registry.py` | `require_functional_adapter` gate | `spec.functional` flag | Yes — live exec confirms fail-closed raise with correct engine list | FLOWING |
| `src/prevue/review.py` | `emit_machine_output` | `run_review` result + gate.conclusion | Yes — UAT test 3 confirmed `$GITHUB_OUTPUT` populated and `prevue-result.json` artifact (1055 bytes) downloaded with real findings | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run pytest -q` | 795 passed | PASS |
| Gap-closure scoped tests pass | `uv run pytest tests/test_engine_contract.py tests/test_registry.py tests/test_usage_capture.py -q` | 48 passed | PASS |
| cursor-cli requests json (not text) | `grep -n 'output-format' src/prevue/engines/spec.py` | `base_argv=("cursor-agent", "-p", "--output-format", "json")` | PASS |
| antigravity-cli functional flag flipped | `grep -n 'functional=False' src/prevue/engines/spec.py` | found at antigravity-cli entry | PASS |
| Docs no longer reference dead gemini-cli row | `grep -c gemini-cli docs/configuration.md` | 0 | PASS |
| Docs reference antigravity-cli not-functional status | `grep -q antigravity-cli docs/configuration.md` | found, status text confirms not-functional | PASS |
| require_functional_adapter fails closed live | `uv run python -c "from prevue.engines.registry import require_functional_adapter; require_functional_adapter('antigravity-cli')"` | `NonFunctionalEngineError: Engine 'antigravity-cli' is registered but not yet functional; choose one of: copilot-cli, claude-code-cli, cursor-cli` | PASS |
| get_adapter still resolves antigravity-cli | `uv run python -c "from prevue.engines.registry import get_adapter; print(get_adapter('antigravity-cli').name)"` | `antigravity-cli` | PASS |
| Full local CI mirror clean | `bash scripts/ci-local.sh` | 795 passed, ruff check clean, ruff format clean, actionlint clean, zizmor 0 findings | PASS |
| No debt markers in modified files | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` across 9 gap-closure-touched files | no matches | PASS |

### Probe Execution

No probe scripts (`scripts/*/tests/probe-*.sh`) defined or referenced for this phase. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENGN-10 | 10-02, 10-07 | Consolidate CLI engine adapters into spec-driven generic; functional flag fail-closed mechanism | SATISFIED | CliEngineAdapter + CliEngineSpec unchanged in structure; antigravity-cli now correctly demonstrates the `functional=False` fail-closed path the original phase built but the original UAT use exposed as unexercised (now exercised, live-tested via registry tests) |
| WKFL-05 | 10-04 | Declared config precedence | SATISFIED (regression check) | `CONFIG_PRECEDENCE` constant unchanged; precedence tests green |
| PERF-03 | 10-03, 10-07 | Real token accounting per engine; labeled fallback | SATISFIED | cursor-cli now routes through the verified-correct `stdout-json` envelope path (was disconnected `"none"` strategy); estimated=True is now a confirmed fact not a stale claim; UAT test 3 live-confirmed `~est 1508` rendering correctly |
| ENGN-08 | 10-04 | Adapter raw-args passthrough | SATISFIED (regression check) | `EngineConfig.raw_args` validator unchanged; raw_args tests green |
| ENGN-09 | 10-04 | Per-role model tiering | SATISFIED (regression check) | `_resolve_engine_models` unchanged; model_roles tests green |
| OUTP-05 | 10-05, 10-07-adjacent (already fixed pre-UAT) | Structured machine-readable ReviewResult as job output/artifact | SATISFIED | `emit_machine_output` wired into `run_review` (3 call sites); UAT test 3 live-confirmed `$GITHUB_OUTPUT` populated and artifact uploaded with `schema_version="1.0"` on a real sandbox PR — this is now production-confirmed, not just unit-tested |

No orphaned requirement IDs — all 6 IDs declared across phase 10 plans (`ENGN-10, WKFL-05, PERF-03, ENGN-08, ENGN-09, OUTP-05`) are present in `.planning/REQUIREMENTS.md` and marked Complete, matching codebase evidence above.

### Anti-Patterns Found

None in files modified by the gap-closure plan (`src/prevue/engines/spec.py`, `src/prevue/engines/usage.py`, `src/prevue/engines/registry.py`, `tests/test_engine_contract.py`, `tests/test_registry.py`, `tests/test_usage_capture.py`, `docs/configuration.md`, `docs/GETTING-STARTED.md`, `docs/consumer-setup.md`). No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers. `ruff check` and `zizmor` both report zero findings on the full repo.

**Pre-existing, out-of-scope note (not a phase-10 gap):** `docs/configuration.md` lists `claude-code-cli`'s auth env var as `ANTHROPIC_API_KEY`, but `spec.py:112` actually uses `CLAUDE_CODE_OAUTH_TOKEN` for the adapter's `secret_env`. This drift predates the 10-07 gap-closure plan and is unrelated to either Gap A (cursor-cli) or Gap B (antigravity-cli). Flagging for awareness only — not blocking phase 10 closure.

### Human Verification Required

#### 1. Copilot OTEL WARNING-3 real-token spot-check

**Test:** On a sandbox repo, run a review with `engine: copilot-cli` using a real `COPILOT_GITHUB_TOKEN` secret. Confirm the sticky Tokens line shows real token counts WITHOUT the `~est` label (estimated=False).

**Expected:** Copilot's sticky comment renders real token usage (estimated=False), confirming `COPILOT_OTEL_FILE_EXPORTER_PATH` wiring (Plan 05) enables real OTEL capture end-to-end in CI with the live Copilot CLI subprocess.

**Why human:** This was explicitly attempted in UAT (10-UAT.md test 2) and came back `blocked` — "No COPILOT_GITHUB_TOKEN available in this session to set as a sandbox repo secret." Unit tests use a pre-written OTEL fixture file, not the live CLI writing real spans; this gap cannot be closed without the credential. It is unresolved, not failed — no code change can close it without the live token.

### Gaps Summary

No code gaps remain. Both UAT-surfaced gaps (cursor-cli token-usage envelope path, antigravity-cli false-functional claim) are closed with live-verified code, passing regression suites (795/795), and a clean full CI mirror (ruff, ruff format, actionlint, zizmor — zero findings).

One item remains genuinely unresolved through no fault of the implementation: the Copilot OTEL real-token spot-check (UAT test 2) is `blocked` on missing `COPILOT_GITHUB_TOKEN` credentials in the verification environment — not a code defect, a credential-access constraint. This keeps phase status at `human_needed` rather than `passed`, per the gate rule that any outstanding human-verification item takes priority over a clean truths/artifacts/links table.

All 6 requirement IDs (ENGN-10, WKFL-05, PERF-03, ENGN-08, ENGN-09, OUTP-05) are satisfied with codebase evidence. No regressions detected in the original phase's 11 previously-VERIFIED truths — full 795-test suite green, all gap-closure-relevant suites individually green, and the originally-flagged OUTP-05 wiring defect (now fixed pre-UAT, commit 2b90ab3) remains fixed and was additionally live-confirmed in production via UAT test 3.

---

_Verified: 2026-06-30T11:57:37Z_
_Verifier: Claude (gsd-verifier)_
