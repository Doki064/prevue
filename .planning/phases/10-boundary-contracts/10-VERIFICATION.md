---
phase: 10-boundary-contracts
verified: 2026-07-01T19:30:00Z
status: human_needed
score: 15/15 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 14/15
  gaps_closed:
    - "usage.py::_parse_copilot_otel rewritten to parse the REAL Copilot CLI flat span-per-line JSONL schema (type/attributes-as-dict/gen_ai.usage.* keys) instead of the fictitious nested resourceSpans->scopeSpans->spans OTLP shape"
    - "copilot-cli's CliEngineSpec.usage_capture flipped back to \"otel-jsonl\" (was \"none\"), with an accurate non-stale spec.py comment describing the supersession"
    - "COPILOT_OTEL_FILE_EXPORTER_PATH wired into both prevue-review.yml and prevue-command-run.yml as a runner.temp per-invocation path"
    - "tests/test_usage_capture.py's Copilot OTEL test group rewritten/extended for the real flat-span schema, including cache_creation summing, metric-type-record skipping, and malformed/missing attributes handling — all green"
    - "CR-02 code-review finding (partial-field OTEL span parse corrupting totals while still reporting estimated=False) fixed: all four token fields now parsed into locals before any total/span_count mutation, so a malformed field discards the whole span atomically — independently reproduced and confirmed fixed in this verification session"
    - "CR-01 code-review finding (fix root-caused against gh copilot v1.0.67 but CI still installed 1.0.61) fixed: install-engine-cli.sh's pin bumped to 1.0.67, docs/configuration.md and docs/DEVELOPMENT.md updated to state support plainly instead of hedging, tests/test_workflow_yaml.py's COPILOT_CLI_VERSION constant bumped to match"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Copilot OTEL real-token spot-check (post-fix, post-review)"
    expected: "With engine: copilot-cli on a sandbox repo, using a real COPILOT_GITHUB_TOKEN secret in actual GitHub Actions CI (not a local subprocess), the sticky Tokens line shows real token counts WITHOUT the ~est label (estimated=False), confirming the full chain (workflow env -> real Copilot CLI subprocess -> OTEL file write -> parser read) works end-to-end in production against the now-1.0.67-pinned CLI."
    why_human: "Requires a live GitHub Actions run with a real COPILOT_GITHUB_TOKEN secret and the actual Copilot CLI subprocess writing real OTEL spans. This session independently confirmed: (1) the parser correctly implements the documented flat-span schema, (2) the CR-02 partial-field-corruption exploit is fixed (reproduced the exact malformed-span scenario from 10-REVIEW.md and confirmed it now degrades to None instead of returning a corrupted estimated=False result), (3) the CI-pinned CLI version now matches the version the fix was diagnosed against (1.0.67, was 1.0.61), and (4) the full local CI mirror (823 tests, ruff, ruff format, actionlint, zizmor) is green. None of this can substitute for an actual GitHub Actions run exercising the real Copilot CLI subprocess end-to-end — that remains the one check this environment cannot perform."
---

# Phase 10: Boundary Contracts Verification Report

