---
phase: 05
slug: multi-engine-adapter-support
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-13
validated: 2026-06-13
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 05-RESEARCH.md § Validation Architecture (D-11 parametrized contract suite).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.x + pytest-cov 7.1.x (existing) |
| **Config file** | `pyproject.toml` (existing pytest config) |
| **Quick run command** | `uv run pytest tests/test_engine_contract.py tests/test_registry.py tests/test_prompt.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10 seconds (mocked subprocess; no live API in CI) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_engine_contract.py tests/test_registry.py tests/test_prompt.py -x -q`
- **After every plan wave:** Run `uv run pytest -q` (full suite — guards criterion 4 / no-regression)
- **Before `/gsd-verify-work`:** Full suite green + two live sandbox verifications (Claude Code + Cursor, D-12) pass
- **Max feedback latency:** ~10 seconds (quick), ~30s (full)

---

## Per-Task Verification Map

> Task IDs assigned by the planner. Behaviors below are the Nyquist sampling targets — every
> registered adapter is exercised through the parametrized contract suite, so a newly added
> adapter is auto-covered with zero new test code (D-11).

| Behavior (sampling target) | Requirement | Test Type | Automated Command | File Exists | Status |
|----------------------------|-------------|-----------|-------------------|-------------|--------|
| Registry resolves known name → adapter instance | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k resolves -x` | ✅ | ✅ |
| Default engine is `copilot-cli` when env unset (D-03) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k default -x` | ✅ | ✅ |
| Unknown `PREVUE_ENGINE` → `UnknownEngineError` naming bad value + listing valid (fail-closed, D-04) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k unknown -x` | ✅ | ✅ |
| Gemini registered AND `review()` raises `NotImplementedError` (D-02) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k gemini -x` | ✅ | ✅ |
| Each adapter: missing credential → `AuthError` BEFORE subprocess (D-06), parametrized over registry | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k auth -x` | ✅ | ✅ |
| Each adapter: valid fence stdout → valid `ReviewResult`, not degraded | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k valid_fence -x` | ✅ | ✅ |
| Each adapter: unparseable stdout → retry → still bad → degraded neutral (D-08) | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k degrade -x` | ✅ | ✅ |
| Each adapter: bad-then-good retry sets `retried=True` (D-08) | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k retry -x` | ✅ | ✅ |
| Each adapter passes correct vendor argv (claude `--bare -p --output-format text`; cursor `-p --output-format text`) | ENGN-04 | unit | `pytest tests/test_engine_contract.py -k argv -x` | ✅ | ✅ |
| Hoisted prompt: `build_prompt` output identical to pre-hoist; fencing preserved verbatim (D-09) | ENGN-04 | tdd/unit | `pytest tests/test_prompt.py -x` | ✅ | ✅ |
| `review.py` resolves adapter via `PREVUE_ENGINE` registry when no adapter injected (D-03) | ENGN-04 | unit | `pytest tests/test_review_flow.py -k engine_selection -x` | ✅ | ✅ |
| `cli.py` catches shared `AuthError` for non-Copilot adapters | ENGN-04 | tdd/unit | `pytest tests/test_cli.py -k auth -x` | ✅ | ✅ |
| Criterion 4: gate/findings/comments/checks layers unchanged (no-regression) | ENGN-04 | regression | `uv run pytest -q` | ✅ | ✅ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_engine_contract.py` — parametrized contract suite (valid/degrade/retry/auth/argv across `ENGINES.keys()`)
- [x] `tests/test_registry.py` — resolve / default / unknown-fail-closed / gemini-skeleton
- [x] `tests/test_prompt.py` — hoisted prompt parity + fencing preserved (D-09)
- [x] Shared subprocess-mock helpers — `tests/engine_helpers.py`
- [x] Framework install: none needed (pytest/ruff/pytest-cov already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude Code adapter reviews a real sandbox PR end-to-end | ENGN-04 | Live CLI + real auth; no API calls in CI (D-12) | Sandbox test PR via Phase 1 D-11 path; `PREVUE_ENGINE=claude-code-cli`, `ANTHROPIC_API_KEY` set |
| Cursor adapter reviews a real sandbox PR end-to-end | ENGN-04 | Live CLI + real auth; no API calls in CI (D-12) | Sandbox test PR via Phase 1 D-11 path; `PREVUE_ENGINE=cursor-cli`, `CURSOR_API_KEY` set |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** automated coverage approved 2026-06-13; D-12 human UAT pending

---

## Validation Audit 2026-06-13

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Automated behaviors | 13/13 green |
| Manual-only (D-12) | 2 |

**Evidence:** `uv run pytest tests/test_engine_contract.py tests/test_registry.py tests/test_prompt.py tests/test_review_flow.py tests/test_cli.py tests/test_workflow_yaml.py -x -q` — 61 passed; full suite 259 passed in 0.83s.
