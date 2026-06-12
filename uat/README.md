# Phase 3 UAT branch

Branch `uat/phase-03` holds **one active scenario** under `uat/active/` for live Prevue review runs.

**Important:** Scenario templates live on the base branch under `uat/scenarios/`. The UAT PR diff must contain **only** `uat/active/*` — never commit all scenarios at once or classification will see multiple domains.

## Setup

1. Open (or update) a PR: `uat/phase-03` → `gsd/phase-03-selective-skill-loading`
2. Wait for **Prevue Review** workflow on the PR
3. Inspect sticky comment **Metadata** section (`Labels:`, `Bundles:`, `Skills:`)

## Switch scenario

```bash
./uat/switch-scenario.sh <scenario-id>
git add uat/active uat/ACTIVE
git commit -m "uat(phase-03): switch to scenario <scenario-id>"
git push
```

Each push re-triggers the review workflow with the new diff.

## Scenarios

| ID | UAT tests | Active files | Expected Metadata |
|----|-----------|--------------|-------------------|
| `01-backend-only` | 1, 4, 9 | `uat/active/sample.py` | Labels: backend; bundles backend (+ security skills) |
| `02-frontend-only` | contrast | `uat/active/Widget.tsx` | Labels: frontend only |
| `03-infra-only` | contrast | `uat/active/main.tf` | Labels: infra only |
| `04-filtered-only` | 5 skip | `uat/active/uv.lock` | Skip note — filtered |

Tests 2, 3, 6, 7, 8 are local (`pytest`, file read) — no branch update.