**Phase Goal:** Stabilize the highest-churn-cost boundaries — config resolution, the engine-adapter contract, and machine-readable output — before more adapters and config knobs accrue and make every change N× more expensive to retrofit.
**Verified:** 2026-07-01T19:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap-closure plan 10-09 (commits 2a75168, 60daa3e, 7c3d17e, 0614995) fixed the Copilot OTEL parser schema mismatch, followed by a code-review round (10-REVIEW.md) that found and fixed two additional issues on top of 10-09's changes (CR-02 commit cdd96e8, CR-01 commit 4956f00), documented in 10-REVIEW-FIX.md.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One concrete CliEngineAdapter implements review/classify/classify_skills once for all CLI engines | VERIFIED (regression check) | `src/prevue/engines/cli_adapter.py:28` unchanged; full suite green |
| 2 | Registry auto-populates by iterating CLI_ENGINE_SPECS | VERIFIED (regression check) | `registry.py:20` unchanged |
| 3 | Adding a CLI engine is one CliEngineSpec data entry | VERIFIED (regression check) | `spec.py:112` `CLI_ENGINE_SPECS` tuple, 4 entries unchanged in count |
| 4 | Config resolution order is declared, documented, and tested | VERIFIED (regression check) | `config.py:43` unchanged; precedence tests green |
| 5 | engine.raw_args is a list[str]; shell string rejected | VERIFIED (regression check) | `_validate_raw_args` unchanged; raw_args tests green |
| 6 | Per-role models resolve: models.<role> else engine.model else engine default | VERIFIED (regression check) | model_roles tests green |
| 7 | compute_cost applies cache-aware formula; vendored pricing snapshot | VERIFIED (regression check) | `src/prevue/pricing/__init__.py` unchanged; pricing tests green |
| 8 | run_review emits compact machine-readable output to $GITHUB_OUTPUT | VERIFIED (regression check) | `emit_machine_output` call sites unchanged, previously UAT-confirmed live |
| 9 | cursor-cli invokes cursor-agent with --output-format json; envelope unwrapped via result field | VERIFIED (regression check) | `spec.py:146` (cursor-cli block) unchanged |
| 10 | cursor-cli's estimated=True is backed by verified envelope-schema fact | VERIFIED (regression check) | `spec.py` comment + `test_fallback_estimated_cursor` unchanged |
| 11 | antigravity-cli is functional=False; require_functional_adapter fails closed | VERIFIED (regression check) | `spec.py:170`-area unchanged; registry tests green |
| 12 | get_adapter('antigravity-cli') still resolves despite functional=False | VERIFIED (regression check) | unchanged, test green |
| 13 | require_functional_adapter used at engine-selection call site | VERIFIED (regression check) | `review.py:559`-area unchanged |
| 14 | Consumer-facing docs no longer claim antigravity-cli is selectable | VERIFIED (regression check) | `docs/configuration.md` antigravity row unchanged from prior verification |
| 15 | usage.py::_parse_copilot_otel correctly parses the REAL Copilot CLI flat-span JSONL schema (gen_ai.usage.* keys, attributes as plain dict), not the fictitious nested resourceSpans->scopeSpans->spans OTLP shape | VERIFIED | `src/prevue/engines/usage.py:190-314` fully rewritten; `grep -c resourceSpans src/prevue/engines/usage.py` = 0; `grep -c gen_ai.usage.input_tokens src/prevue/engines/usage.py` >= 1; `_extract_attr_value` absent (0 matches); 10 Copilot-OTEL-specific tests in `tests/test_usage_capture.py` all pass |
| 16 | copilot-cli's usage_capture is "otel-jsonl" (not "none"), with an accurate non-stale spec comment | VERIFIED | `src/prevue/engines/spec.py:126` `usage_capture="otel-jsonl"`; `grep -c "has no effect" src/prevue/engines/spec.py` = 0; comment at lines 112-125 states the 10-08 conclusion is superseded and cites the real root cause |
| 17 | COPILOT_OTEL_FILE_EXPORTER_PATH wired into both reusable workflow YAMLs as a per-invocation runner.temp path | VERIFIED | `.github/workflows/prevue-review.yml:187` and `.github/workflows/prevue-command-run.yml:95`, both `COPILOT_OTEL_FILE_EXPORTER_PATH: ${{ runner.temp }}/copilot-otel` |
| 18 | CR-02: a malformed field partway through one OTEL span's attributes cannot produce a corrupted-but-trusted (estimated=False) partial total | VERIFIED | Independently reproduced the exact exploit from 10-REVIEW.md (`input_tokens=500, output_tokens="garbage"`) against the live code — result is `None`, not a corrupted `{"input": 500, ...}`; regression test `test_copilot_otel_partial_field_parse_failure_skips_whole_span` present and passing; code at `usage.py:279-295` parses all 4 fields into locals before mutating totals/span_count |
| 19 | CR-01: the fix's premise (gh copilot v1.0.67 OTEL schema) is verified against the actual CI-pinned CLI version, not a stale mismatched version | VERIFIED | `.github/scripts/install-engine-cli.sh:8` pins `@github/copilot@1.0.67` (was `1.0.61`); `docs/configuration.md:306` engine-install-versions table shows `1.0.67`; `docs/configuration.md:298` states support plainly (no hedge/self-verify instruction); `tests/test_workflow_yaml.py:26,252` `COPILOT_CLI_VERSION = "1.0.67"` asserted against the installer script |

