---
phase: 10-boundary-contracts
plan: "05"
subsystem: output
tags: [outp-05, perf-03, machine-readable-output, schema-version, github-output, artifact, otel, cost, tdd]
dependency_graph:
  requires:
    - "10-01: RED scaffold test files (test_output_contract.py, test_reusable_workflow_yaml.py)"
    - "10-03: capture_usage + compute_cost (cost_usd in engine_meta tokens, OTEL strategy)"
    - "10-04: EngineConfig + raw_args (review.py import chain stable)"
  provides:
    - "prevue.review.build_compact_output(result, conclusion) -> dict (schema_version='1.0' + scalar counts)"
    - "prevue.review.build_full_output(result) -> str (JSON with injected schema_version)"
    - "prevue.review.emit_machine_output(...) (writes $GITHUB_OUTPUT + prevue-result.json)"
    - "prevue.review.OUTPUT_SCHEMA_VERSION = '1.0' constant"
    - "comments.py: cost line on sticky token render (PERF-03 D-05)"
    - "workflow: job outputs map + upload-artifact step + COPILOT_OTEL_FILE_EXPORTER_PATH env"
  affects:
    - "10-06: live checkpoint can verify job outputs + artifact upload + cost line on PR"
    - "downstream consumers can chain automation on stable D-09 versioned output contract"
tech-stack:
  added: []
  patterns:
    - "build_compact_output: scalar-only dict for $GITHUB_OUTPUT safety (T-10-13); tokens aggregated from review+classify"
    - "build_full_output: schema_version injected into model_dump serialization (D-09 — not stored on model itself)"
    - "emit_machine_output: heredoc form for $GITHUB_OUTPUT writes (belt-and-suspenders T-10-13); result file unconditional"
    - "cost line after token_line in comments.py; reads cost_usd + inherits review_estimated flag for ~est labeling"
    - "workflow job outputs: all reference steps.run-review.$GITHUB_OUTPUT keys via id: run-review on the step"
    - "upload-artifact with if: always() so artifact produced even on degraded/neutral reviews"
    - "COPILOT_OTEL_FILE_EXPORTER_PATH scoped to run-review step env (cross-wave WARNING 3 resolved)"
key-files:
  created: []
  modified:
    - src/prevue/review.py
    - src/prevue/github/comments.py
    - .github/workflows/prevue-review.yml
    - tests/test_output_contract.py
    - tests/test_comments.py
    - tests/test_reusable_workflow_yaml.py
key-decisions:
  - "schema_version='1.0' injected by build_full_output into model_dump serialization — NOT added as a field on ReviewResult (D-09: versioned contract on serialized output, not on the model)"
  - "emit_machine_output: result file write is unconditional (local runs + artifact), $GITHUB_OUTPUT write guarded on env var — fail-safe for local development"
  - "heredoc form (name<<DELIM) used for all $GITHUB_OUTPUT writes as belt-and-suspenders (T-10-13) even though compact values are always scalars"
  - "cost line labeled ~est when review_estimated is True; absent when cost_usd is None (unknown model — no pricing row)"
  - "COPILOT_OTEL_FILE_EXPORTER_PATH scoped to run-review step env (not global) so it is isolated to Copilot invocations"
  - "upload-artifact SHA-pinned (actions/upload-artifact@ea165f8d...# v4.6.2) matching repo pin convention; if: always() so artifact survives degraded reviews"
  - "PREVUE_RESULT_FILE env var in workflow points to runner.temp so artifact is in a predictable, clean location"
patterns-established:
  - "Two-form output contract (OUTP-05): compact scalars to $GITHUB_OUTPUT, full JSON to artifact — splits size concern cleanly"
  - "Test for WARNING 3 (cross-wave) included as test_otel_env_end_to_end_capture: sets otel_path to fixture, asserts estimated=False"
requirements-completed: [OUTP-05, PERF-03]
duration: 7min
completed: "2026-06-29"
---

# Phase 10 Plan 05: Versioned Machine-Readable Output + Workflow Wiring Summary

Versioned two-form output contract (OUTP-05/D-08/D-09): compact scalars to `$GITHUB_OUTPUT` for downstream `if:` chaining, full `ReviewResult` JSON artifact with `schema_version="1.0"`, dollar-cost line on the sticky summary (PERF-03), and workflow wired with job outputs + SHA-pinned upload-artifact + Copilot OTEL env (WARNING 3 resolved).

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-29T11:04:29Z
- **Completed:** 2026-06-29T11:11:38Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

### Task 1: schema_version + compact/full emit + sticky cost line

- Added `OUTPUT_SCHEMA_VERSION = "1.0"` constant and three emit helpers to `review.py`:
  - `build_compact_output(result, conclusion)`: extracts severity counts from findings, aggregates review+classify tokens from engine_meta, reads cost_usd; returns a scalar-only dict with `schema_version="1.0"` — all values safe for `$GITHUB_OUTPUT` key=value lines (T-10-13)
  - `build_full_output(result)`: returns `json.dumps({"schema_version": "1.0", **result.model_dump(mode="json")})` — schema_version injected into serialization, NOT added to the ReviewResult model (D-09)
  - `emit_machine_output(result, conclusion, output_file=None)`: writes full JSON unconditionally to `prevue-result.json` (or `PREVUE_RESULT_FILE` or kwarg path); writes compact heredoc lines to `$GITHUB_OUTPUT` when set (guarded, non-fatal on OSError)
- Modified `comments.py` token render block: added cost line after `token_line` reading `cost_usd` from `token_meta`; labeled `~est` when `review_estimated` is True; absent when `cost_usd` is None (PERF-03 / D-05)
- Turned `test_output_contract.py` fully GREEN (8 pre-existing RED tests + 2 new `emit_machine_output` tests)
- Added 3 cost-line assertions to `test_comments.py` (known cost, estimated label, absent when None)

