---
phase: 01-walking-skeleton-review-loop
verified: 2026-06-12T14:30:02Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Structured findings validated and populated in ReviewResult.findings"
    addressed_in: "Phase 4"
    evidence: "D-01/D-02: Phase 1 carries prose in summary_markdown; findings list intentionally empty until Phase 4 schema validation"
  - truth: "Verdict section shows pass/fail merge gate"
    addressed_in: "Phase 4"
    evidence: "D-05: Verdict placeholder states 'no verdict in v1'; OUTP-03 merge gate deferred"
  - truth: "Inline line-level review comments"
    addressed_in: "Phase 4"
    evidence: "OUTP-02 not in Phase 1 scope; sticky summary only"
  - truth: "Consumer .github/prevue.yml loaded from trusted base ref at runtime"
    addressed_in: "Phase 5"
    evidence: "Phase 5 goal: configurable behavior via prevue.yml from base ref"
---

# Phase 1: Walking Skeleton Review Loop Verification Report

**Phase Goal:** End-to-end PR review loop on Actions: PR event → fetch diff via GitHub API (no untrusted checkout) → Copilot CLI via EngineAdapter → sticky summary comment posted/updated in place. `pull_request` only; forks unsupported.

**Verified:** 2026-06-12T14:30:02Z  
**Status:** passed  
**Re-verification:** No — initial verification (prior working-copy report discarded; regenerated from live codebase)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DIFF-01: `fetch_diff()` builds `DiffBundle` from GitHub REST API; no PR-head checkout for analysis | ✓ VERIFIED | `src/prevue/github/diff.py` maps `pr.get_files()` → `ChangedFile`; `client.py` uses PyGithub only; `test_fetch_diff_returns_diff_bundle`; `test_workflow_yaml.py::test_no_pr_head_checkout` |
| 2 | ENGN-01: `ReviewRequest`/`ReviewResult` pydantic contract with `Finding` model; pluggable `EngineAdapter` ABC | ✓ VERIFIED | `src/prevue/models.py` (lines 24–44); `src/prevue/engines/base.py`; `CopilotCliAdapter(EngineAdapter)` |
| 3 | ENGN-02: Copilot CLI headless (`-s --no-ask-user`, stdin prompt, no `--allow-tool`); auth via `COPILOT_GITHUB_TOKEN` fine-grained PAT guard | ✓ VERIFIED | `copilot_cli.py` lines 75–127; `test_command_uses_s_and_no_ask_user_without_allow_tool`; `TestAuthGuard` |
| 4 | D-07: Prompt excludes PR title/body — diff + changed-file list only | ✓ VERIFIED | `DiffBundle` has no title/body fields (`models.py` line 21 comment); `test_excludes_pr_title_and_body`; `_build_prompt` uses paths/status/patches only |
| 5 | OUTP-01: Marker-based sticky comment upsert; in-place edit on subsequent runs (D-06) | ✓ VERIFIED | `comments.py` `MARKER`, `_upsert_marker_comment`; `test_upsert_sticky_edits_existing_marker_comment`; sectioned shell Verdict/Review/Metadata (D-04) |
| 6 | SECR-01: `pull_request` trigger only; least-privilege permissions; fork guard; static CI gates | ✓ VERIFIED | `review.yml` `on.pull_request` + `permissions: {contents: read, pull-requests: write}`; `test_pull_request_trigger_only`; `test_fork_guard.py`; `ci.yml` actionlint + zizmor steps |
| 7 | D-09: Engine failure leaves sticky untouched; workflow exits non-zero | ✓ VERIFIED | `run_review` calls `upsert_sticky` only after `engine.review()` succeeds; `test_engine_failure_propagates_without_upsert`; `cli.py` returns 1 on `EngineFailure`/`CopilotAuthError` (spot-checked) |
| 8 | Fork PR (`head.repo != base.repo`) exits early with documented message; no fetch/engine/post | ✓ VERIFIED | `review.py` lines 39–40; `test_fork_pr_exits_early_without_side_effects`; README fork matrix documents unsupported v1 |
| 9 | End-to-end wiring: `review.yml` → `uv run prevue review` → `run_review()` pipeline | ✓ VERIFIED | `review.yml` single `uv run prevue review` step; `pyproject.toml` script `prevue = prevue.cli:main`; `test_run_review_happy_path_calls_upsert_once` |
| 10 | Throwaway spike workflow removed post-E2E (D-12) | ✓ VERIFIED | `spike-copilot.yml` absent from repo; only `review.yml` + `ci.yml` under `.github/workflows/` |

