---
phase: 4
slug: structured-findings-merge-gate
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-12
validated: 2026-06-13
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-cov 7.x + responses 0.26.x (installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests) |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest --cov=prevue` |
| **Estimated runtime** | ~1 second (220 tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q` (scope to the task's test files during Wave 2 parallelism: scaffolds for the *other* in-flight plan stay RED until that plan merges)
- **After every plan wave:** Run `uv run pytest --cov=prevue` (with `--ignore` for scaffolds whose implementing plan has not executed yet)
- **Before `/gsd-verify-work`:** Full suite must be green with ZERO ignores
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | all (dep) | T-04-SC | pinned audited dep, lock committed | import check | `uv run python -c "from unidiff import PatchSet"` | ✅ | ✅ green |
| 04-01-02 | 01 | 1 | all (contracts) | T-04-01 | strict-validation contracts pinned RED | unit | `uv run pytest tests/test_findings_parsing.py tests/test_positions.py tests/test_gate.py tests/test_checks.py -q` | ✅ | ✅ green |
| 04-02-01 | 02 | 2 | ENGN-03 | T-04-02 | last-fence extraction; strict no-coercion salvage | unit | `uv run pytest tests/test_findings_parsing.py tests/test_models.py -x` | ✅ | ✅ green |
| 04-02-02 | 02 | 2 | ENGN-03 | T-04-03 | rubric/contract in trusted prompt section only | unit | `uv run pytest tests/test_copilot_adapter.py -x` | ✅ | ✅ green |
| 04-02-03 | 02 | 2 | ENGN-03 | T-04-04/05/06 | bounded retry; degrade never raises; hard fail stays red | unit | `uv run pytest tests/test_copilot_adapter.py tests/test_findings_parsing.py -q` | ✅ | ✅ green |
| 04-03-01 | 03 | 2 | OUTP-02 | T-04-08 | header-synthesis hunk validation, no snapping | unit | `uv run pytest tests/test_positions.py -x` | ✅ | ✅ green |
| 04-03-02 | 03 | 2 | NOIS-02, OUTP-03 | T-04-07 | fail-closed config before engine spend; neutral never blocks | unit | `uv run pytest tests/test_gate.py -k "ReviewConfig or Conclude"` | ✅ | ✅ green |
| 04-03-03 | 03 | 2 | NOIS-02, NOIS-03, OUTP-03 | T-04-09/10 | budget cap; verdict over ALL findings | unit | `uv run pytest tests/test_gate.py tests/test_positions.py -q` | ✅ | ✅ green |
| 04-04-01 | 04 | 3 | OUTP-02 | T-04-12 | suggestion fence escape-hardened | unit | `uv run pytest tests/test_comments.py -k InlineTemplate` | ✅ | ✅ green |
| 04-04-02 | 04 | 3 | OUTP-03, NOIS-02 | T-04-11/15 | table-cell escaping; verdict mirror via gate helpers | unit | `uv run pytest tests/test_comments.py -x` | ✅ | ✅ green |
| 04-04-03 | 04 | 3 | OUTP-02, NOIS-03 | T-04-14 | single atomic COMMENT POST; crash-proof failure path | unit | `uv run pytest tests/test_comments.py -x` | ✅ | ✅ green |
| 04-05-01 | 05 | 4 | OUTP-03 | T-04-17 | head SHA only; completed-only check | unit | `uv run pytest tests/test_checks.py -x` | ✅ | ✅ green |
| 04-05-02 | 05 | 4 | ENGN-03, OUTP-02, OUTP-03, NOIS-03 | T-04-18 | degrade→neutral; fork→no check; config-fail→red pre-engine | unit | `uv run pytest tests/test_review_flow.py -x && uv run pytest -q` | ✅ | ✅ green |
| 04-05-03 | 05 | 4 | OUTP-03 | T-04-16 | exact-equality permission pin | unit | `uv run pytest tests/test_workflow_yaml.py -x && uv run pytest -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_findings_parsing.py` — RED stubs for ENGN-03 (fence/salvage/strict)
- [x] `tests/test_positions.py` — RED stubs for OUTP-02 (unidiff validity sets incl. `@@ -0,0`, deletions, no-newline marker)
- [x] `tests/test_gate.py` — RED stubs for NOIS-02/NOIS-03/OUTP-03 (config, ladder, partition, budget, verdict strings)
- [x] `tests/test_checks.py` — RED stubs for OUTP-03 (check-run payload via MagicMock)
- [x] `uv add "unidiff==0.7.*"` — before any positions test runs

*(All created by Plan 04-01; this file's `wave_0_complete` flips to true in that plan.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inline comments land on correct diff lines in the real GitHub UI; check run visible in PR merge box and selectable as a required check | OUTP-02, OUTP-03 | RESEARCH Assumptions A2 (GITHUB_TOKEN check-suite grouping) and A4 (LEFT-side comments via batched endpooint) need live confirmation; Copilot fence-compliance rate (A3) is engine-behavioral | Open/refresh the sandbox test PR (Phase 1 precedent, PR #2 pattern): confirm 💬 inline comments on changed lines, `prevue/review` check in merge box, verdict section mirroring check conclusion. End-of-phase UAT per `workflow.human_verify_mode=end-of-phase`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-12 (planner); re-validated 2026-06-13 (`/gsd-validate-phase 4`)

---

## Validation Audit 2026-06-13

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Coverage summary:** 13/13 tasks COVERED (220 tests green). 1 manual-only item retained (live GitHub UI per RESEARCH A2/A4). No new tests required — documentation lag only (status column was ⬜ pending while verifier already green).