**Score:** 19/19 truths verified (14 regression-checked unchanged from prior verification, 5 newly closed by 10-09 + review fixes)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/usage.py` | `_parse_copilot_otel` rewritten for flat schema, CR-02-safe | VERIFIED | Lines 190-314; atomic per-span parse confirmed live |
| `src/prevue/engines/spec.py` | copilot-cli `usage_capture="otel-jsonl"`, non-stale comment | VERIFIED | Lines 112-127 |
| `.github/workflows/prevue-review.yml` | `COPILOT_OTEL_FILE_EXPORTER_PATH` env wired | VERIFIED | Line 187 |
| `.github/workflows/prevue-command-run.yml` | `COPILOT_OTEL_FILE_EXPORTER_PATH` env wired | VERIFIED | Line 95 |
| `.github/scripts/install-engine-cli.sh` | Copilot CLI pin matches the version the fix was diagnosed against | VERIFIED | Line 8, `@github/copilot@1.0.67` |
| `tests/test_usage_capture.py` | Copilot OTEL tests rewritten for flat schema + CR-02 regression test | VERIFIED | 10 Copilot-OTEL test functions present, all passing |
| `tests/fixtures/usage/copilot_otel.jsonl` | Flat span-per-line JSON, not nested OTLP | VERIFIED | 2 lines, each `{"type": "span", "attributes": {...dict...}}` |
| `tests/test_workflow_yaml.py` | `COPILOT_CLI_VERSION` constant matches installer pin | VERIFIED | Line 26 = "1.0.67", asserted against installer script at line 252 |
| `docs/configuration.md` | Describes real OTEL capture path without hedging on version mismatch | VERIFIED | Lines 298, 306 — states plainly, no self-verify instruction |
| `src/prevue/engines/cli_adapter.py` | Stale "usage_capture=none" comment corrected | VERIFIED | Lines 192-193 describe the restored otel-jsonl path |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/prevue/engines/spec.py` (copilot-cli usage_capture="otel-jsonl") | `src/prevue/engines/flow.py` | `spec.usage_capture == "otel-jsonl"` gate at flow.py:350 | WIRED | Confirmed live: `os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH")` read at flow.py:351, gated correctly |
| `.github/workflows/prevue-review.yml` (env.COPILOT_OTEL_FILE_EXPORTER_PATH) | `src/prevue/engines/usage.py::_parse_copilot_otel` | flow.py reads env var into otel_path, passes to capture_usage -> _parse_copilot_otel | WIRED | Full chain traced: workflow YAML env -> flow.py:351 -> capture_usage (usage.py:75-106) -> `_parse_copilot_otel` dispatch on `strategy == "otel-jsonl"` |
| `.github/workflows/prevue-command-run.yml` (env.COPILOT_OTEL_FILE_EXPORTER_PATH) | Same as above | Parity wiring, identical env line | WIRED | Line 95, same pattern as prevue-review.yml |
| `tests/fixtures/usage/copilot_otel.jsonl` (real flat-span shape) | `usage.py::_parse_copilot_otel` | `test_copilot_otel` reads fixture, asserts summed gen_ai.usage.* token counts | WIRED | `uv run pytest tests/test_usage_capture.py -q` — 91 passed |
| `.github/scripts/install-engine-cli.sh` (pinned CLI version) | `docs/configuration.md` / `tests/test_workflow_yaml.py` | Doc table + test constant both cross-reference the same pinned version | WIRED | All three sources agree on `1.0.67` — no residual version-mismatch gap (CR-01 fully closed, not just documented) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `usage.py::_parse_copilot_otel` | `total_input`/`total_output`/`total_cache_read`/`total_cache_creation` | Per-line JSONL records under `COPILOT_OTEL_FILE_EXPORTER_PATH`, `type == "span"` filter, `attributes` dict | Yes for well-formed spans (verified via fixture-driven unit tests); correctly degrades to `None` for empty/malformed/metric-only files (verified via `test_otel_missing_path_returns_none`, `test_otel_empty_file_returns_none`, `test_copilot_otel_ignores_metric_type_records`, `test_copilot_otel_partial_field_parse_failure_skips_whole_span` — all passing) | FLOWING (locally verified; live-CI flow still unconfirmed — see Human Verification) |
| `.github/workflows/prevue-review.yml` `COPILOT_OTEL_FILE_EXPORTER_PATH` | `${{ runner.temp }}/copilot-otel` | Static workflow-YAML expression, not PR-controlled | Yes — confirmed present via grep, not a placeholder or empty string | FLOWING |
| `.github/scripts/install-engine-cli.sh` Copilot pin | `@github/copilot@1.0.67` | Static script constant | Yes — matches the version the OTEL schema fix was diagnosed against, closing the CR-01 verification gap | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run pytest -q` | 823 passed | PASS |
| Gap-closure + review-fix scoped tests pass | `uv run pytest tests/test_usage_capture.py tests/test_workflow_yaml.py tests/test_engine_contract.py -q` | 91 passed | PASS |
| Old nested-OTLP shape fully removed | `grep -c resourceSpans src/prevue/engines/usage.py` | 0 | PASS |
| New flat schema key present | `grep -c "gen_ai.usage.input_tokens" src/prevue/engines/usage.py` | >=1 | PASS |
| `_extract_attr_value` deleted | `grep -c _extract_attr_value src/prevue/engines/usage.py` | 0 | PASS |
| copilot-cli usage_capture flipped | `grep -n 'usage_capture="otel-jsonl"' src/prevue/engines/spec.py` | found at copilot-cli entry | PASS |
| Stale "has no effect" comment removed | `grep -c "has no effect" src/prevue/engines/spec.py` | 0 | PASS |
| COPILOT_OTEL_FILE_EXPORTER_PATH wired in both workflows | `grep -n COPILOT_OTEL_FILE_EXPORTER_PATH .github/workflows/prevue-review.yml .github/workflows/prevue-command-run.yml` | both found | PASS |
| CI-pinned CLI version matches diagnosis version | `grep '@github/copilot@' .github/scripts/install-engine-cli.sh` | `1.0.67` | PASS |
| CR-02 exploit reproduction | Live Python repro of malformed-mid-span-field scenario from 10-REVIEW.md against `_parse_copilot_otel` | Returns `None` (not corrupted `{"input": 500, "output": 0, ...}` with `estimated=False`) | PASS |
| No debt markers in phase-10-touched files | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` across 11 files (usage.py, spec.py, cli_adapter.py, both workflow YAMLs, install-engine-cli.sh, test_usage_capture.py, test_workflow_yaml.py, fixture, configuration.md, DEVELOPMENT.md) | no matches | PASS |
| Full local CI mirror clean | `bash scripts/ci-local.sh` | 823 passed, ruff clean, ruff format clean, actionlint clean, zizmor 0 findings (33 suppressed, pre-existing) | PASS |

