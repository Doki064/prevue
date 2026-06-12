---
phase: 3
slug: selective-skill-loading
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source test map: see `03-RESEARCH.md` § Validation Architecture (authoritative).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (+ pytest-cov 7.1.0) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_skills_loader.py tests/test_skills_builtin.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_skills_loader.py tests/test_skills_builtin.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite green + `uv run ruff check`
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Authoritative requirement→test map lives in `03-RESEARCH.md` § Validation Architecture.
> Planner copies these into per-task `<acceptance_criteria>` / `<automated>` blocks.

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| SKIL-01 | backend-only PR loads backend + security skills, NOT frontend/data/infra | unit | `uv run pytest tests/test_skills_loader.py::test_backend_only_pr_selects_backend_not_frontend -x` | ❌ W0 |
| SKIL-01 | dedupe by path (D-09) | unit | `uv run pytest tests/test_skills_loader.py::test_dedupe_by_path -x` | ❌ W0 |
| SKIL-01 | deterministic order (D-08) | unit | `uv run pytest tests/test_skills_loader.py::test_canonical_then_filename_order -x` | ❌ W0 |
| SKIL-01 | no-match → BASELINE_INSTRUCTIONS alone (D-06) | unit | `uv run pytest tests/test_skills_loader.py::test_no_match_falls_back_to_baseline -x` | ❌ W0 |
| SKIL-01 | assembled = preamble + `## Skill:` sections (D-07) | unit/snapshot | `uv run pytest tests/test_skills_loader.py::test_assemble_sections -x` | ❌ W0 |
| SKIL-02 | all 5 bundle dirs exist; every built-in skill parses + validates | unit | `uv run pytest tests/test_skills_builtin.py::test_all_builtin_skills_valid -x` | ❌ W0 |
| SKIL-02 | security bundle includes committed-secrets skill | unit | `uv run pytest tests/test_skills_builtin.py::test_security_secrets_skill_present -x` | ❌ W0 |
| SKIL-02/D-12 | malformed frontmatter (missing/empty applies-to) raises | unit | `uv run pytest tests/test_skills_loader.py::test_missing_applies_to_raises -x` | ❌ W0 |
| SKIL-04 | load path is packaged framework dir, not `__file__`/PR head | unit | `uv run pytest tests/test_skills_loader.py::test_loads_from_packaged_framework_dir -x` | ❌ W0 |
| SKIL-04 | packaged `.md` readable via importlib.resources | unit | `uv run pytest tests/test_skills_builtin.py::test_skills_packaged_and_readable -x` | ❌ W0 |
| D-13 | run_review threads loaded skill names+bundles into upsert_sticky | unit | `uv run pytest tests/test_review_flow.py::test_loaded_skills_in_metadata -x` | ⚠️ extend |
| D-13 | render_body emits `Skills:` line | unit | `uv run pytest tests/test_comments.py::test_render_body_loaded_skills -x` | ⚠️ extend |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_skills_loader.py` — SKIL-01, D-06/08/09, D-12, SKIL-04 selection/order/fail-closed
- [ ] `tests/test_skills_builtin.py` — SKIL-02 (5 bundles, secrets skill, all-valid, packaged-readable)
- [ ] Extend `tests/test_review_flow.py` — D-13 loaded-skills threading (existing `test_run_review_happy_path*` asserts `instructions == BASELINE_INSTRUCTIONS`; that assertion **must change** once a matching skill loads)
- [ ] Extend `tests/test_comments.py` — D-13 `Skills:` metadata line
- [ ] `uv add python-frontmatter==1.3.*` (behind `checkpoint:human-verify` — legitimacy gate flagged false-positive SUS)
- [ ] conftest fixture: tmp skills tree / `tests/fixtures/skills/` for loader-unit tests independent of real built-in content

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Built-in skill content quality (lean-but-real checklists, D-11) | SKIL-02 | Content judgment, not assertable | Read each `src/prevue/skills/<bundle>/*.md`; confirm genuine review guidance, not placeholders |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
