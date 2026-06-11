---
phase: 1
slug: walking-skeleton-review-loop
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `01-RESEARCH.md` → Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-cov 7.1.0 + responses 0.26.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — none yet (Wave 0 installs) |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest --cov=prevue` |
| **Estimated runtime** | ~5–15 seconds (pure unit + mocked REST; no live calls) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest --cov=prevue` + `ruff check` + `actionlint` + `zizmor .github/workflows`
- **Before `/gsd-verify-work`:** Full suite green + spike workflow green + one live sandbox PR shows a sticky comment created then updated
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

> Plan/Wave/Task IDs are assigned by the planner; rows below are the requirement→test contract every task must satisfy. Status updated during execution.

| Req / Decision | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| ENGN-01 | `ReviewRequest`/`ReviewResult` validate; `findings` defaults `[]`; round-trips JSON | — | pydantic boundary validation | unit | `uv run pytest tests/test_models.py -x` | ❌ W0 | ⬜ pending |
| DIFF-01 | `fetch_diff()` builds `DiffBundle` from mocked `get_files()`; no checkout invoked | T-1 secret-exfil | Diff fetched as API data, never a checked-out tree | unit | `uv run pytest tests/test_diff.py -x` | ❌ W0 | ⬜ pending |
| DIFF-01 | Live: PR event run produces a `DiffBundle` with correct file count | — | N/A | integration (sandbox PR, D-11) | manual | ❌ W0 | ⬜ pending |
| ENGN-02 | Adapter builds fenced prompt containing diff + file list, **excludes** PR title/body | T-1 prompt-injection | Untrusted diff fenced as DATA; title/body omitted (D-07) | unit | `uv run pytest tests/test_copilot_adapter.py::test_prompt -x` | ❌ W0 | ⬜ pending |
| ENGN-02 | Auth guard rejects missing/`ghp_` token; timeout / non-zero exit / empty stdout → `EngineFailure` | T-2 token shadowing | `COPILOT_GITHUB_TOKEN` prefix guard; never log token | unit (monkeypatch subprocess) | `uv run pytest tests/test_copilot_adapter.py -k failure -x` | ❌ W0 | ⬜ pending |
| ENGN-02 | Live: `copilot -p -s --no-ask-user` returns prose on a clean runner | — | Zero tools granted; agent has no write path | integration (spike D-12) | `workflow_dispatch` spike workflow | ❌ W0 | ⬜ pending |
| OUTP-01 | `upsert_sticky`: no marker → create; existing marker → edit (single comment) | — | Deterministic Python owns all GitHub writes | unit (mock PR, responses) | `uv run pytest tests/test_comments.py -x` | ❌ W0 | ⬜ pending |
| OUTP-01 | Live: open PR → comment appears; push again → same comment updated, not duplicated | — | N/A | integration (sandbox PR, D-11) | manual | ❌ W0 | ⬜ pending |
| SECR-01 | Workflow has `pull_request` and **no** `pull_request_target`; perms exactly `contents: read` / `pull-requests: write` | T-3 priv-escalation | `pull_request`-only; least-privilege perms | static | `uv run pytest tests/test_workflow_yaml.py -x` + zizmor in CI | ❌ W0 | ⬜ pending |
| SECR-01 | Fork PR (`head.repo != base`) → early documented exit, no raw 403 | T-4 fork DoS/UX | Fork detected at start; documented unsupported | unit + doc check | `uv run pytest tests/test_fork_guard.py -x` | ❌ W0 | ⬜ pending |
| D-09 | Engine failure leaves sticky comment untouched (upsert not reached) and exits non-zero | — | Fail closed; no error comment on PR thread | unit (orchestration) | `uv run pytest tests/test_review_flow.py -k failure -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` with pytest/ruff config + `uv init --package prevue` scaffold — none exists (greenfield)
- [ ] `tests/conftest.py` — shared fixtures (fake engine runner, `responses` activation, sample event JSON)
- [ ] `tests/fixtures/pulls_files.json` — recorded `/pulls/{n}/files` payload
- [ ] `tests/fixtures/event_pull_request.json` — sample `GITHUB_EVENT_PATH` payload
- [ ] Framework install: `uv add --dev pytest==9.* pytest-cov==7.* responses==0.26.* ruff==0.15.*`
- [ ] CI workflow (`ci.yml`) running pytest + ruff + actionlint + zizmor

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Copilot CLI auth + prose output on a clean runner | ENGN-02 | Needs a live runner + real `COPILOT_GITHUB_TOKEN`; cannot be unit-mocked | Run the D-12 `spike-copilot.yml` via `workflow_dispatch`; confirm `PREVUE_SPIKE_OK` (or equivalent prose) and record timing |
| End-to-end sticky comment created then updated | OUTP-01, DIFF-01 | Requires a live PR event through GitHub Actions | Open a PR in the sandbox repo (D-11); confirm one comment appears, push again, confirm same comment updated (not duplicated) |
| Workflow security smells (broad perms, unpinned actions, `pull_request_target`) | SECR-01 | Static analyzer, run in CI not pytest | `zizmor .github/workflows` exits clean in `ci.yml` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