### Probe Execution

No probe scripts (`scripts/*/tests/probe-*.sh`) defined or referenced for this phase. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENGN-10 | 10-02, 10-07 | Consolidate CLI engine adapters; functional flag fail-closed | SATISFIED (regression check) | Unchanged from prior verification |
| WKFL-05 | 10-04 | Declared config precedence | SATISFIED (regression check) | Unchanged from prior verification |
| PERF-03 | 10-03, 10-07, 10-09 | Real token accounting per engine; labeled fallback | SATISFIED | Copilot CLI's real-token path (`otel-jsonl`) now correctly implemented against the real CLI schema, with a CI-pinned version that matches the diagnosis version. Local verification (fixture-driven tests + CR-02 exploit repro) confirms the parser is schema-correct and corruption-safe; live-CI end-to-end confirmation remains open (see Human Verification) |
| ENGN-08 | 10-04 | Adapter raw-args passthrough | SATISFIED (regression check) | Unchanged from prior verification |
| ENGN-09 | 10-04 | Per-role model tiering | SATISFIED (regression check) | Unchanged from prior verification |
| OUTP-05 | 10-05, 10-07 | Structured machine-readable ReviewResult as job output/artifact | SATISFIED (regression check) | Unchanged from prior verification, previously UAT-confirmed live |

