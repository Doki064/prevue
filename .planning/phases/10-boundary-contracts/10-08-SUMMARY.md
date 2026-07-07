---
phase: 10-boundary-contracts
plan: "08"
subsystem: infra
tags: [github-actions, workflow_call, copilot-cli, otel, config-precedence, reusable-workflow]

# Dependency graph
requires:
  - phase: 10-04
    provides: per-role model resolution (ENGN-09/D-11) and resolve_review_model() env-wins logic
  - phase: 10-05
    provides: OUTP-05 job-level outputs block, emit_machine_output, artifact upload
  - phase: 10-07
    provides: cursor-cli/antigravity-cli usage_capture="none" honest-estimate precedent
provides:
  - Copilot CLI reports honest ~est token estimates (usage_capture="none") instead of a
    non-functional OTEL real-capture claim
  - A working `model` workflow_call input that reaches PREVUE_MODEL end-to-end
  - A working on.workflow_call.outputs block so callers can read needs.<job>.outputs.*
affects: [phase-11-skills-as-pinned-external-repo, phase-12-cross-file-dependency-context]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "workflow_call.outputs must sibling-mirror jobs.<job>.outputs 1:1 — job-level outputs alone never cross the workflow_call boundary"
    - "Empty-string env var overrides are safe when the consuming Python code uses `env_val or fallback` (falsy-string) rather than presence/`in os.environ` checks"

key-files:
  created: []
  modified:
    - src/prevue/engines/spec.py
    - src/prevue/engines/cli_adapter.py
    - .github/workflows/prevue-review.yml
    - .github/workflows/prevue-command-run.yml
    - tests/test_reusable_workflow_yaml.py
    - docs/configuration.md

key-decisions:
  - "copilot-cli usage_capture flipped from otel-jsonl to none — no CI-viable OTEL export mechanism exists on @github/copilot@1.0.61 per live sandbox verification and official docs/issue-tracker check"
  - "usage.py's otel-jsonl parser and flow.py's dispatch path left untouched (valid, tested, just unreached for Copilot) so no regression risk and no throwaway work if GitHub ships real OTEL later"
  - "model workflow_call input added with default \"\" (not a real model name) — verified against review.py's `env_model or ...` resolution chains that an empty-string PREVUE_MODEL falls through to COPILOT_MODEL/yml/None exactly like an unset var, so no copy-paste risk from the engine input's non-empty default"
  - "on.workflow_call.outputs added as a literal sibling block to jobs.review.outputs, same 7 keys same order, backed by a per-key-drift regression test rather than a superset check"

patterns-established:
  - "Gap-closure regression tests assert exact key-set equality between two YAML blocks that must stay in sync, not just presence of expected keys — catches silent drift"

requirements-completed: [PERF-03, WKFL-05, OUTP-05]

# Metrics
duration: 5min
completed: 2026-07-01
---

# Phase 10 Plan 08: Boundary-Contract Gap Closure (Copilot OTEL, Model Input, Workflow Outputs) Summary

**Closed three live-UAT-confirmed boundary breaks in the reusable workflow's public YAML surface — Copilot now reports honest token estimates, a `model` workflow input actually reaches the engine, and `on.workflow_call.outputs` finally lets callers read `needs.<job>.outputs.*`.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-01T11:31:00Z
- **Completed:** 2026-07-01T11:33:37Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Copilot CLI's `CliEngineSpec.usage_capture` flipped from `"otel-jsonl"` to `"none"`, matching the cursor-cli/antigravity-cli honest-estimate precedent, with root-cause documentation citing the live sandbox check and official docs/issue-tracker confirmation
- Both workflow YAML files (`prevue-review.yml`, `prevue-command-run.yml`) had the now-inert `COPILOT_OTEL_FILE_EXPORTER_PATH` env line removed, along with the stale "WARNING 3" comment block and its matching wiring-assertion test
- `on.workflow_call.inputs.model` added and threaded into `PREVUE_MODEL` in the Run review step, closing the previously-unreachable "workflow input" tier of the documented `CONFIG_PRECEDENCE` ladder
- `on.workflow_call.outputs` block added, re-mapping all 7 `jobs.review.outputs` keys 1:1, backed by a new TDD-driven regression test (`test_workflow_call_outputs_block_declared`) that fails on missing block OR key drift between the two declarations
- `docs/configuration.md` updated: `model` input row added to the Inputs table, "Review model" paragraph now recommends the workflow input as the primary override path

## Task Commits

Each task was committed atomically:

1. **Task 1: Flip Copilot to honest usage_capture="none" (Gap 1)** - `a9bb583` (fix)
2. **Task 2: Thread workflow-input model override into PREVUE_MODEL (Gap 2)** - `cb78e2a` (feat)
3. **Task 3: Add workflow_call.outputs re-mapping (Gap 3, TDD)**
   - RED: `4048c4d` (test) — `test_workflow_call_outputs_block_declared` added and confirmed failing against the pre-fix file
   - GREEN: `e205b2d` (feat) — `on.workflow_call.outputs` block added, test passes

