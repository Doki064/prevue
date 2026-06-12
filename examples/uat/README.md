# Phase 2 UAT branch fixtures

Reusable upstream test branch: `test/uat-phase-02` (PR against phase 2 base).

Swap fixture directories per test; push to re-trigger Prevue Review.

| Test | Fixture path | Expected behavior |
|------|--------------|-------------------|
| 1 | `frontend/*.tsx` only | `frontend` label, `**/*.tsx` |
| 2 | `frontend/*.tsx` + `infra/*.tf` | `frontend` + `infra` union |
| 3 | `general-only/*` (no prevue.yml override) | `general` only |
| 4 | `lockfile-only/package-lock.json` only | D-10 skip, no engine |
| 6 | `general-only/*` + `.github/prevue.yml` | `data` label via consumer override; `fixture.meta` filtered |

Remove `examples/uat/` and `.github/prevue.yml` after UAT completes.