No orphaned requirement IDs — all 6 IDs declared across phase 10 plans (`ENGN-10, WKFL-05, PERF-03, ENGN-08, ENGN-09, OUTP-05`) are present in `.planning/REQUIREMENTS.md` and marked Complete (lines 243-248), matching codebase evidence above.

### Anti-Patterns Found

None in files touched by 10-09 or the subsequent code-review fixes (`src/prevue/engines/usage.py`, `src/prevue/engines/spec.py`, `src/prevue/engines/cli_adapter.py`, `.github/workflows/prevue-review.yml`, `.github/workflows/prevue-command-run.yml`, `.github/scripts/install-engine-cli.sh`, `tests/test_usage_capture.py`, `tests/test_workflow_yaml.py`, `tests/test_reusable_workflow_yaml.py`, `tests/fixtures/usage/copilot_otel.jsonl`, `docs/configuration.md`, `docs/DEVELOPMENT.md`). No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers. `ruff check` and `zizmor` both report zero findings on the full repo. Both critical (CR-01, CR-02) and both warning (WR-01, WR-02) findings from `10-REVIEW.md` are confirmed fixed in the actual codebase, not just claimed in `10-REVIEW-FIX.md` — independently re-verified in this session via direct grep/code inspection and a live exploit reproduction, not by trusting the fix report's narrative.