**Score:** 10/10 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Structured findings in `ReviewResult.findings` | Phase 4 | D-01/D-02: prose in `summary_markdown`; empty findings list by design |
| 2 | Verdict pass/fail merge gate | Phase 4 | D-05 placeholder; OUTP-03 deferred |
| 3 | Inline line-level comments | Phase 4 | OUTP-02 deferred |
| 4 | Consumer `prevue.yml` from trusted base ref | Phase 5 | Phase 5 roadmap goal |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/github/diff.py` | API diff fetch → DiffBundle | ✓ VERIFIED | 28 lines; `pr.get_files()` mapping; patch=None when omitted |
| `src/prevue/github/client.py` | PR context from event payload; PyGithub pull | ✓ VERIFIED | No git checkout; `GITHUB_EVENT_PATH` parse |
| `src/prevue/models.py` | Engine contract models | ✓ VERIFIED | `ChangedFile`, `DiffBundle`, `ReviewRequest`, `ReviewResult`, `Finding` |
| `src/prevue/engines/base.py` | `EngineAdapter` ABC | ✓ VERIFIED | Single `review()` abstract method |
| `src/prevue/engines/copilot_cli.py` | Copilot CLI adapter | ✓ VERIFIED | Subprocess in engine layer only; auth + failure guards |
| `src/prevue/github/comments.py` | Sticky upsert | ✓ VERIFIED | Marker scan/edit/create; trusted actor check |
| `src/prevue/review.py` | `run_review()` orchestration | ✓ VERIFIED | Fork guard → fetch → engine → upsert; fail-closed on engine error |
| `src/prevue/cli.py` | `prevue review` entrypoint | ✓ VERIFIED | Exit 0 success/fork-skip; exit 1 engine/auth failure |
| `.github/workflows/review.yml` | PR-triggered review job | ✓ VERIFIED | SHA-pinned actions; separate GITHUB_TOKEN / COPILOT_GITHUB_TOKEN |
| `.github/workflows/ci.yml` | Test + lint + workflow security gate | ✓ VERIFIED | pytest, ruff, actionlint, zizmor-action |
| `tests/test_diff.py` | Diff fetch unit tests | ✓ VERIFIED | responses fixtures; no checkout assertions |
| `tests/test_copilot_adapter.py` | ENGN-02 adapter tests | ✓ VERIFIED | Prompt, auth, failure, success paths |
| `tests/test_comments.py` | OUTP-01 sticky tests | ✓ VERIFIED | Marker upsert create/edit/skip paths |
| `tests/test_workflow_yaml.py` | SECR-01 static guards | ✓ VERIFIED | 11 tests on trigger, perms, pins, no PR-head ref |
| `tests/test_fork_guard.py` | Fork early exit | ✓ VERIFIED | No fetch/adapter/upsert on fork |
| `tests/test_review_flow.py` | E2E orchestration + D-09 | ✓ VERIFIED | Happy path + engine failure without upsert |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `review.yml` | `cli.py::main` | `uv run prevue review` | ✓ WIRED | Single invocation asserted in `test_single_prevue_review_invocation` |
| `cli.py` | `review.py::run_review` | `_cmd_review()` dispatch | ✓ WIRED | `run_review()` called from review subcommand |
| `review.py` | `fetch_diff()` | First data step after fork guard | ✓ WIRED | Line 42; mocked in happy-path test |
| `review.py` | `CopilotCliAdapter.review` | `engine.review(req)` | ✓ WIRED | Line 67; injectable adapter in tests |
| `review.py` | `upsert_sticky()` | Post-engine success only | ✓ WIRED | Lines 69–74; skipped on `EngineFailure` |
| `copilot_cli.py` | `subprocess.run(["copilot", ...])` | Engine subprocess boundary | ✓ WIRED | Only subprocess usage under `src/prevue/engines/` |
| `comments.py` | GitHub issue comments API | `_upsert_marker_comment` scan + edit/create | ✓ WIRED | `get_issue_comments()` → `edit` or `create_issue_comment` |
| `diff.py` | PyGithub REST | `get_authenticated_pull` → `pr.get_files()` | ✓ WIRED | No checkout anywhere in `src/` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `fetch_diff()` | `DiffBundle.files` | `pr.get_files()` REST payload | Yes — fixture maps real paths/patches | ✓ FLOWING |
| `CopilotCliAdapter.review` | `ReviewResult.summary_markdown` | Copilot CLI stdout | Yes — subprocess output mapped (tested with mock stdout) | ✓ FLOWING |
| `upsert_sticky` | comment body | `render_body(result, ...)` | Yes — engine prose + metadata sections | ✓ FLOWING |
| `load_pr_context` | fork detection fields | `GITHUB_EVENT_PATH` JSON | Yes — fork fixture drives guard test | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `uv run pytest -q` | 113 passed in 0.66s | ✓ PASS |
| Phase 1 targeted tests | `uv run pytest tests/test_diff.py tests/test_copilot_adapter.py tests/test_comments.py tests/test_workflow_yaml.py tests/test_fork_guard.py tests/test_review_flow.py -q` | 57 passed in 0.63s | ✓ PASS |
| D-09 fail-closed | `uv run pytest tests/test_review_flow.py::test_engine_failure_propagates_without_upsert -q` | 1 passed | ✓ PASS |
| CLI non-zero on engine failure | `main(['review'])` with mocked `EngineFailure` | exit code 1 | ✓ PASS |
| No `pull_request_target` in workflows | `grep pull_request_target .github/workflows/` | no matches | ✓ PASS |
| No `secrets: inherit` in workflows | `grep 'secrets: inherit' .github/workflows/` | no matches | ✓ PASS |
| Subprocess only in engine adapter | `grep subprocess src/` | single hit: `engines/copilot_cli.py` | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no phase-declared probes or `scripts/*/tests/probe-*.sh` for Phase 1.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DIFF-01 | 01-04, 01-06, 01-07 | Fetch diff + changed-file metadata via GitHub API; no untrusted checkout | ✓ SATISFIED | `diff.py`, `client.py`, `test_diff.py`, workflow no PR-head ref |
| ENGN-01 | 01-03, 01-05, 01-06 | Pluggable adapter: ReviewRequest → ReviewResult with findings list | ✓ SATISFIED | `models.py`, `base.py`, `EngineAdapter` ABC; findings empty in v1 per D-02 |
| ENGN-02 | 01-01, 01-05, 01-07 | Copilot CLI headless; auth via `COPILOT_GITHUB_TOKEN`; minimal tool posture | ✓ SATISFIED | stdin + `-s --no-ask-user` (documented ARG_MAX deviation from `-p`); no `--allow-tool`; PAT prefix guard |
| OUTP-01 | 01-04, 01-06, 01-07 | Sticky summary comment updated in place | ✓ SATISFIED | `MARKER` upsert; sectioned body; edit-in-place tests |
| SECR-01 | 01-02, 01-06, 01-07 | `pull_request` only; fork unsupported; least privilege | ✓ SATISFIED | `review.yml`, README, fork guard, actionlint + zizmor in `ci.yml` |

No orphaned Phase 1 requirements — all five IDs appear in plan frontmatter and are implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | No TBD/FIXME/stub markers in Phase 1 source files |

Scanned: `src/prevue/github/*`, `src/prevue/engines/*`, `src/prevue/models.py`, `src/prevue/review.py`, `src/prevue/cli.py`, `.github/workflows/*`. No `pull_request_target`, no `secrets: inherit`, no subprocess outside engine adapter.

### Human Verification Required

None for phase closure — automated tests cover all observable Phase 1 truths. Live E2E (PR #2, Actions run 27378511750) and UAT (8 passed, 1 fork skipped per `01-UAT.md`) provide supplementary confirmation but were not copied into this report.

### Gaps Summary

No blocking gaps. Phase 1 walking skeleton goal achieved:

- PR-triggered Actions workflow runs `prevue review` with minimal permissions and pinned dependencies
- Diff fetched exclusively via GitHub REST API — no PR-head checkout in analysis path
- Copilot CLI adapter runs headless with prompt-injection-safe diff-only input and fail-closed error handling
- Sticky summary comment upserts in place via HTML marker; engine failures leave prior comment untouched and fail the job
- Fork PRs detected and skipped with documented unsupported message
- 113/113 tests pass; 57/57 Phase 1 targeted tests pass

Intentionally out of scope (deferred, not gaps): structured findings validation, verdict/merge gate, inline comments, consumer config from base ref, reusable-workflow consumer packaging.

---

_Verified: 2026-06-12T14:30:02Z_  
_Verifier: Claude (gsd-verifier)_
