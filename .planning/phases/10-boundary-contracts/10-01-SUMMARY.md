---
phase: 10-boundary-contracts
plan: "01"
subsystem: testing
tags: [pytest, tdd, usage-capture, pricing, config-precedence, raw-args, model-roles, output-contract]

requires:
  - phase: 09-classification-skill-loading-multi-call-review
    provides: merge_findings fingerprint dedup (used in model-roles test to assert D-13 preservation)

provides:
  - "6 RED test files pinning Phase 10 behavioral contracts (PERF-03, WKFL-05, ENGN-08, ENGN-09, OUTP-05)"
  - "5 small fixture files (pricing + usage) so contract tests do not load the 500 KB production snapshot"
  - "Executable automated commands for Plans 03, 04, 05 to verify GREEN status"

affects:
  - 10-boundary-contracts-03 (usage capture + pricing implementation turns these RED tests GREEN)
  - 10-boundary-contracts-04 (EngineConfig + _resolve_model + _resolve_engine_models turns RED tests GREEN)
  - 10-boundary-contracts-05 (build_compact_output + build_full_output turns RED tests GREEN)

tech-stack:
  added: []
  patterns:
    - "try/except import + _require_import() pattern for RED test files that must collect but fail on missing modules"
    - "Small fixture files (pricing/usage) under tests/fixtures/ mirroring LiteLLM field names"

key-files:
  created:
    - tests/test_usage_capture.py
    - tests/test_pricing.py
    - tests/test_config_precedence.py
    - tests/test_raw_args.py
    - tests/test_model_roles.py
    - tests/test_output_contract.py
    - tests/fixtures/pricing/sample_prices.json
    - tests/fixtures/usage/claude_envelope.json
    - tests/fixtures/usage/cursor_envelope.json
    - tests/fixtures/usage/copilot_otel.jsonl
    - tests/fixtures/usage/antigravity_text.txt
  modified: []

key-decisions:
  - "RED pattern via try/except + pytest.fail() rather than pytest.importorskip — importorskip skips the whole module (0 tests collected), try/except allows collection with explicit FAIL on missing import"
  - "Fixture design: claude_envelope.json mirrors Claude --output-format json with usage.{input_tokens,output_tokens,cache_read_input_tokens,cache_creation_input_tokens} + total_cost_usd; copilot_otel.jsonl has 2 lines summing to input=2100 for deterministic assertions"
  - "test_model_roles.py: merge_findings tests kept GREEN (assert existing behavior unchanged per D-13); per-role resolver tests are RED pending Plan 04"

patterns-established:
  - "Wave-0 RED scaffold pattern: import via try/except, define _require_import(), call at top of each test — collection succeeds, running fails clearly on missing module"

requirements-completed: [WKFL-05, PERF-03, ENGN-08, ENGN-09, OUTP-05]

duration: 8min
completed: 2026-06-29
---

# Phase 10 Plan 01: RED Scaffold for Boundary Contracts Summary

**6 new test files + 5 fixtures pin every Phase 10 behavioral contract (PERF-03 / WKFL-05 / ENGN-08 / ENGN-09 / OUTP-05) as executable RED assertions before any production code exists**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-29T10:04:43Z
- **Completed:** 2026-06-29T10:13:26Z
- **Tasks:** 3
- **Files modified:** 11 (6 test files + 5 fixture files)

## Accomplishments

- Created 5 usage + pricing fixtures (small, not the 500 KB production snapshot) mirroring LiteLLM field names and per-engine OTEL/stdout-json/plain-text output shapes
- Created 6 RED test files (49 total test cases) that collect under pytest and fail clearly on missing production modules, locking every Phase 10 contract before implementation begins
- Verified merge_findings determinism (D-13) is preserved in test_model_roles.py via GREEN assertions against existing multicall.py code

## Task Commits

1. **Task 1: Usage-capture + pricing fixtures and RED tests (PERF-03)** - `334681f` (test)
2. **Task 2: Config precedence + raw_args + model-roles RED tests (WKFL-05 / ENGN-08 / ENGN-09)** - `a0595e2` (test)
3. **Task 3: Output contract RED test (OUTP-05)** - `a9ad1e6` (test)

## Files Created/Modified