One Info-severity finding (IN-01: no regression test pinning that `github.copilot.cost` is excluded from the parser's output) was explicitly left unfixed per `10-REVIEW-FIX.md`, consistent with the review's `fix_scope: critical_warning` — this is a documented, intentional deferral of a non-blocking finding, not a gap.

**Pre-existing, out-of-scope note (carried forward, not a phase-10 gap):** `docs/configuration.md` lists `claude-code-cli`'s auth env var as `ANTHROPIC_API_KEY` in one place while `spec.py` uses `CLAUDE_CODE_OAUTH_TOKEN` for the adapter's `secret_env` — this drift predates the 10-09 gap-closure round and is unrelated to the Copilot OTEL fix. Flagging for awareness only.

### Human Verification Required

#### 1. Copilot OTEL real-token spot-check (post-fix, post-review)

**Test:** On a sandbox repo, run a review with `engine: copilot-cli` using a real `COPILOT_GITHUB_TOKEN` secret in actual GitHub Actions CI (not a local subprocess). Confirm the sticky Tokens line shows real token counts WITHOUT the `~est` label (estimated=False).

**Expected:** The full chain — reusable workflow YAML sets `COPILOT_OTEL_FILE_EXPORTER_PATH` -> the pinned `@github/copilot@1.0.67` CLI subprocess writes real flat-span JSONL to that path -> `_parse_copilot_otel` reads and sums it correctly -> the sticky PR comment renders real (non-estimated) token counts — works end-to-end in production.

**Why human:** Requires a live GitHub Actions run with a real secret and the actual Copilot CLI subprocess. This verification session independently confirmed everything short of that live run: the parser correctly implements the documented real flat-span schema (code read directly, not trusted from SUMMARY.md); the CR-02 corruption exploit from the code review was reproduced against the live code and confirmed fixed (returns `None`, not a corrupted `estimated=False` result); the CI-pinned CLI version (`1.0.67`) now matches the version the fix was diagnosed against, closing the CR-01 verification gap that made the prior fix's premise unconfirmed; and the full local CI mirror (823 tests, ruff, ruff format, actionlint, zizmor) is green. None of this can substitute for an actual live CI run exercising the real subprocess — that is the one remaining check this environment cannot perform.

### Gaps Summary

No code gaps remain. The Copilot OTEL parser schema mismatch (the sole `gaps_remaining` item from the prior verification) is closed: `usage.py::_parse_copilot_otel` was rewritten for the real flat span-per-line schema, `copilot-cli`'s spec was flipped back to `usage_capture="otel-jsonl"`, and `COPILOT_OTEL_FILE_EXPORTER_PATH` was wired into both reusable workflow YAML files — all confirmed present and correctly wired in this verification session, not merely claimed in 10-09-SUMMARY.md.

A subsequent code-review round (10-REVIEW.md) found two additional critical issues on top of 10-09's changes, both independently confirmed fixed in this session:
- **CR-02** (a malformed field partway through one OTEL span's attributes could corrupt the running total while the function still reported `estimated=False`, i.e. trustworthy real data) — fixed by parsing all four fields atomically per span before merging into totals. Reproduced the exact exploit scenario from the review against the live code: confirmed it now returns `None` instead of a corrupted result.
- **CR-01** (the fix's premise was diagnosed against a locally installed `gh copilot` v1.0.67, but CI still pinned 1.0.61 — the exact version a *prior* gap-closure round had concluded OTEL export was "inert" on) — fixed by bumping the CI pin to 1.0.67 and updating all cross-referencing docs/tests/scripts to state support plainly rather than hedging. Confirmed all three sources (install script, docs table, test constant) now agree on `1.0.67`.

Both warning-level findings (WR-01, WR-02) were resolved as byproducts of the CR-01/CR-02 fixes, also confirmed. The one Info-level finding (IN-01) was explicitly and reasonably deferred per the review's declared scope.

Full local CI mirror (823 tests, ruff, ruff format, actionlint, zizmor) is green, matching the 10-REVIEW-FIX.md claim — independently re-run and confirmed in this session, not trusted from the report.

**Status remains `human_needed`, not `passed`,** per the verification gate rule (Step 9, rule 2): an outstanding human-verification item takes priority over a clean truths/artifacts/links table, even when the score is 19/19 and every code-level gap is closed. The one remaining item — a live GitHub Actions run with a real `COPILOT_GITHUB_TOKEN` confirming `estimated=False` end-to-end against the actual Copilot CLI subprocess — genuinely cannot be performed from this environment. This is not a code deficiency; it is the honest, correctly-scoped boundary of what static/local verification can prove for a live external-CLI integration. All prerequisites for that live check to succeed (correct parser schema, corruption-safe parsing, matching CI-pinned CLI version, wired env var in both workflows) are now confirmed present in the codebase.

All 6 requirement IDs (ENGN-10, WKFL-05, PERF-03, ENGN-08, ENGN-09, OUTP-05) are satisfied with codebase evidence. No regressions detected in the 14 previously-VERIFIED truths from the prior verification round — full 823-test suite green (up from 795, reflecting the 10-09 + review-fix additions), all gap-closure-relevant suites individually green, and a clean full CI mirror.

---

_Verified: 2026-07-01T19:30:00Z_
_Verifier: Claude (gsd-verifier)_
