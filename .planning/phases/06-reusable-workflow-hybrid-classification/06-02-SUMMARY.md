---
phase: 06-reusable-workflow-hybrid-classification
plan: 02
subsystem: infra
tags: [github-actions, workflow_call, reusable-workflow, SECR-01, consumer-setup]

requires:
  - phase: 06-reusable-workflow-hybrid-classification
    plan: 01
    provides: Wave 0 RED scaffolds, PrevueConfig loader, test_reusable_workflow_yaml.py
provides:
  - Shippable on:workflow_call prevue-review.yml reusable workflow
  - Thin pull_request review.yml dogfood caller
  - docs/consumer-setup.md with caller snippet, permissions, skip≠auto-merge
  - Green static YAML guards for both workflow files
affects:
  - 06-03-llm-fallback
  - 06-04-skip-pipeline
  - consumer adoption

tech-stack:
  added: []
  patterns:
    - "Reusable workflow self-checkouts Prevue at pinned v0.6.0 + consumer at base.sha"
    - "Named per-engine secrets required:false; NO secrets: inherit"
    - "Thin caller grants permissions; job body lives in prevue-review.yml"

key-files:
  created:
    - .github/workflows/prevue-review.yml
    - docs/consumer-setup.md
  modified:
    - .github/workflows/review.yml
    - tests/test_reusable_workflow_yaml.py
    - tests/test_workflow_yaml.py

key-decisions:
  - "Prevue self-checkout hardcoded to v0.6.0 (bump at each release per Pitfall 1)"
  - "prevue-ref input is test-only override for D-03 version-skew guard"
  - "review.yml passes engine via vars.PREVUE_ENGINE || copilot-cli to reusable workflow"

patterns-established:
  - "Dogfood: review.yml is uses: ./.github/workflows/prevue-review.yml only"
  - "PREVUE_CONFIG_PATH absolute: github.workspace/consumer/{config-path}"

requirements-completed: [WKFL-01, WKFL-02, WKFL-04]

duration: 1min
completed: 2026-06-13
---

# Phase 6 Plan 2: Reusable Workflow Summary

**Shippable workflow_call surface with pinned v0.6.0 self-checkout, thin dogfood caller, and consumer-setup docs under minimal permissions**

## Performance

- **Duration:** 1 min
- **Started:** 2026-06-13T19:05:06Z
- **Completed:** 2026-06-13T19:06:09Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `.github/workflows/prevue-review.yml` — `workflow_call` with named `required:false` secrets, draft `if:`, two SHA-pinned checkouts (Prevue `v0.6.0` + consumer `base.sha`), single `uv run prevue review`
- `.github/workflows/review.yml` rewritten as thin caller using local reusable workflow with named secrets (no `secrets: inherit`)
- `docs/consumer-setup.md` — minimal `@v0.6.0` caller snippet, permissions table, per-engine secret mapping, skip≠auto-merge note
- All 27 workflow YAML static guards green (`test_reusable_workflow_yaml.py` + `test_workflow_yaml.py`)

## Release Tag Note (Pitfall 1)

The Prevue framework self-checkout uses hardcoded ref **`v0.6.0`**. This must be bumped to match each release tag before publishing — both in `prevue-review.yml` and `docs/consumer-setup.md`. The `prevue-ref` input exists only for test overrides (D-03).

## Task Commits

1. **Task 1: Create prevue-review.yml reusable workflow** - `60a9f88` (feat)
2. **Task 2: Rewrite review.yml thin caller + docs** - `47c6772` (feat)

## Files Created/Modified

- `.github/workflows/prevue-review.yml` — shippable reusable workflow (WKFL-01/02/04, NOIS-01 draft skip)
- `.github/workflows/review.yml` — thin `uses:` dogfood caller (D-01)
- `docs/consumer-setup.md` — consumer adoption guide with permissions + skip≠auto-merge (D-14)
- `tests/test_reusable_workflow_yaml.py` — green guards; PyYAML `on`→True fix
- `tests/test_workflow_yaml.py` — retargeted guards to reusable workflow + caller assertions

## Decisions Made

- Hardcoded `v0.6.0` as placeholder release tag (documented for release-time bump)
- Engine install/credentials blocks live in reusable workflow only; caller passes `vars.PREVUE_ENGINE` via `with.engine`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PyYAML `on` key parsing in secrets test**
- **Found during:** Task 1
- **Issue:** `test_named_secrets_not_required` used `wf.get("on")` but PyYAML parses `on:` as boolean `True`
- **Fix:** Use `wf.get("on") or wf.get(True)` pattern (consistent with other tests)
- **Files modified:** `tests/test_reusable_workflow_yaml.py`
- **Committed in:** `60a9f88`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for green test suite. No scope creep.

## Issues Encountered

None beyond auto-fixed deviation above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plans 06-03/06-04 can proceed; reusable workflow is the delivery surface for LLM fallback and skip pipeline
- Release process must bump `v0.6.0` in `prevue-review.yml` and `docs/consumer-setup.md` when tagging

## Self-Check: PASSED

- FOUND: .github/workflows/prevue-review.yml
- FOUND: .github/workflows/review.yml
- FOUND: docs/consumer-setup.md
- FOUND: tests/test_reusable_workflow_yaml.py
- FOUND: tests/test_workflow_yaml.py
- FOUND: 60a9f88
- FOUND: 47c6772

---
*Phase: 06-reusable-workflow-hybrid-classification*
*Completed: 2026-06-13*