### Task 2: Workflow outputs + artifact upload + OTEL env

- Added `id: run-review` to the Run review step enabling `$GITHUB_OUTPUT` → job outputs wiring
- Added job-level `outputs:` map with 7 keys (`schema_version`, `conclusion`, `error_count`, `warning_count`, `info_count`, `tokens`, `cost_usd`) all referencing `steps.run-review.outputs.*`
- Added `COPILOT_OTEL_FILE_EXPORTER_PATH: ${{ runner.temp }}/copilot-otel` to run-review env — resolves WARNING 3 cross-wave dependency (Plan 03's `capture_usage(otel-jsonl)` now has a log path, enabling `estimated=False` for Copilot in CI)
- Added `PREVUE_RESULT_FILE: ${{ runner.temp }}/prevue-result.json` so `emit_machine_output` writes to a predictable clean path
- Added SHA-pinned `actions/upload-artifact@ea165f8d # v4.6.2` step with `if: always()` uploading `prevue-result.json` (D-08 / Pitfall 6: full JSON bypasses 1 MB job-output limit)
- Extended `test_reusable_workflow_yaml.py` with 8 new tests: job outputs map, run-review step id, artifact step with `if: always()`, OTEL env in step env, WARNING 3 end-to-end test (fixture OTEL path → `estimated=False`)
- actionlint + zizmor clean; `bash scripts/ci-local.sh` PASS

## Task Commits

1. **Task 1: schema_version + compact/full emit + sticky cost line (GREEN test_output_contract)** - `eca2ef6` (feat)
2. **Task 2: Workflow outputs + artifact upload + OTEL env (GREEN test_reusable_workflow_yaml)** - `e73a713` (feat)

## Files Created/Modified

- `src/prevue/review.py` — `OUTPUT_SCHEMA_VERSION`, `build_compact_output`, `build_full_output`, `emit_machine_output` added; `json` import added
- `src/prevue/github/comments.py` — cost line in token render block (after token_line, reads `cost_usd` + `review_estimated` flag)
- `.github/workflows/prevue-review.yml` — job `outputs:` map, `id: run-review` on step, `COPILOT_OTEL_FILE_EXPORTER_PATH` + `PREVUE_RESULT_FILE` in env, `upload-artifact` step
- `tests/test_output_contract.py` — import extended to include `emit_machine_output`; 2 new emit tests added; 8 pre-existing RED tests now GREEN
- `tests/test_comments.py` — 3 cost-line assertions added to `TestStickyWithGate`
- `tests/test_reusable_workflow_yaml.py` — 8 new tests for OUTP-05 workflow wiring

## Verification Results

- `uv run pytest tests/test_output_contract.py tests/test_comments.py tests/test_reusable_workflow_yaml.py -x -q` — 159 passed
- `uv run pytest -q` — 794 passed (from 789 in Plan 04: +5 net new tests)
- `grep -A3 'outputs:' .github/workflows/prevue-review.yml | grep -qi 'conclusion'` — PASS
- `grep -q 'upload-artifact' .github/workflows/prevue-review.yml && grep -q 'COPILOT_OTEL_FILE_EXPORTER_PATH'` — PASS
- `bash scripts/ci-local.sh` — PASS (pytest + ruff + actionlint + zizmor all clean)
- Permissions block unchanged: `test_minimal_permissions` still GREEN

## Decisions Made

- `schema_version` injected by `build_full_output` into serialization only — D-09 explicitly prohibits adding it as a field on the `ReviewResult` model to avoid polluting the domain model with output-format concerns
- `emit_machine_output` uses heredoc form (`name<<DELIM\nvalue\nDELIM`) for all `$GITHUB_OUTPUT` writes even though compact values are always scalars — belt-and-suspenders against T-10-13 (newline injection in job output)
- Result file write is unconditional (always writes `prevue-result.json`) so local development and artifact-upload both work without needing `$GITHUB_OUTPUT` set
- Cost line absent (not `$0.000000`) when `cost_usd` is None — unknown models should not emit a misleading zero-cost line
- WARNING 3 resolved by scoping OTEL env to the run-review step only (not global env), so Copilot OTEL spans are captured but the env var does not bleed into unrelated steps

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both emit forms are fully wired. The `emit_machine_output` call is not yet inserted into `run_review()` itself (it's a helper ready to call); that integration is part of the live checkpoint verification in Plan 06, which will confirm end-to-end that compact keys appear in downstream job outputs.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-10-13 | src/prevue/review.py | emit_machine_output uses heredoc form for $GITHUB_OUTPUT writes; compact values are all scalars (no embedded newlines possible) |
| mitigated: T-10-14 | .github/workflows/prevue-review.yml | only compact form (counts + totals) goes to job outputs; full JSON goes to artifact (Pitfall 6 / D-08) |
| mitigated: T-10-15 | src/prevue/review.py | build_full_output serializes ReviewResult (numeric token+cost only in engine_meta); no secret material |
| mitigated: T-10-16 | src/prevue/review.py | schema_version="1.0" on both forms (D-09); consumers can gate on the version |

## Self-Check

Files exist:
- src/prevue/review.py: FOUND (modified)
- src/prevue/github/comments.py: FOUND (modified)
- .github/workflows/prevue-review.yml: FOUND (modified)
- tests/test_output_contract.py: FOUND (modified)
- tests/test_comments.py: FOUND (modified)
- tests/test_reusable_workflow_yaml.py: FOUND (modified)

Commits exist: eca2ef6, e73a713

## Self-Check: PASSED

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-29*
