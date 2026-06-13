# Prevue UAT Fixtures

Branch-scoped fixtures for live `/gsd-verify-work` runs. Each `uat/phase-NN` branch targets the matching `gsd/phase-NN-*` integration branch.

## Phase 5 — Multi-Engine Adapter Support

**Branch:** `uat/phase-05` → base `gsd/phase-05-multi-engine-adapter-support`

**Fixture:** `uat/phase-05/sample.py` — small Python diff with an intentional missing-validation pattern for engines to review.

**Active test:** see `uat/phase-05/ACTIVE` (currently `cursor-cli` — Test 2).

### Prerequisites (repo Settings → Secrets and variables → Actions)

| Name | Type | Required for |
|------|------|--------------|
| `COPILOT_GITHUB_TOKEN` | Secret | default engine (already configured) |
| `ANTHROPIC_API_KEY` | Secret | Test 1 — Claude Code |
| `CURSOR_API_KEY` | Secret | Test 2 — Cursor |

### Engine selection

Priority order:

1. **`uat/phase-05/ACTIVE`** on the UAT PR head (read via GitHub API — no repo variable needed)
2. Repository variable `PREVUE_ENGINE` (Settings → Variables)
3. Default `copilot-cli`

Edit `uat/phase-05/ACTIVE` and push to switch engines:

```
cursor-cli        # Test 2 (current)
typo-engine       # Test 3 (fail-closed)
```

After each test, re-run the **Prevue Review** workflow on the UAT PR (Actions → workflow run → Re-run jobs), or push an empty commit:

```bash
git commit --allow-empty -m "chore(uat): re-trigger review" && git push
```

### Test checklist

| # | Set engine | Pass criteria |
|---|------------|---------------|
| 1 | `claude-code-cli` | *(skipped — Pro sub, no API key)* |
| 2 | `cursor-cli` | Sticky + check; `cursor-agent` from official installer; completes within budget; no repo file writes |
| 3 | `typo-engine` | Job fails; logs show `UnknownEngineError` naming bad value and listing valid engines |

Report results in chat via `/gsd-verify-work 5` (reply `pass` or describe issues per test).
