---
phase: 05
slug: multi-engine-adapter-support
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-13
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

| Behavior (sampling target) | Requirement | Test Type | Automated Command | File Exists |
|----------------------------|-------------|-----------|-------------------|-------------|
| Registry resolves known name → adapter instance | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k resolves -x` | ❌ W0 |
| Default engine is `copilot-cli` when env unset (D-03) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k default -x` | ❌ W0 |
| Unknown `PREVUE_ENGINE` → `UnknownEngineError` naming bad value + listing valid (fail-closed, D-04) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k unknown -x` | ❌ W0 |
| Gemini registered AND `review()` raises `NotImplementedError` (D-02) | ENGN-04 | tdd/unit | `pytest tests/test_registry.py -k gemini -x` | ❌ W0 |
| Each adapter: missing credential → `AuthError` BEFORE subprocess (D-06), parametrized over registry | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k auth -x` | ❌ W0 |
| Each adapter: valid fence stdout → valid `ReviewResult`, not degraded | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k valid_fence -x` | ❌ W0 |
| Each adapter: unparseable stdout → retry → still bad → degraded neutral (D-08) | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k degrade -x` | ❌ W0 |
| Each adapter: bad-then-good retry sets `retried=True` (D-08) | ENGN-04 | tdd/unit | `pytest tests/test_engine_contract.py -k retry -x` | ❌ W0 |
| Each adapter passes correct vendor argv (claude `--bare -p --output-format text`; cursor `-p --output-format text`) | ENGN-04 | unit | `pytest tests/test_engine_contract.py -k argv -x` | ❌ W0 |
| Hoisted prompt: `build_prompt` output identical to pre-hoist; fencing preserved verbatim (D-09) | ENGN-04 | tdd/unit | `pytest tests/test_prompt.py -x` | ❌ W0 |
| `review.py` resolves adapter via `PREVUE_ENGINE` registry when no adapter injected (D-03) | ENGN-04 | unit | `pytest tests/test_review_flow.py -k engine_selection -x` | ⚠️ extend |
| `cli.py` catches shared `AuthError` for non-Copilot adapters | ENGN-04 | tdd/unit | `pytest tests/test_cli.py -k auth -x` | ⚠️ extend |
| Criterion 4: gate/findings/comments/checks layers unchanged (no-regression) | ENGN-04 | regression | `uv run pytest -q` | ✓ existing |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_engine_contract.py` — parametrized contract suite (valid/degrade/retry/auth/argv across `ENGINES.keys()`)
- [ ] `tests/test_registry.py` — resolve / default / unknown-fail-closed / gemini-skeleton
- [ ] `tests/test_prompt.py` — hoisted prompt parity + fencing preserved (D-09)
- [ ] Shared subprocess-mock helpers — move `_stdout_with_fence` + `SAMPLE_REQUEST` into `tests/conftest.py` so the contract suite and `test_copilot_adapter.py` share them
- [ ] Framework install: none needed (pytest/ruff/pytest-cov already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude Code adapter reviews a real sandbox PR end-to-end | ENGN-04 | Live CLI + real auth; no API calls in CI (D-12) | Sandbox test PR via Phase 1 D-11 path; `PREVUE_ENGINE=claude-code-cli`, `ANTHROPIC_API_KEY` set |
| Cursor adapter reviews a real sandbox PR end-to-end | ENGN-04 | Live CLI + real auth; no API calls in CI (D-12) | Sandbox test PR via Phase 1 D-11 path; `PREVUE_ENGINE=cursor-cli`, `CURSOR_API_KEY` set |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
