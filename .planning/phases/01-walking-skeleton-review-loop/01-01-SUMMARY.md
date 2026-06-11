---
phase: 01-walking-skeleton-review-loop
plan: 01
subsystem: infra
tags: [copilot-cli, github-actions, spike, d-12]

requires: []
provides:
  - D-12 live spike findings (A1 zero-tool prose, A2 PAT prefix, A3 install timing)
  - throwaway spike-copilot.yml workflow (to delete after Plan 07 E2E)
affects: [01-05, 01-07]

tech-stack:
  added: ["@github/copilot@1.0.60"]
  patterns:
    - "Zero-tool headless Copilot: copilot -p ... -s --no-ask-user with no --allow-tool"
    - "Fine-grained PAT auth guard: github_pat_ prefix (A2 confirmed)"

key-files:
  created:
    - .github/workflows/spike-copilot.yml
  modified: []

key-decisions:
  - "A1 YES: zero-tool prose call returns usable output — Plan 05 keeps no --allow-tool posture"
  - "A2 confirmed github_pat_ prefix — adapter auth guard locks to github_pat_"
  - "A3 install 12s wall time — well within 300s call budget; no npm cache mitigation needed"

patterns-established:
  - "Spike-before-adapter: validate Copilot CLI on clean runner before writing adapter code"

requirements-completed: [ENGN-02]

duration: 20min
completed: 2026-06-12
---

# Phase 01 Plan 01: Copilot CLI Spike (D-12) Summary

**Live Actions spike confirms zero-tool Copilot prose works with github_pat_ fine-grained PAT; 12s npm install on ubuntu-latest**

## Performance

- **Duration:** ~20 min (Task 1 automated + Task 2 human verify)
- **Started:** 2026-06-12
- **Completed:** 2026-06-12
- **Tasks:** 2
- **Files modified:** 1

## Spike Findings (D-12)

| Assumption | Finding | Impact on Plan 05 |
|------------|---------|-------------------|
| **A1** Zero-tool prose | **YES** — bare `copilot -p "Reply with exactly: PREVUE_SPIKE_OK" -s --no-ask-user` returned usable prose | Keep zero `--allow-tool` flags; diff inline in prompt |
| **A2** PAT prefix | **`github_pat_`** confirmed by diagnostic step | Auth guard rejects missing token and `ghp_` classic PATs |
| **A3** Timing | **Install wall time: 12s** on ubuntu-latest; call well within 300s budget | No npm global cache workaround needed |
| **Auth notes** | No entitlement or token-shadowing errors observed | Pitfall 7 mitigations sufficient |

## Accomplishments

- Throwaway `workflow_dispatch` spike workflow authored and run on real runner
- D-12 open questions 1–3 resolved with live evidence before adapter code
- Plan 05 unblocked with confirmed zero-tool + PAT prefix design inputs

## Task Commits

1. **Task 1: Author the throwaway Copilot CLI spike workflow** - `c84b8d0` (feat)
2. **Task 2: Run the spike and record live findings** - human-verify checkpoint (this summary)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `.github/workflows/spike-copilot.yml` — D-12 throwaway spike (delete after Plan 07 E2E)

## Decisions Made

- Proceed with zero-tool adapter design (no `--allow-tool=read` fallback needed)
- Lock auth guard to `github_pat_` prefix per live confirmation

## Deviations from Plan

None - plan executed as specified.

## Issues Encountered

None — spike completed on first run.

## Next Phase Readiness

- Plan 05 (CopilotCliAdapter) can implement with confirmed A1/A2/A3
- Delete `spike-copilot.yml` after Plan 07 live E2E sign-off

---
*Phase: 01-walking-skeleton-review-loop*
*Completed: 2026-06-12*
