---
phase: 10
slug: boundary-contracts
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-28
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `10-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.* + pytest-cov 7.* (verified: `pyproject.toml`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_engine_contract.py tests/test_config_precedence.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Phase gate** | `bash scripts/ci-local.sh` green (full suite + ruff) before `/gsd-verify-work` and before any push |
| **Estimated runtime** | ~30 seconds (quick); full suite + ci-local longer |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/<touched-area> -x -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** `bash scripts/ci-local.sh` must be green
- **Max feedback latency:** ~30 seconds (quick run)

---

## Per-Task Verification Map

> Populated during planning/Wave 0 once PLAN.md task IDs exist. Requirement → test
> seeds below come from research; map each to concrete task IDs after `/gsd-plan-phase`.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | ENGN-10 | — | spec generic passes contract suite; registry auto-populates | unit (parametrized) | `uv run pytest tests/test_engine_contract.py -x` | ✅ exists | ⬜ pending |
| TBD | 01 | 1 | ENGN-10 | — | per-engine AuthError types + argv shapes preserved | unit | `uv run pytest tests/test_engine_contract.py -x` | ✅ exists | ⬜ pending |
| TBD | 01 | 1 | ENGN-10 | — | `functional` flag replaces SKELETON_ENGINES; unknown engine fails closed | unit | `uv run pytest tests/test_registry.py -x` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | WKFL-05 | — | input > yml > default for engine, model (+fallback model) | unit (matrix) | `uv run pytest tests/test_config_precedence.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERF-03 | — | Claude stdout-json usage captured (real tokens, cost); `estimated:false` | unit | `uv run pytest tests/test_usage_capture.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERF-03 | — | Cursor/Antigravity → bytes/4 fallback, `estimated:true` | unit | `uv run pytest tests/test_usage_capture.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERF-03 | T-pricing | cost = tokens × pricing (cache discount); override precedence base-ref-only | unit | `uv run pytest tests/test_pricing.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ENGN-08 | T-rawargs | raw_args list appended after framework argv; ignored from PR-head | unit | `uv run pytest tests/test_raw_args.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | ENGN-09 | — | per-role model resolves; consolidate slot resolves but merge stays deterministic | unit | `uv run pytest tests/test_model_roles.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | OUTP-05 | — | compact `$GITHUB_OUTPUT` + full artifact JSON, `schema_version="1.0"` | unit | `uv run pytest tests/test_output_contract.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | OUTP-05 | — | workflow YAML declares outputs + upload-artifact step | static | `uv run pytest tests/test_reusable_workflow_yaml.py -x` | ✅ exists (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config_precedence.py` — WKFL-05 input>yml>default matrix
- [ ] `tests/test_usage_capture.py` — PERF-03 per-strategy capture (stdout-json / otel-jsonl / fallback)
- [ ] `tests/test_pricing.py` — PERF-03 cost compute + cache discount + override precedence
- [ ] `tests/test_raw_args.py` — ENGN-08 list-form append + base-ref-only
- [ ] `tests/test_model_roles.py` — ENGN-09 per-role resolution + deterministic merge preserved
- [ ] `tests/test_output_contract.py` — OUTP-05 compact + full + schema_version
- [ ] `tests/fixtures/pricing/` — small pricing-JSON fixture (don't load the full snapshot in unit tests)
- [ ] `tests/fixtures/usage/` — sample Claude JSON envelope, Cursor JSON (no tokens), Copilot OTEL JSONL line, Antigravity text output

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Antigravity (`agy`) headless review returns parseable output in CI | PERF-03 / ENGN-10 (D-12) | Vendor-controlled binary; non-TTY stdout-drop risk; token reporting unconfirmed | `checkpoint:human-verify` — run a sandbox PR review with `engine: antigravity-cli`, confirm output captured (may need `script -qec` pseudo-TTY wrapper) and tokens fall back to estimate cleanly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
