---
phase: 10-boundary-contracts
verified: 2026-06-29T11:56:27Z
status: gaps_found
score: 11/13 must-haves verified
overrides_applied: 0
gaps:
  - truth: "run_review emits a compact machine-readable output (schema_version, conclusion, severity counts, tokens, cost) to $GITHUB_OUTPUT"
    status: failed
    reason: "emit_machine_output is defined in review.py but never called from run_review() or any production code path. The prevue review CLI calls run_review(), which does not invoke emit_machine_output. The workflow job outputs (steps.run-review.outputs.*) will be empty at runtime. Plan 05 SUMMARY explicitly acknowledges: 'emit_machine_output call is not yet inserted into run_review() itself.'"
    artifacts:
      - path: "src/prevue/review.py"
        issue: "emit_machine_output defined at line 1352 but never called from run_review() (line 470). grep -n 'emit_machine_output' src/prevue/review.py shows only the definition."
      - path: "src/prevue/cli.py"
        issue: "CLI entry point calls run_review() only; no emit_machine_output call anywhere in production code."
    missing:
      - "Call emit_machine_output(result, conclusion) inside run_review() after gate is finalized and before publish (as specified in Plan 05 action block: 'Call emit_machine_output near the end of run_review after gate is finalized, alongside the check publish')"

  - truth: "A human verifies a live Antigravity review on a sandbox PR before the engine is declared production-functional (token estimate fallback confirmed)"
    status: failed
    reason: "Plan 06 Task 3 is a blocking checkpoint:human-verify that has not been approved. The Plan 06 SUMMARY states: 'Task 3 is blocked on a live human verification of the Antigravity engine on a sandbox PR. This cannot be automated.' The SUMMARY checkpoint section shows the gate open with no approval signal."
    artifacts:
      - path: ".planning/phases/10-boundary-contracts/10-06-SUMMARY.md"
        issue: "Checkpoint section states 'awaiting human verification' with no approved signal"
    missing:
      - "Human must run live Antigravity sandbox review per Plan 06 Task 3 criteria (non-TTY wrapper confirmed, tokens labeled ~est, cost renders, prevue-result.json artifact uploaded, compact job outputs populated, and Copilot OTEL WARNING-3 spot-check passed)"

human_verification:
  - test: "Live Antigravity sandbox review end-to-end"
    expected: "Antigravity review posts sticky summary with findings (pseudo-TTY wrapper prevents stdout-drop); tokens labeled ~est (estimate fallback honest); cost line renders; prevue-result.json artifact uploaded; compact job outputs populated (conclusion, error_count etc.) in downstream job"
    why_human: "Vendor-controlled binary, non-TTY reliability is LOW-confidence per research (Open Q1/A1/A2). Cannot simulate vendor CLI behavior in unit tests."

  - test: "Copilot OTEL WARNING-3 real-token spot-check"
    expected: "With engine: copilot-cli on the sandbox, the sticky Tokens line shows review WITHOUT the ~est label (estimated=False), confirming COPILOT_OTEL_FILE_EXPORTER_PATH wiring from Plan 05 actually enables real OTEL capture in CI"
    why_human: "Requires a live CI run; unit tests simulate the path but cannot confirm the OTEL log file is written and read successfully by the real Copilot CLI subprocess on a runner"
---

# Phase 10: Boundary Contracts Verification Report

