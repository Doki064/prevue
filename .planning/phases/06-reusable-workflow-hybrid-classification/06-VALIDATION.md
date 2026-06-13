---
phase: 06
slug: reusable-workflow-hybrid-classification
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-13
validated: 2026-06-14
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `06-RESEARCH.md` § Validation Architecture. Task IDs are filled by the planner/executor.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.x + pytest-cov 7.1.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_reusable_workflow_yaml.py tests/test_config.py tests/test_skip.py tests/test_llm_fallback.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Workflow static guards** | `tests/test_reusable_workflow_yaml.py` + `tests/test_workflow_yaml.py` |
| **Estimated runtime** | ~1 second (full suite on current repo) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_<touched>.py -x -q` + `uv run ruff check .`
- **After every plan wave:** `uv run pytest -q` + `uv run ruff format --check .`
- **Before `/gsd-verify-work`:** phase-targeted suites green + full suite green + workflow static guards green
- **Max feedback latency:** ~1 second on current phase test load

---

## Per-Task Verification Map

> Requirement coverage mapped to executed plans `06-01` .. `06-04`.

| Task ID | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-02 | WKFL-01 | — | Reusable `prevue-review.yml` has `on: workflow_call`, minimal inputs, named `required:false` secrets | unit (YAML static) | `uv run pytest tests/test_reusable_workflow_yaml.py::test_workflow_call_trigger -x` | ✅ | ✅ |
| 06-02 | WKFL-01 | — | Thin `review.yml` `uses:` the reusable workflow (dogfood) | unit (YAML static) | `uv run pytest tests/test_workflow_yaml.py::test_review_yml_uses_reusable_workflow -x` | ✅ | ✅ |
| 06-02 | WKFL-02 | — | Self-checkout Prevue at pinned non-`main` ref + consumer at `base.sha`; single `prevue review` invocation | unit (YAML static) | `uv run pytest tests/test_reusable_workflow_yaml.py::test_two_checkouts tests/test_reusable_workflow_yaml.py::test_self_checkout_ref_not_main -x` | ✅ | ✅ |
| 06-04 | WKFL-02 | — | Live: separate consumer repo gets a working review via pinned ref | manual (sandbox PR) | manual — sandbox consumer PR walkthrough (`06-VERIFICATION.md`) | ✅ | ✅ |
| 06-01/06-03 | WKFL-03 | — | Single `.github/prevue.yml` read feeds rules/review/skip/engine/fallback; absent file → all defaults | unit | `uv run pytest tests/test_config.py -x` | ✅ | ✅ |
| 06-01/06-03 | WKFL-03 | — | `load_ruleset` receives consumer config path through `load_config`/`run_review` wiring | unit | `uv run pytest tests/test_config.py::test_consumer_rules_applied tests/test_review_flow.py::test_run_review_uses_default_config_path -x` | ✅ | ✅ |
| 06-02 | WKFL-04 | T-06-sec | Permissions exactly {contents:read, pull-requests:write, checks:write}; no `secrets: inherit`; no `pull_request_target` | unit (YAML static) | `uv run pytest tests/test_reusable_workflow_yaml.py::test_minimal_permissions tests/test_reusable_workflow_yaml.py::test_no_pull_request_target tests/test_reusable_workflow_yaml.py::test_no_secrets_inherit -x` | ✅ | ✅ |
| 06-03 | CLSF-02 | — | All-matched PR triggers ZERO `adapter.classify()` calls (zero-token) | unit (mock adapter) | `uv run pytest tests/test_llm_fallback.py::test_no_call_when_all_matched tests/test_review_flow.py::test_run_review_fallback_skipped_when_all_matched -x` | ✅ | ✅ |
| 06-03 | CLSF-02 | — | Unmatched files → `classify()` called with ONLY those paths; labels validated to canonical set | unit (mock adapter) | `uv run pytest tests/test_llm_fallback.py::test_unmatched_only tests/test_review_flow.py::test_run_review_fallback_fires_on_unmatched_paths tests/test_engine_contract.py::test_classify_drops_unknown_labels -x` | ✅ | ✅ |
| 06-03 | CLSF-02 | — | Fallback failure (raise/timeout/bad label) → degrade to `general` + disclosure, no red | unit (mock adapter) | `uv run pytest tests/test_llm_fallback.py::test_degrade_to_general -x` | ✅ | ✅ |
| 06-02 | NOIS-01 | — | Draft skipped at workflow `if:` | unit (YAML static) | `uv run pytest tests/test_reusable_workflow_yaml.py::test_draft_if_guard -x` | ✅ | ✅ |
| 06-04 | NOIS-01 | — | `pr.user.type=="Bot"` skipped unless in `review_bots`; neutral check posted | unit (responses) | `uv run pytest tests/test_skip.py::test_bot_skip_neutral tests/test_review_flow.py::test_run_review_bot_skip_neutral_no_engine -x` | ✅ | ✅ |
| 06-04 | NOIS-01 | — | `skip-review` label skips by default; `skip_labels`/`skip_title_patterns` configurable | unit | `uv run pytest tests/test_skip.py::test_label_and_title -x` | ✅ | ✅ |
| 06-04 | NOIS-01 | — | Skip posts sticky reason + neutral (non-blocking) check | unit (responses) | `uv run pytest tests/test_skip.py::test_skip_surface -x` | ✅ | ✅ |

*Status: ✅ green · ⚠️ flaky · ❌ red*

---

## Wave 0 Requirements

- [x] `tests/test_reusable_workflow_yaml.py` — static guards for `prevue-review.yml` (workflow_call, inputs, required:false secrets, permissions, draft `if:`, two checkouts, SHA/tag pins, no `pull_request_target`/`secrets: inherit`) — WKFL-01/02/04, NOIS-01 draft
- [x] `tests/test_config.py` — single-read `.github/prevue.yml` loader (all sections; absent-file defaults; `extra="forbid"` typo → fail) — WKFL-03
- [x] `tests/test_skip.py` — `should_skip` bot/label/title + neutral surfacing (responses mocks) — NOIS-01
- [x] `tests/test_llm_fallback.py` — per-file fallback: no-call-when-matched, unmatched-only, label validation, degrade-to-general (mock adapter) — CLSF-02
- [x] Extend `tests/test_workflow_yaml.py` — assert `review.yml` now `uses:` the reusable workflow (dogfood)
- [x] Extend `tests/test_review_flow.py` — skip-path early-return, fallback wiring, config-path default `.github/prevue.yml`
- [x] Extend engine contract suite (`tests/test_engine_contract.py`) — parametrized `classify()` contract case per adapter (mock subprocess); Gemini asserts `NotImplementedError`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Separate consumer repo adopts Prevue via `workflow_call` at a pinned ref and gets a working review | WKFL-01 / WKFL-02 (Success Criterion #1) | `workflow_call` E2E not reliably provable in local test harnesses | Run sandbox consumer PR scenario from `06-04-PLAN.md` Task 3 (documented in `06-VERIFICATION.md`) |
| Per-engine cheap-model classification JSON reliability/latency | CLSF-02 (A2/A4) | Live model behavior cannot be unit-tested deterministically | Confirm ambiguous-file PR routes through fallback label or degrade disclosure in sandbox run |
| `neutral` check satisfies required branch protection without blocking | NOIS-01 (A3) | Required-check behavior is GitHub platform runtime behavior | In sandbox repo, mark Prevue check required and verify skip path remains non-blocking |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** automated coverage approved 2026-06-14; manual-only checkpoints documented in `06-VERIFICATION.md`.

---

## Validation Audit 2026-06-14

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Automated behaviors | 14/14 green |
| Manual-only checks | 3 |

**Evidence:** `uv run pytest tests/test_reusable_workflow_yaml.py tests/test_workflow_yaml.py tests/test_config.py tests/test_skip.py tests/test_llm_fallback.py tests/test_review_flow.py tests/test_engine_contract.py -q` (85 passed), plus full suite `uv run pytest -q` (299 passed).