- `tests/fixtures/pricing/sample_prices.json` - 4-model pricing fixture (claude-3-5-sonnet, gpt-4o, gpt-4o-tiered, gemini-1.5-flash) with LiteLLM field names including cache fields
- `tests/fixtures/usage/claude_envelope.json` - Claude stdout-json envelope with usage + total_cost_usd
- `tests/fixtures/usage/cursor_envelope.json` - Cursor result envelope with NO token fields (confirms estimate path)
- `tests/fixtures/usage/copilot_otel.jsonl` - 2 JSONL lines; tokens sum to input=2100, output=300, cache_read=1050
- `tests/fixtures/usage/antigravity_text.txt` - Plain review text (no JSON, triggers estimate fallback)
- `tests/test_usage_capture.py` - 6 RED tests: capture_usage per-strategy (stdout-json/otel-jsonl/none), fixtures linked
- `tests/test_pricing.py` - 8 RED tests: cache-aware formula, unknown-model→None, D-06c override precedence, prefer-total_cost_usd
- `tests/test_config_precedence.py` - 12 tests: 6 GREEN (engine ladder via existing _resolve_engine), 6 RED (model/fallback-model via missing _resolve_model/_resolve_engine_models)
- `tests/test_raw_args.py` - 7 tests: EngineConfig list-form + string-rejection RED, sentinel/GITHUB_ACTIONS Pitfall 4 GREEN
- `tests/test_model_roles.py` - 8 tests: 5 RED (per-role resolver), 3 GREEN (merge_findings determinism unchanged)
- `tests/test_output_contract.py` - 8 RED tests: compact schema_version, full JSON round-trip, GITHUB_OUTPUT newline safety

## Decisions Made

- **RED pattern**: Used `try/except ImportError` + `_require_import()` helper rather than `pytest.importorskip` — the latter skips the entire module at collection time (0 tests collected), defeating the "collect but RED" requirement. try/except allows collection while test bodies explicitly fail with a clear message.
- **Fixture design**: claude_envelope.json matches Claude --output-format json envelope exactly (usage fields + total_cost_usd + result text). copilot_otel.jsonl has 2 lines with deterministic sums for assert-exact-value tests.
- **merge_findings tests**: Kept GREEN in test_model_roles.py to assert D-13 (merge stays deterministic-fingerprint, not LLM-driven). These test existing multicall.py code and must remain passing through all later plans.

## Deviations from Plan

None — plan executed exactly as written. The only implementation decision was the RED pattern (try/except vs importorskip), which is explicitly authorized by the plan's action block ("use `pytest.importorskip` or a module-level import that fails so the file collects but tests are RED").

## Issues Encountered

Minor: Initial approach using `pytest.importorskip` at module level caused 0 tests to collect (the module was marked as skipped rather than collected with failing tests). Switched to try/except + explicit `pytest.fail()` per-test, which satisfies the "collect + RED" requirement. Resolved in Task 1 before commit.

## Known Stubs

None — this plan creates only test scaffolds and fixtures. No production code with stubs.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns. All changes are test files and data fixtures under `tests/`.

## Next Phase Readiness

- All 6 test files collect and are RED — ready to serve as acceptance gates for Plans 03, 04, and 05
- Fixture files are small and deterministic — Plans 03/04/05 can assert exact token counts without loading the 500 KB production snapshot
- Plan 02 (ENGN-10 adapter consolidation) can proceed — it has no dependency on this plan's RED tests

## Self-Check

Files exist:
- tests/test_usage_capture.py: FOUND
- tests/test_pricing.py: FOUND
- tests/test_config_precedence.py: FOUND
- tests/test_raw_args.py: FOUND
- tests/test_model_roles.py: FOUND
- tests/test_output_contract.py: FOUND
- tests/fixtures/pricing/sample_prices.json: FOUND
- tests/fixtures/usage/claude_envelope.json: FOUND
- tests/fixtures/usage/cursor_envelope.json: FOUND
- tests/fixtures/usage/copilot_otel.jsonl: FOUND
- tests/fixtures/usage/antigravity_text.txt: FOUND

Commits exist: 334681f, a0595e2, a9ad1e6

## Self-Check: PASSED

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-29*