**Phase Goal:** Establish and test the behavioral contracts for Phase 10 boundary requirements — engine consolidation (ENGN-10), token accounting (PERF-03), config precedence (WKFL-05), raw-args passthrough (ENGN-08), per-role model tiering (ENGN-09), and versioned output contract (OUTP-05).
**Verified:** 2026-06-29T11:56:27Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One concrete CliEngineAdapter implements review/classify/classify_skills once for all CLI engines | VERIFIED | `src/prevue/engines/cli_adapter.py:28` defines `class CliEngineAdapter(EngineAdapter)`; all 4 engines use it; `uv run pytest tests/test_engine_contract.py -q` = 46 passed |
| 2 | Registry auto-populates by iterating CLI_ENGINE_SPECS — no manual import+dict edit per engine | VERIFIED | `registry.py:20`: `ENGINES = {spec.name: spec for spec in CLI_ENGINE_SPECS}`; SKELETON_ENGINES removed (0 occurrences) |
| 3 | Adding a CLI engine is one CliEngineSpec data entry | VERIFIED | `spec.py:91` defines `CLI_ENGINE_SPECS` as a tuple; antigravity-cli added as one spec entry (D-12) |
| 4 | Per-engine AuthError subclasses still exist and are raised by spec.auth_error | VERIFIED | `python -c "from prevue.engines.copilot_cli import CopilotAuthError; from prevue.engines.cursor_cli import CursorAuthError; from prevue.engines.claude_code_cli import ClaudeAuthError; from prevue.engines.gemini_cli import AntigravityAuthError; print('ok')"` — all import successfully |
| 5 | copilot_cli.__all__ re-exports relied on by tests still resolve | VERIFIED | `build_prompt` and `_sanitize_stderr` confirmed in `__all__`; `uv run pytest tests/test_copilot_adapter.py -q` = 34 passed |
| 6 | functional flag replaces SKELETON_ENGINES; antigravity-cli is functional | VERIFIED | `grep -c 'SKELETON_ENGINES' src/prevue/engines/registry.py` = 0; `get_adapter('antigravity-cli')` returns `CliEngineAdapter antigravity-cli` |
| 7 | Config resolution order (workflow input > prevue.yml > defaults) is declared, documented, and tested | VERIFIED | `config.py:43`: `CONFIG_PRECEDENCE = "workflow input > .github/prevue.yml > built-in defaults"`; `grep -qi 'workflow input > .*prevue.yml > .*default' src/prevue/config.py` = FOUND; `uv run pytest tests/test_config_precedence.py -q` = passed |
| 8 | engine.raw_args is a list[str] appended after framework argv; a shell string is rejected | VERIFIED | `EngineConfig(raw_args='--x')` raises `pydantic.ValidationError`; `cli_adapter.py` appends `_raw_args` LAST; `grep -n 'shell=True' cli_adapter.py` = 0 actual code occurrences; 800 total tests pass |
| 9 | Per-role models resolve: models.<role> else engine.model else engine default, for classify and review | VERIFIED | `config.py:243` defines `_resolve_engine_models`; `review.py` uses `_resolve_engine_models` at classify/review sites; `uv run pytest tests/test_model_roles.py -q` = passed |
| 10 | Claude stdout-json usage captured as real tokens (estimated=False); Cursor/Antigravity fall back to bytes/4 (estimated=True) | VERIFIED | `usage.py:43` defines `capture_usage`; spec usage_capture: claude=stdout-json, copilot=otel-jsonl, cursor/antigravity=none; `uv run pytest tests/test_usage_capture.py -q` = passed |
| 11 | compute_cost applies cache-aware formula; vendored pricing snapshot inside prevue.pricing package; no runtime fetch | VERIFIED | `pricing/__init__.py` exists; `model_prices.json` (2918 models, 1.5 MB); no network imports; `uv run pytest tests/test_pricing.py -q` = passed; `test -d src/prevue/pricing && test -f src/prevue/pricing/__init__.py && ! test -f src/prevue/pricing.py` = PASS |
| 12 | run_review emits a compact machine-readable output (schema_version, conclusion, severity counts, tokens, cost) to $GITHUB_OUTPUT | FAILED | `emit_machine_output` defined at review.py:1352 but never called from run_review() (line 470) or cli.py. The function is ORPHANED — wired to no call site. Workflow job outputs will be empty at runtime. Plan 05 SUMMARY explicitly acknowledges this: "emit_machine_output call is not yet inserted into run_review() itself." |
| 13 | A human verifies a live Antigravity review on a sandbox PR before declaring it production-functional | FAILED | Plan 06 Task 3 is a blocking checkpoint:human-verify. SUMMARY states: "Task 3 is blocked on a live human verification." No approval signal found. |

