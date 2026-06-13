---
phase: 2
slug: zero-token-classification-routing
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-11
validated: 2026-06-13
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 02-RESEARCH.md §Validation Architecture (Requirements→Test Map + Wave 0 Gaps).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.* + pytest-cov 7.* (`[dependency-groups].dev` in pyproject.toml) — already installed |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options] testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest tests/test_classify_*.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5 seconds (pure-function tests, zero network; `responses` mocks GitHub REST in flow tests) |

Mock approach: `responses` for GitHub REST (existing Phase 1 pattern). classify/filter/route are pure functions → no mocks, only plain-literal `ChangedFile`/`DiffBundle` data fixtures.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_classify_*.py -x -q`
- **After every plan wave:** Run `uv run pytest -q` (full suite green incl. Phase 1 regression)
- **Before `/gsd-verify-work`:** Full suite must be green **and** `uv run ruff check` clean
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | CLSF-03 (packaging) | T-02-01 / T-02-04 / T-02-SC | `yaml.safe_load` only (never `yaml.load`); malformed rules → pydantic ValidationError (fail-closed); `default_rules.yml` resolves via `importlib.resources` (never `__file__`) after wheel build | unit + integration | `uv run pytest tests/test_classify_rules.py -x -q` | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | DIFF-02, CLSF-01, ROUT-01 | T-02-02 / T-02-03 | Pure functions only (no I/O/subprocess/network); never mutate input `DiffBundle` (`model_copy`); matched-glob provenance via `check_file().index`; no 0.12-era `gitwildmatch` factory | unit | `uv run pytest tests/test_classify_filter.py tests/test_classify_classifier.py tests/test_classify_router.py -x -q` | ✅ | ✅ green |
| 02-01-03 | 01 | 1 | DIFF-02 (D-08), CLSF-01, CLSF-03 (D-09) | T-02-03 | Engine receives a **reduced** `DiffBundle` (filtered files dropped, D-08); dropped lockfile produces no entry in `ClassificationResult.labels` (D-08 classification half); classify stage makes zero subprocess/network calls | unit | `uv run pytest tests/test_review_flow.py tests/test_comments.py -x -q` | ✅ | ✅ green |
| 02-02-01 | 02 | 2 | CLSF-01 (D-01/D-02/D-03), CLSF-03 (D-09) | T-02-05 / T-02-06 | D-03 `general` fallback so no file is silently un-reviewed; D-01 union so secondary domains are not dropped; fixed `CANONICAL_LABEL_ORDER` → deterministic, churn-free audit | unit | `uv run pytest tests/test_classify_classifier.py -x -q` | ✅ | ✅ green |
| 02-02-02 | 02 | 2 | ROUT-01 (D-06), CLSF-03 (D-09) | T-02-06 | `route` handles `general` (1:1, override-able, D-06); Metadata renders labels + bundles in `CANONICAL_LABEL_ORDER` (deterministic, no nondeterministic churn) | unit | `uv run pytest tests/test_classify_router.py tests/test_comments.py -x -q` | ✅ | ✅ green |
| 02-03-01 | 03 | 3 | CLSF-03 (D-05/D-07), ROUT-01 (D-06) | T-02-08 / T-02-09 / T-02-10 | `yaml.safe_load` for consumer config; result validated into pydantic `RuleSet` (fail-closed on malformed); consumer config read from **trusted base ref only** (no PR-head read path); additive merge so built-in security globs survive unless explicitly overridden | unit | `uv run pytest tests/test_classify_rules.py -x -q` | ✅ | ✅ green |
| 02-03-02 | 03 | 3 | DIFF-02 (D-10/D-08), CLSF-03 (D-09) | T-02-11 | D-10 filter-first ordering: `if not reduced.files: upsert_skip_note(); return` gates BEFORE the engine call → zero engine tokens on all-noise PRs; dropped count disclosed in the D-09 audit trail (suppression is visible, never silent) | unit | `uv run pytest tests/test_review_flow.py tests/test_comments.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Requirement coverage (all four phase requirement IDs mapped): **DIFF-02** (02-01-02, 02-01-03, 02-03-02), **CLSF-01** (02-01-02, 02-01-03, 02-02-01), **CLSF-03** (02-01-01, 02-01-03, 02-02-01, 02-02-02, 02-03-01, 02-03-02), **ROUT-01** (02-01-02, 02-02-02, 02-03-01).

---

## Wave 0 Requirements

New test files (RED-first; created by the task that owns them per the plan's TDD flow):

- [x] `tests/test_classify_filter.py` — DIFF-02 filter behavior, additive consumer ignores, dropped-count (created in 02-01 Task 2)
- [x] `tests/test_classify_classifier.py` — CLSF-01 label assignment, D-01 union, D-03 general, provenance (created in 02-01 Task 2)
- [x] `tests/test_classify_rules.py` — CLSF-03 YAML load + packaged-resource load + additive merge (created in 02-01 Task 1)
- [x] `tests/test_classify_router.py` — ROUT-01 routing map + precedence D-06 (created in 02-01 Task 2)

Extensions to existing Phase 1 test files (no new file; extend in place):

- [x] Extend `tests/test_review_flow.py` — D-08 reduced bundle reaches engine (`test_run_review_filtered_diff_and_classification_metadata`); D-10 neutral skip branch (`test_run_review_empty_skip_no_engine_call`)
- [x] Extend `tests/test_comments.py` — D-09 Metadata renders labels + matched rules + dropped count (`test_render_body_metadata_*`); skip-note idempotency (`test_upsert_skip_note_*`)

Test data fixtures: sample `ChangedFile` lists per scenario (frontend-only, mixed-domain, lockfile-only, no-match) — plain Python literals, no I/O.

Framework install: none — pytest/pytest-cov already in the dev group; runtime deps `pathspec`/`PyYAML` are added by 02-01 Task 1 (not a test-infra gap).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.* The phase is pure Python (classify/filter/route are pure functions; GitHub I/O is mocked with `responses`), so every requirement maps to a `pytest` command above. Live-PR smoke verification against a sandbox repo is a phase-gate convenience, not a substitute for any automated check.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 new test files + 2 extensions; creators named)
- [x] No watch-mode flags (all commands use `-x -q`, no `--watch`)
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-11 · validated 2026-06-13

---

## Validation Audit 2026-06-13

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Audit notes:** State A (VALIDATION.md existed pre-execution). All 7 tasks now COVERED — 4 Wave 0 test files + 2 Phase 1 extensions exist and pass. Per-task commands verified green; full suite 115 passed in 0.70s. No new tests generated; doc sync only.
