---
phase: 9
slug: classification-skill-loading-multi-call-review
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-17
revised: 2026-06-21
---

# Phase 9 — Validation Strategy

> **REVISED 2026-06-21.** The 2026-06-17 version validated the superseded
> "surgical union" design. This version matches the locked re-discussion design:
> classify-first reorder + B+D hybrid skill selection (Thread 1) + configurable
> multi-call review (Thread 2). Derived from 09-RESEARCH.md (Phase Requirements →
> Test Map) and the plan task verify blocks.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-cov 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -q` |
| **Phase-scoped command** | `uv run pytest tests/test_selection.py tests/test_importscan.py tests/test_multicall.py tests/test_skills_loader.py tests/test_review_flow.py tests/test_comments.py tests/test_gate.py tests/test_config.py -q` |
| **Estimated runtime** | ~6 seconds (GitHub API mocked via `responses`; engine adapters stubbed) |

---

## Sampling Rate

- **After every task commit:** Run the task `<automated>` command from the PLAN
- **After every wave merge:** Run the wave gate command below
- **Before phase verify:** `uv run pytest -q` full suite green + `uv run ruff check`
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Plan | Wave | Requirement | Test Type | Automated Command |
|------|------|-------------|-----------|-------------------|
| 09-01 (caps) | 1 | ENGN-05/06/07 | unit | `uv run pytest tests/test_gate.py tests/test_config.py -x -q` |
| 09-01 (RED scaffolds) | 1 | SKIL-01 | scaffold | `uv run pytest tests/test_selection.py tests/test_importscan.py tests/test_multicall.py -q` (MUST fail/error — RED) |
| 09-02 (hybrid select) | 2 | SKIL-01, ROUT-01 | unit | `uv run pytest tests/test_selection.py tests/test_llm_fallback.py -x -q` |
| 09-03 (import scan) | 2 | ENGN-06 | unit | `uv run pytest tests/test_importscan.py -x -q` |
| 09-04 (reorder) | 3 | SKIL-01, ROUT-01, CLSF-03 | integration | `uv run pytest tests/test_review_flow.py -x -q` |
| 09-04 (gap regression) | 3 | SKIL-01 | integration | `uv run pytest tests/test_review_flow.py::test_gap_demo_skill_loaded -x -q` |
| 09-05 (multi-call) | 4 | ENGN-05/06/07 | unit+integration | `uv run pytest tests/test_multicall.py tests/test_review_flow.py -x -q` |
| 09-06 (sticky audit) | 5 | OUTP-04, CLSF-03 | unit | `uv run pytest tests/test_comments.py -k "skill_source or per_call or budget_alert" -x -q` |
| 09-06 (docs+sticky) | 5 | CLSF-03 | integration+doc | `uv run pytest tests/test_review_flow.py::test_sticky_multicall_token_meta -x -q && grep -q "max_review_calls" docs/configuration.md` |
| 09-06 (live UAT) | 5 | SKIL-01, ENGN-05/06/07 | human-verify | Live gap-demo-sandbox PR #25/#26 + multi-call sandbox run |

---

## Wave Gates

| Wave | Gate command | Must pass before next wave |
|------|--------------|----------------------------|
| 1 | `uv run pytest tests/test_gate.py tests/test_config.py -x -q` (caps green; new scaffolds RED) | 09-02, 09-03 |
| 2 | `uv run pytest tests/test_selection.py tests/test_importscan.py tests/test_llm_fallback.py -x -q` | 09-04 |
| 3 | `uv run pytest tests/test_review_flow.py -x -q` (incl. gap-demo-sandbox regression) | 09-05 |
| 4 | `uv run pytest tests/test_multicall.py tests/test_review_flow.py -x -q` | 09-06 |
| 5 | `uv run pytest -q` (full suite) + live UAT approved | verify-phase |

---

## Success-Criteria → Test Coverage

| SC | Behavior | Plan | Test |
|----|----------|------|------|
| 1 | routed bundle skills unioned into instructions pre-review | 09-04 | test_routed_bundle_skill_loads_via_union |
| 2 | glob select unchanged for non-routed bundles | 09-04 | test_non_routed_bundle_glob_unchanged |
| 3 | LLM fallback labels trigger same union | 09-04 | test_llm_fallback_label_triggers_bundle_selection |
| 4 | post-union re-trim + byte guard → neutral skip | 09-04/09-05 | test_post_union_budget_neutral_skip / test_whole_run_cap_overflow_disclosure |
| 5 | sticky reflects final loaded skills; docs match | 09-06 | test_render_body_skill_source_provenance + docs grep |
| 6 | gap-demo-sandbox regression (bundle ≠ glob path) | 09-04 | test_gap_demo_skill_loaded |
| 7 | max_review_calls default 1; single-call unchanged | 09-05 | test_single_call_default_unchanged |
| 8 | bundle-aligned + import-co-located split | 09-05 | test_multicall_split_and_merge |
| 9 | findings merged + fingerprint-deduped before gate | 09-05 | merge_dedupe + severity tie-break tests |
| 10 | review_concurrency default 1; parallel up to cap | 09-05 | test_multicall_parallel_fail_soft |

---

## Lint

| When | Command |
|------|---------|
| After each plan | `uv run ruff check src/prevue/skills/ src/prevue/importscan.py src/prevue/multicall.py src/prevue/review.py src/prevue/gate.py src/prevue/github/comments.py src/prevue/classify/llm_fallback.py` |

---

## Validation Audit 2026-06-23

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests run | 720 (full suite) / 312 (phase-scoped) |
| Lint | clean |

All requirements COVERED. Key regressions confirmed:
- `test_gap_demo_skill_loaded` — PASS
- `test_sticky_multicall_token_meta` — PASS
- `test_comments.py` skill_source/per_call/budget_alert (12 tests) — PASS
- `docs/configuration.md` contains `max_review_calls` — PASS

---

*Phase 9 validation (revised) — execute with `/gsd-execute-phase 9`*