**Score:** 11/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/spec.py` | CliEngineSpec frozen pydantic model + CLI_ENGINE_SPECS list | VERIFIED | class CliEngineSpec at line 21; CLI_ENGINE_SPECS tuple at line 91 with 4 entries |
| `src/prevue/engines/cli_adapter.py` | CliEngineAdapter(spec) — single generic CLI adapter | VERIFIED | class CliEngineAdapter at line 28; review/classify/classify_skills implemented once |
| `src/prevue/engines/registry.py` | auto-populated ENGINES from CLI_ENGINE_SPECS; functional check | VERIFIED | ENGINES dict from spec iteration at line 20; SKELETON_ENGINES removed |
| `src/prevue/engines/usage.py` | capture_usage(spec, stdout, otel_path) per-strategy parser | VERIFIED | def capture_usage at line 43 |
| `src/prevue/pricing/__init__.py` | compute_cost + load_pricing_table; package re-exports | VERIFIED | def compute_cost at line 110; import from prevue.pricing works |
| `src/prevue/pricing/model_prices.json` | vendored pinned LiteLLM pricing snapshot | VERIFIED | 1.5 MB; 2918 models confirmed |
| `src/prevue/config.py` | EngineConfig (name, model, models, raw_args, pricing); _resolve_model; _resolve_engine_models; documented precedence | VERIFIED | class EngineConfig at line 107; CONFIG_PRECEDENCE at line 43; both resolvers present |
| `src/prevue/review.py` | build_compact_output, build_full_output, emit_machine_output; schema_version | VERIFIED (partially) | All three functions exist; OUTPUT_SCHEMA_VERSION="1.0"; but emit_machine_output is never called from run_review (ORPHANED) |
| `src/prevue/github/comments.py` | cost line in sticky token render | VERIFIED | cost_usd read at line 551; rendered at line 555 |
| `.github/workflows/prevue-review.yml` | job outputs map + upload-artifact step + OTEL env | VERIFIED | outputs: at line 65 with 7 keys; upload-artifact at line 159; COPILOT_OTEL_FILE_EXPORTER_PATH at line 149 |
| `.github/scripts/install-engine-cli.sh` | antigravity-cli install case with checksum verification | VERIFIED | antigravity-cli) case at line 24; PREVUE_ANTIGRAVITY_INSTALL_SHA256 gate present; bash -n exits 0 |
| `.github/workflows/update-pricing.yml` | scheduled LiteLLM pricing bump → PR (D-06b) | VERIFIED | schedule cron trigger; no auto-merge step; permissions scoped |
| `tests/test_config_precedence.py` | WKFL-05 precedence matrix | VERIFIED | exists; 52 contract tests pass |
| `tests/test_usage_capture.py` | PERF-03 per-strategy capture tests | VERIFIED | exists; 7 tests pass |
| `tests/test_pricing.py` | PERF-03 cost compute tests | VERIFIED | exists; 8 tests pass |
| `tests/test_raw_args.py` | ENGN-08 list-form + base-ref-only tests | VERIFIED | exists; Pitfall 4 sentinel asserted |
| `tests/test_model_roles.py` | ENGN-09 per-role resolution tests | VERIFIED | exists; merge_findings D-13 determinism asserted |
| `tests/test_output_contract.py` | OUTP-05 compact + full + schema_version tests | VERIFIED | exists; 10 tests pass including emit_machine_output helper behavior |
| `tests/fixtures/pricing/sample_prices.json` | small pricing fixture | VERIFIED | 957 B; 4-model fixture |
| `tests/fixtures/usage/claude_envelope.json` | sample Claude stdout-json usage envelope | VERIFIED | 461 B; usage block + total_cost_usd |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/prevue/engines/registry.py` | `src/prevue/engines/spec.py` | iterate CLI_ENGINE_SPECS to build ENGINES | WIRED | registry.py:14 imports CLI_ENGINE_SPECS; line 20 builds ENGINES dict |
| `src/prevue/engines/cli_adapter.py` | `src/prevue/engines/flow.py` | review_with_retry | WIRED | cli_adapter passes spec= to flow.review_with_retry |
| `src/prevue/engines/cli_adapter.py` | `src/prevue/engines/spec.py` | spec.secret_env / spec.validate_secret / spec.auth_error / spec.base_argv | WIRED | cli_adapter._invoke() references spec.base_argv, spec.model_flag, spec.prompt_delivery etc. |
| `src/prevue/engines/flow.py` | `src/prevue/engines/usage.py` | capture_usage called in token-meta builders | WIRED | flow.py imports and calls capture_usage post-invoke |
| `src/prevue/engines/usage.py` | `src/prevue/engines/tokens.py` | estimate_tokens fallback when capture returns None | WIRED | usage.py returns None for 'none' strategy; flow.py falls back to estimate_tokens |
| `src/prevue/pricing/__init__.py` | `src/prevue/pricing/model_prices.json` | Path(__file__).parent / 'model_prices.json' | WIRED | pricing/__init__.py uses Path(__file__).parent to load JSON |
| `src/prevue/review.py` | `src/prevue/config.py` | _resolve_engine_models at review/classify model-resolution sites | WIRED | review.py imports _resolve_engine_models; used at _classify_model and _review_model_from_config sites |
| `src/prevue/engines/cli_adapter.py` | `src/prevue/config.py` | raw_args appended from engine_config | WIRED | review.py injects engine._raw_args from config.engine_config.raw_args post-get_adapter |
| `src/prevue/review.py` | `$GITHUB_OUTPUT` | emit_machine_output writes compact key=value lines | NOT_WIRED | emit_machine_output exists as a helper but is NEVER called from run_review() — no call site found anywhere in src/ |
| `.github/workflows/prevue-review.yml` | `prevue-result.json` | upload-artifact uploads the full JSON | WIRED | upload-artifact step at line 159 uploads ${{ runner.temp }}/prevue-result.json |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/prevue/engines/usage.py` | capture_usage return dict | Claude stdout-json envelope / Copilot OTEL JSONL | Yes (when strategy matches) | FLOWING |
| `src/prevue/pricing/__init__.py` | compute_cost return value | vendored model_prices.json (2918 models) | Yes | FLOWING |
| `src/prevue/config.py` | EngineConfig.raw_args | base-ref prevue.yml via load_config | Yes (base-ref gated) | FLOWING |
| `src/prevue/review.py` | emit_machine_output | run_review result + conclusion | No — never called | DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CLI_ENGINE_SPECS contains exactly 4 engines | `python -c "from prevue.engines.spec import CLI_ENGINE_SPECS; names=sorted(s.name for s in CLI_ENGINE_SPECS); assert names==['antigravity-cli','claude-code-cli','copilot-cli','cursor-cli']"` | exit 0 | PASS |
| get_adapter('antigravity-cli') returns CliEngineAdapter | `python -c "from prevue.engines.registry import get_adapter; a=get_adapter('antigravity-cli'); print(type(a).__name__, a.name)"` | CliEngineAdapter antigravity-cli | PASS |
| compute_cost unknown model returns None | `python -c "from prevue.pricing import compute_cost; r=compute_cost('x','no-such-model',{'input':10,'output':10}); assert r is None"` | exit 0 | PASS |
| EngineConfig rejects string raw_args | `python -c "from prevue.config import EngineConfig; import pydantic; EngineConfig(raw_args='--x')"` | pydantic.ValidationError raised | PASS |
| Full test suite passes | `uv run pytest -q` | 800 passed | PASS |
| emit_machine_output called from run_review | `grep -n 'emit_machine_output' src/prevue/review.py \| grep -v 'def emit_machine_output'` | Only definition found; no call site | FAIL |

### Probe Execution

Step 7c: No probe scripts (`scripts/*/tests/probe-*.sh`) defined or referenced for this phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENGN-10 | 10-02 | Consolidate CLI engine adapters into spec-driven generic | SATISFIED | CliEngineAdapter + CliEngineSpec in spec.py/cli_adapter.py; registry auto-populates; 4 engines |
| WKFL-05 | 10-04 | Declared config precedence workflow input > prevue.yml > defaults | SATISFIED | CONFIG_PRECEDENCE constant; _resolve_model; _resolve_engine_models; precedence tests green |
| PERF-03 | 10-03 | Real token accounting per engine; labeled fallback | SATISFIED | capture_usage strategy dispatch; pricing package; per-engine estimated flag; costs in sticky |
| ENGN-08 | 10-04 | Adapter raw-args passthrough as list[str], base-ref-only | SATISFIED | EngineConfig.raw_args with @field_validator; appended LAST in _invoke; sentinel test present |
| ENGN-09 | 10-04 | Per-role model tiering (classify/review/consolidate) | SATISFIED | _resolve_engine_models; classify/review call-sites use per-role model; consolidate reserved (D-13) |
| OUTP-05 | 10-05 | Structured machine-readable ReviewResult as job output/artifact | PARTIALLY SATISFIED | build_compact_output/build_full_output/emit_machine_output exist; schema_version="1.0" on both forms; workflow declares outputs + artifact upload; BUT emit_machine_output is never called from run_review — job outputs will be empty strings at runtime |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/prevue/review.py` | 1352 | `emit_machine_output` defined but never called from `run_review()` — ORPHANED helper | Blocker | OUTP-05 job output contract is not fulfilled at runtime; workflow job outputs will be empty |

No TBD/FIXME/XXX debt markers found in modified files.
No shell=True in production code paths.
No network imports in src/prevue/pricing/.

### Human Verification Required

#### 1. emit_machine_output Integration in run_review

**Test:** Add `emit_machine_output(result, gate.conclusion)` call inside `run_review()` near the end (after gate is finalized, before check publish), then trigger a test PR review and confirm the compact job outputs (conclusion, error_count, etc.) appear in the downstream workflow job.

**Expected:** `steps.run-review.outputs.conclusion` and sibling keys are non-empty in the job that consumes the review; `prevue-result.json` is uploaded as an artifact with `schema_version="1.0"`.

**Why human:** Requires a live CI run to confirm `$GITHUB_OUTPUT` is written correctly and the workflow outputs propagate to downstream jobs.

#### 2. Live Antigravity Sandbox Review

**Test:** In gap-demo-sandbox repo, set `with: engine: antigravity-cli`, provide `ANTIGRAVITY_API_KEY`, open a small test PR, let Prevue review run.

**Expected:** (a) Sticky summary posted with findings/prose (pseudo-TTY wrapper prevents non-TTY stdout drop — NOT an "empty output" EngineFailure). (b) Tokens line shows `~est` label (bytes/4 fallback honest). (c) Cost line renders or labeled estimated. (d) prevue-result.json artifact uploaded. (e) Compact job outputs populated (conclusion non-empty).

**Why human:** Vendor-controlled binary (agy), LOW-confidence non-TTY reliability (research Open Q1, Assumptions A1/A2). Cannot simulate in unit tests.

#### 3. Copilot OTEL WARNING-3 End-to-End

**Test:** On the same sandbox, run one review with `with: engine: copilot-cli`. After COPILOT_OTEL_FILE_EXPORTER_PATH is wired (Plan 05, now in workflow), confirm the sticky Tokens line shows WITHOUT the `~est` label.

**Expected:** Copilot sticky shows real token counts (estimated=False), not bytes/4 estimation. If still `~est`, OTEL log path/read is broken end-to-end despite unit test coverage.

**Why human:** Requires a live CI run with the real Copilot CLI subprocess writing OTEL spans to the configured path. Unit tests use a pre-written fixture file, not the live CLI.

### Gaps Summary

Two gaps block goal achievement:

**Gap 1 (BLOCKER) — OUTP-05 emit not wired into run_review:**
The `emit_machine_output` helper is fully implemented and unit-tested, but it is never called from `run_review()`. The Plan 05 SUMMARY explicitly acknowledged this: "The `emit_machine_output` call is not yet inserted into `run_review()` itself." The workflow's job `outputs:` map references `steps.run-review.outputs.*` keys that will never be populated at runtime. Fix: add `emit_machine_output(result, gate.conclusion)` at the end of `run_review()`, after gate finalization and before `conclude_review_check`.

**Gap 2 (BLOCKER) — Plan 06 blocking human checkpoint not approved:**
Plan 06 Task 3 is a `checkpoint:human-verify` gate requiring a live Antigravity sandbox review and Copilot OTEL spot-check. The task was explicitly marked "awaiting human verification" in the SUMMARY with no approval signal. This is a designed blocking gate for the one vendor-controlled, unverifiable surface (Antigravity CLI non-TTY reliability).

Both gaps are required for OUTP-05 success criterion 6 ("The validated ReviewResult is emitted as a GitHub Actions job output that consumers can chain automation on") and for ENGN-10/D-12 (Antigravity production-functional declaration) to be fully satisfied.

---

_Verified: 2026-06-29T11:56:27Z_
_Verifier: Claude (gsd-verifier)_
