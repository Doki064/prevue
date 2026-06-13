---
phase: 1
slug: walking-skeleton-review-loop
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-12
validated: 2026-06-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `01-RESEARCH.md` → Validation Architecture.
> Retroactively audited 2026-06-13 via `/gsd-validate-phase 1`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.* + pytest-cov 7.* + responses 0.26.* |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options] testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest --cov=prevue` |
| **Estimated runtime** | ~1s (pure unit + mocked REST; no live calls) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest --cov=prevue` + `ruff check` + `actionlint` + zizmor in CI
- **Before `/gsd-verify-work`:** Full suite green + one live sandbox PR shows sticky comment created then updated
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Req / Decision | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| ENGN-01 | `ReviewRequest`/`ReviewResult` validate; `findings` defaults `[]`; round-trips JSON | — | pydantic boundary validation | unit | `uv run pytest tests/test_models.py -x -q` | ✅ | ✅ green |
| DIFF-01 | `fetch_diff()` builds `DiffBundle` from mocked `get_files()`; no checkout invoked | T-1 secret-exfil | Diff fetched as API data, never a checked-out tree | unit | `uv run pytest tests/test_diff.py -x -q` | ✅ | ✅ green |
| DIFF-01 | Live: PR event run produces a `DiffBundle` with correct file count | — | N/A | integration (sandbox PR, D-11) | manual — [PR #2](https://github.com/Doki064/prevue/pull/2), [run 27378511750](https://github.com/Doki064/prevue/actions/runs/27378511750) | ✅ | ✅ green (2026-06-12) |
| ENGN-02 | Adapter builds fenced prompt containing diff + file list, **excludes** PR title/body | T-1 prompt-injection | Untrusted diff fenced as DATA; title/body omitted (D-07) | unit | `uv run pytest tests/test_copilot_adapter.py::TestBuildPrompt -x -q` | ✅ | ✅ green |
| ENGN-02 | Auth guard rejects missing/`ghp_` token; timeout / non-zero exit / empty stdout → `EngineFailure` | T-2 token shadowing | `COPILOT_GITHUB_TOKEN` prefix guard; never log token | unit (monkeypatch subprocess) | `uv run pytest tests/test_copilot_adapter.py -k "AuthGuard or FailurePaths" -x -q` | ✅ | ✅ green |
| ENGN-02 | Live: `copilot -s --no-ask-user` returns prose on a clean runner | — | Zero tools granted; agent has no write path | integration (spike D-12 → E2E) | manual — spike deleted post-E2E; live run 27378511750 | ✅ | ✅ green (2026-06-12) |
| OUTP-01 | `upsert_sticky`: no marker → create; existing marker → edit (single comment) | — | Deterministic Python owns all GitHub writes | unit (mock PR, responses) | `uv run pytest tests/test_comments.py -x -q` | ✅ | ✅ green |
| OUTP-01 | Live: open PR → comment appears; push again → same comment updated, not duplicated | — | N/A | integration (sandbox PR, D-11) | manual — [PR #2](https://github.com/Doki064/prevue/pull/2) sticky `edited: true` | ✅ | ✅ green (2026-06-12) |
| SECR-01 | Workflow has `pull_request` and **no** `pull_request_target`; perms exactly `contents: read` / `pull-requests: write` | T-3 priv-escalation | `pull_request`-only; least-privilege perms | static | `uv run pytest tests/test_workflow_yaml.py -x -q` + zizmor in CI | ✅ | ✅ green |
| SECR-01 | Fork PR (`head.repo != base`) → early documented exit, no raw 403 | T-4 fork DoS/UX | Fork detected at start; documented unsupported; CLI exit 0 | unit + doc check | `uv run pytest tests/test_fork_guard.py -x -q` + README fork matrix | ✅ | ✅ green |
| D-09 | Engine failure leaves sticky comment untouched (upsert not reached) and exits non-zero | — | Fail closed; no error comment on PR thread | unit (orchestration) | `uv run pytest tests/test_review_flow.py -k failure -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Requirement coverage (all five phase requirement IDs mapped): **DIFF-01** (rows 2–3), **ENGN-01** (row 1), **ENGN-02** (rows 4–6), **OUTP-01** (rows 7–8), **SECR-01** (rows 9–10). **D-09** (row 11) is a phase decision with automated coverage.

---

## Wave 0 Requirements

- [x] `pyproject.toml` with pytest/ruff config + `uv init --package prevue` scaffold
- [x] `tests/conftest.py` — shared fixtures (fake engine runner, `responses` activation, sample event JSON)
- [x] `tests/fixtures/pulls_files.json` — recorded `/pulls/{n}/files` payload
- [x] `tests/fixtures/event_pull_request.json` — sample `GITHUB_EVENT_PATH` payload
- [x] `tests/fixtures/event_pull_request_fork.json` — fork PR event payload
- [x] Framework install: `pytest==9.*`, `pytest-cov==7.*`, `responses==0.26.*`, `ruff==0.15.*` in dev group
- [x] CI workflow (`ci.yml`) running pytest + ruff + actionlint + zizmor

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Copilot CLI auth + prose output on a clean runner | ENGN-02 | Needs live runner + real `COPILOT_GITHUB_TOKEN` | D-12 spike (deleted post-E2E); full loop on PR #2 | ✅ done 2026-06-12 |
| End-to-end sticky comment created then updated | OUTP-01, DIFF-01 | Requires live PR event through GitHub Actions | PR #2: one comment, updated in place on re-push | ✅ done 2026-06-12 |
| Workflow security smells (broad perms, unpinned actions, `pull_request_target`) | SECR-01 | zizmor runs in CI, not pytest | `zizmorcore/zizmor-action` step in `ci.yml` | ✅ enforced in CI |

*Automated pytest covers all unit/static behaviors. Manual rows above were executed during Phase 1 E2E (Plan 07) and remain the live-integration proof layer.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-13

---

## Validation Audit 2026-06-13

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap closed:** SECR-01 fork CLI exit 0 — added `test_cli_fork_returns_exit_zero` in `tests/test_fork_guard.py`.

**Audit commands run:**

```bash
uv run pytest tests/test_models.py tests/test_diff.py tests/test_copilot_adapter.py \
  tests/test_comments.py tests/test_workflow_yaml.py tests/test_fork_guard.py \
  tests/test_review_flow.py -k failure -x -q
# 66 passed (post gap-fill)

uv run pytest -q
# 115 passed
```

**Coverage summary:** 11/11 verification-map rows green (8 automated pytest, 3 manual executed during Phase 1 E2E). No PARTIAL or MISSING automated rows remain.