**Plan metadata:** (this commit)

## Files Created/Modified
- `src/prevue/engines/spec.py` - copilot-cli `CliEngineSpec.usage_capture` flipped `"otel-jsonl"` → `"none"`; root-cause comment added citing live sandbox + official docs verification
- `src/prevue/engines/cli_adapter.py` - stale comment referencing Copilot as the otel-jsonl example engine corrected (Rule 1: comment described now-false behavior)
- `.github/workflows/prevue-review.yml` - added `model` workflow_call input + `PREVUE_MODEL: ${{ inputs.model }}` env line; added `on.workflow_call.outputs` block (7 keys); removed `COPILOT_OTEL_FILE_EXPORTER_PATH` env line and its WARNING 3 comment
- `.github/workflows/prevue-command-run.yml` - removed `COPILOT_OTEL_FILE_EXPORTER_PATH` env line (parity fix)
- `tests/test_reusable_workflow_yaml.py` - removed stale `test_otel_env_set_in_run_review_step`; updated section header comment; added `test_workflow_call_outputs_block_declared` (RED→GREEN)
- `docs/configuration.md` - added `model` input row to the Inputs table; updated "Review model" paragraph to recommend the workflow input first

## Decisions Made
- **Copilot OTEL is unshippable today, not a Prevue bug**: verified via live sandbox (no `~/.copilot`, no OTEL directory ever created, zero OTEL mention in `copilot --help`) and cross-checked against official GitHub Copilot CLI docs and the `github/copilot-cli` repo's open issues (an "Enterprise OTel auth" feature request is open and unresolved). Left `usage.py`/`flow.py`'s `otel-jsonl` strategy code untouched since it remains valid, tested infrastructure that can be re-enabled if/when GitHub ships real OTEL export.
- **Empty-string `PREVUE_MODEL` is safe by construction**: read `src/prevue/review.py` (lines ~627, ~748, ~818) and `src/prevue/config.py::resolve_review_model` before choosing the YAML expression. All three call sites resolve the env value with a Python `or` chain (`env_model or review_model_from_config`), which treats an empty string as falsy and falls through — so the simpler `PREVUE_MODEL: ${{ inputs.model }}` (matching the plan's preferred simplification) is correct without needing a conditional expression, despite `model` being the first optional workflow input with an empty-string (not named) default.
- **workflow_call.outputs must be a literal sibling, not a derived reference**: GitHub Actions has no mechanism to auto-propagate `jobs.<job>.outputs` to callers; the fix requires manually duplicating the key list. The regression test asserts exact set equality between the two blocks (not "contains at least") specifically to catch the class of drift that caused this gap to ship silently in the first place.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected stale Copilot-as-otel-jsonl-example comment in cli_adapter.py**
- **Found during:** Task 1 (flipping copilot-cli's usage_capture)
- **Issue:** A comment at `src/prevue/engines/cli_adapter.py:192` described "otel-jsonl engines (copilot-cli)" as an example and referenced "WARNING 3 ... until Plan 05 wires it" — both statements became false the moment copilot-cli's spec flipped to `usage_capture="none"`. Not in the plan's explicit file list, but directly caused by Task 1's change and left uncorrected would mislead a future reader into thinking Copilot still uses the OTEL path.
- **Fix:** Rewrote the comment to state otel-jsonl remains valid, tested, but currently-unreached infrastructure, referencing the 10-08 gap closure and the `usage_capture="none"` fallback.
- **Files modified:** `src/prevue/engines/cli_adapter.py`
- **Verification:** Full test suite + `ci-local.sh` pass; no test asserted on this comment's prior wording.
- **Committed in:** `a9bb583` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — stale comment)
**Impact on plan:** Documentation-accuracy only; no behavior change beyond what Task 1 already specified. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. This closes gaps in a workflow YAML surface that consumers already reference; no new consumer-facing setup step is introduced (the new `model` input is optional with an inert default).

## Next Phase Readiness
- All 3 P0 gaps from 10-UAT.md's live sandbox verification are closed; this was the sole remaining incomplete plan in Phase 10 (Wave 4, depends_on 10-04/10-05/10-07, all already complete).
- Full local CI gate (`./scripts/ci-local.sh`: pytest 811 passed, ruff clean, actionlint clean, zizmor clean) passes on the modified workflow YAML and Python.
- Manual re-verification note (from the plan, not automated here): a live re-check against a real `Doki064/test-sandbox-repo` PR is recommended in the next `/gsd-uat-phase` pass, per 10-UAT.md's own follow-up note that this exact bug class ("job-level outputs declared but caller-facing block missing") is easy to reintroduce.
- Phase 10 (boundary-contracts) is now fully complete pending that live re-verification pass.

---
*Phase: 10-boundary-contracts*
*Completed: 2026-07-01*

## Self-Check: PASSED

All 6 claimed files verified present on disk; all 4 claimed commit hashes (`a9bb583`, `cb78e2a`, `4048c4d`, `e205b2d`) verified present in git log.
