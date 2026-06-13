---
phase: 04-structured-findings-merge-gate
verified: 2026-06-13T12:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
deferred:
  - truth: "run_review loads consumer review thresholds from .github/prevue.yml trusted base ref at runtime"
    addressed_in: "Phase 5"
    evidence: "Phase 5 success criteria: 'Run behavior is configurable via workflow inputs and a .github/prevue.yml read from the trusted base ref'; run_review calls load_review_config() with no consumer_path; gate.py documents Phase 5 wiring (04-05-SUMMARY)"
human_verification:
  - test: "Open or refresh the sandbox test PR; confirm inline comments land on changed diff lines in the GitHub UI"
    expected: "💬 inline comments appear on correct changed lines; unplaceable findings visible only in sticky summary index"
    why_human: "OUTP-02 Assumption A4 (LEFT-side batched review endpoint) and real diff-line placement require live GitHub UI confirmation"
  - test: "Confirm prevue/review check run appears in the PR merge box and verdict mirrors sticky Verdict section"
    expected: "Check run selectable as required check; conclusion success/neutral/failure matches sticky; blocking only when min_severity_to_fail configured"
    why_human: "OUTP-03 Assumption A2 (GITHUB_TOKEN check-suite grouping) and merge-gate UX require live PR inspection"
---

# Phase 4: Structured Findings & Merge Gate — Verification Report

**Phase Goal:** Reviews produce trustworthy, bounded output — schema-validated findings as correctly-placed inline comments, severity-filtered, capped by a hard budget, with a pass/fail/neutral check that never falsely blocks

**Verified:** 2026-06-13T12:00:00Z  
**Status:** human_needed  
**Re-verification:** No — initial verification

## User Flow Coverage (MVP Mode)

| Step | Expected | Evidence | Status |
|------|----------|----------|--------|
| Engine returns prose + JSON findings | Schema-validated `Finding` list extracted from last ```json fence | `parsing.py` `extract_json_fence`/`validate_findings`; `test_findings_parsing.py` (9 tests) | ✓ VERIFIED |
| Parse failure | One retry, then degrade — prose-only, neutral check, no crash | `copilot_cli.py` retry loop + `_degraded_result`; `test_run_review_degraded_neutral_check_no_inline` | ✓ VERIFIED |
| Valid findings with placeable lines | Batched inline COMMENT review on diff lines | `post_inline_review` → `create_review(event="COMMENT")`; `test_run_review_with_findings_posts_inline_then_sticky_then_check` | ✓ VERIFIED |
| Unplaceable findings | Fall back to sticky summary, never snap or drop | `apply_gate` `position-fallback`; `test_invalid_position_gets_position_fallback` | ✓ VERIFIED |
| Severity filtering | Sub-threshold findings summary-only; counts include ALL | `apply_gate` threshold + `conclude` over all findings; gate tests | ✓ VERIFIED |
| Comment budget | Inline count ≤ `max_inline_comments` | `apply_gate` budget cap; `test_budget_cap_only_first_n_placeable_inline` | ✓ VERIFIED |
| Merge gate | `prevue/review` check on head SHA: success/neutral/failure | `checks.py` `conclude_review_check`; `CHECK_NAME == "prevue/review"` | ✓ VERIFIED |
| Never false-block | Degraded → neutral; default findings → neutral; fork → no check | `conclude(degraded=True)` → neutral; fork test; degraded E2E | ✓ VERIFIED |
| Outcome: trustworthy bounded review output | Full pipeline wired inline → sticky → check | `review.py` lines 77–98; 205 tests green | ✓ VERIFIED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Engine output schema-validated with retry-then-degrade; parse failure → neutral check + summary-only, never crash or red X (ENGN-03) | ✓ VERIFIED | `parsing.py` strict salvage; `copilot_cli.py` single retry then `_degraded_result(degraded=True)`; `EngineFailure` only on auth/timeout/exit/empty; `test_run_review_degraded_neutral_check_no_inline` asserts neutral check, no inline, engine hard-fail raises without check |
| 2 | Inline comments on correct diff lines; invalid positions fall back to summary (OUTP-02) | ✓ VERIFIED | `positions.py` unidiff hunk sets incl. header synthesis; `apply_gate` marks `position-fallback`; `post_inline_review` batched `create_review`; position + comment tests green |
| 3 | Findings carry severity; consumer can configure min-severity thresholds (NOIS-02) | ✓ VERIFIED | `Finding.severity` Literal; `ReviewConfig` + `load_review_config` fail-closed (`extra="forbid"`, unknown severity raises); unit tests with fixture prevue.yml; runtime trusted-base-ref path deferred Phase 5 |
| 4 | Check reports pass/fail/neutral usable as merge gate; blocking opt-in (OUTP-03) | ✓ VERIFIED | `gate.conclude` ladder: failure > neutral > success; `checks.py` `create_check_run(conclusion=gate.conclusion)` on `diff.head_sha`; workflow `checks: write`; `test_minimal_permissions` exact-equality pin |
| 5 | No review posts more inline comments than hard budget (NOIS-03) | ✓ VERIFIED | Default `max_inline_comments=10`; `apply_gate` severity-rank then emission-order allocation; unplaceable never consumes slot; budget tests in `test_gate.py` |

**Score:** 5/5 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `run_review` loads consumer `review:` thresholds from `.github/prevue.yml` trusted base ref at runtime | Phase 5 | `review.py:46` calls `load_review_config()` with no path; `gate.py:29-41` accepts `consumer_path` for tests/fixtures; Phase 5 WKFL-03 success criterion |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/parsing.py` | Fence extraction + strict salvage (ENGN-03) | ✓ VERIFIED | 44 lines; last-fence wins; `model_validate(..., strict=True)` |
| `src/prevue/engines/copilot_cli.py` | JSON contract, rubric, retry-degrade loop | ✓ VERIFIED | `OUTPUT_CONTRACT`, `_build_retry_prompt`, separate `_degraded_result` vs `EngineFailure` |
| `src/prevue/models.py` | Finding severity Literal; ReviewResult.degraded/dropped_findings | ✓ VERIFIED | Additive defaults preserve adapter contract |
| `src/prevue/github/positions.py` | unidiff-backed commentable line sets | ✓ VERIFIED | 39 lines; header synthesis; `build_valid_lines` |
| `src/prevue/gate.py` | ReviewConfig, conclude ladder, apply_gate, verdict helpers | ✓ VERIFIED | 170 lines; D-14 counts over ALL findings before partition |
| `src/prevue/github/comments.py` | Uniform template, table, details, batched review | ✓ VERIFIED | 243 lines; imports `verdict_title` from gate; `post_inline_review` crash-proof |
| `src/prevue/github/checks.py` | Check run on head SHA | ✓ VERIFIED | 66 lines; `CHECK_NAME = "prevue/review"`; skip + review conclude |
| `src/prevue/github/client.py` | `get_repo` for Checks API | ✓ VERIFIED | `get_repo(ctx)` exported |
| `src/prevue/review.py` | Full post-engine pipeline | ✓ VERIFIED | config → engine → gate → inline → sticky → check; skip/fork/degraded paths |
| `.github/workflows/review.yml` | `checks: write` permission | ✓ VERIFIED | Exact minimal block pinned by test |
| `pyproject.toml` | unidiff 0.7.x pinned | ✓ VERIFIED | `"unidiff==0.7.*"`; import check passes |
| `tests/test_findings_parsing.py` | ENGN-03 parsing contracts | ✓ VERIFIED | 9 tests green |
| `tests/test_gate.py` | NOIS-02/03 + OUTP-03 logic | ✓ VERIFIED | 30 tests green |
| `tests/test_positions.py` | OUTP-02 hunk validity | ✓ VERIFIED | 8 tests green |
| `tests/test_comments.py` | OUTP-02 rendering + D-20 batch POST | ✓ VERIFIED | 35 tests green |
| `tests/test_checks.py` | OUTP-03 check payloads | ✓ VERIFIED | 6 tests green |
| `tests/test_review_flow.py` | End-to-end orchestration | ✓ VERIFIED | 8 tests incl. degraded/skip/fork/config-order |
| `tests/test_copilot_adapter.py` | ENGN-03 adapter slice | ✓ VERIFIED | 34 tests green |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `copilot_cli.py` | `parsing.py` | `extract_json_fence`, `validate_findings` in `review()` | ✓ WIRED | Lines 11, 192–209 |
| `parsing.py` | `models.py` | `Finding.model_validate(item, strict=True)` | ✓ WIRED | Line 40 |
| `review.py` | `gate.py` | `load_review_config` before fetch; `apply_gate` after engine | ✓ WIRED | Lines 46, 78–84 |
| `review.py` | `positions.py` | `build_valid_lines(reduced.files)` | ✓ WIRED | Line 77 |
| `review.py` | `comments.py` | `post_inline_review` → `upsert_sticky` | ✓ WIRED | Lines 85–92; order test confirms inline→sticky→check |
| `review.py` | `checks.py` | `conclude_review_check(get_repo(ctx), diff.head_sha, gate)` | ✓ WIRED | Lines 93–98 |
| `comments.py` | `gate.py` | `verdict_title`, `severity_counts_line`, `thresholds_line` | ✓ WIRED | Line 11 import; D-07 single source |
| `comments.py` | PyGithub | `pr.create_review(event="COMMENT", comments=[...])` | ✓ WIRED | Line 234 |
| `positions.py` | unidiff | `PatchSet` with synthesized headers | ✓ WIRED | Lines 5–7, 17 |
| `checks.py` | `gate.py` | Verdict helpers in check output | ✓ WIRED | Lines 11, 18–30 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `apply_gate` | `gate.inline` | Engine `ReviewResult.findings` filtered by severity, position, budget | Yes — from validated findings + diff hunks | ✓ FLOWING |
| `post_inline_review` | `comments[]` | `gate.inline` findings | Yes — path/line/side from Finding model | ✓ FLOWING |
| `render_body` | Verdict section | `GateResult` from `apply_gate` | Yes — conclusion/counts/thresholds from real findings | ✓ FLOWING |
| `conclude_review_check` | `conclusion` | `gate.conclusion` from `conclude()` | Yes — derived from findings + degraded flag | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green (205 tests) | `uv run pytest -q` | `205 passed in 0.80s` | ✓ PASS |
| unidiff importable | `uv run python -c "from unidiff import PatchSet"` | exit 0 | ✓ PASS |
| Degraded → neutral, no inline | `uv run pytest tests/test_review_flow.py::test_run_review_degraded_neutral_check_no_inline -q` | 1 passed | ✓ PASS |
| Budget cap enforced | `uv run pytest tests/test_gate.py::TestApplyGate::test_budget_cap_only_first_n_placeable_inline -q` | 1 passed | ✓ PASS |
| Retry then salvage | `uv run pytest tests/test_copilot_adapter.py -k "retry or salvage or degraded" -q` | multiple passed | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `probe-*.sh` declared in phase plans or conventional scripts path.

### Nyquist Validation (04-VALIDATION.md Per-Task Map)

All 13 tasks verified green via documented automated commands:

| Task ID | Automated Command | Status |
|---------|-------------------|--------|
| 04-01-01 | `uv run python -c "from unidiff import PatchSet"` | ✅ green |
| 04-01-02 | Phase 4 test scaffolds exist and pass | ✅ green |
| 04-02-01 | `pytest tests/test_findings_parsing.py tests/test_models.py` | ✅ green (21 passed) |
| 04-02-02 | `pytest tests/test_copilot_adapter.py` | ✅ green (34 passed) |
| 04-02-03 | `pytest tests/test_copilot_adapter.py tests/test_findings_parsing.py` | ✅ green (43 passed) |
| 04-03-01 | `pytest tests/test_positions.py` | ✅ green (8 passed) |
| 04-03-02 | `pytest tests/test_gate.py -k "ReviewConfig or Conclude"` | ✅ green (13 passed) |
| 04-03-03 | `pytest tests/test_gate.py tests/test_positions.py` | ✅ green (38 passed) |
| 04-04-01 | `pytest tests/test_comments.py -k InlineTemplate` | ✅ green (6 passed) |
| 04-04-02 | `pytest tests/test_comments.py` | ✅ green (35 passed) |
| 04-04-03 | `pytest tests/test_comments.py` | ✅ green (35 passed) |
| 04-05-01 | `pytest tests/test_checks.py` | ✅ green (6 passed) |
| 04-05-02 | `pytest tests/test_review_flow.py` | ✅ green (8 passed) |
| 04-05-03 | `pytest tests/test_workflow_yaml.py` | ✅ green (11 passed) |

Note: `04-VALIDATION.md` task status column still shows ⬜ pending — documentation lag only; all commands pass in verifier run.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENGN-03 | 04-02, 04-05 | Schema-validated output; retry-then-degrade; parse → neutral never crash/block | ✓ SATISFIED | `parsing.py`, `copilot_cli.py` retry/degrade; degraded E2E neutral check |
| OUTP-02 | 04-03, 04-04, 04-05 | Inline comments via Reviews API; position-validated; summary fallback | ✓ SATISFIED | `positions.py`, `apply_gate`, `post_inline_review`, uniform template |
| OUTP-03 | 04-03, 04-05 | pass/fail/neutral merge gate; blocking opt-in | ✓ SATISFIED | `gate.conclude`, `checks.py`, workflow `checks: write` |
| NOIS-02 | 04-03 | Severity thresholds configurable | ✓ SATISFIED | `ReviewConfig`, `load_review_config`; fail-closed validation in unit tests |
| NOIS-03 | 04-03, 04-05 | Hard per-review comment budget | ✓ SATISFIED | `max_inline_comments` default 10; budget allocation tests |

No orphaned requirements — all five Phase 4 IDs appear in plan frontmatter and have implementation evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None | — | No TBD/FIXME/XXX/stub markers in phase source files |

### Human Verification Required

### 1. Live GitHub inline comment placement

**Test:** Open or refresh the sandbox test PR; inspect inline comments on changed lines  
**Expected:** Comments on correct diff lines; unplaceable findings only in sticky index with `position-fallback` badge  
**Why human:** Batched Reviews API LEFT/RIGHT side behavior and visual line alignment cannot be verified by unit mocks alone (04-VALIDATION.md Assumption A4)

### 2. Check run as merge gate

**Test:** Confirm `prevue/review` check in PR merge box; compare check conclusion to sticky Verdict section  
**Expected:** Check selectable as required check; success/neutral/failure mirrors sticky; neutral never blocks by default  
**Why human:** GITHUB_TOKEN check-suite grouping and branch-protection UX require live PR (04-VALIDATION.md Assumption A2)

### Gaps Summary

No automated gaps blocking phase goal. All five roadmap success criteria verified in codebase with 205 passing tests and full Nyquist task map green.

**Remaining:** Two manual UAT items (live GitHub UI) documented in `04-VALIDATION.md`. Consumer `prevue.yml` review-threshold loading at runtime intentionally deferred to Phase 5 (same pattern as Phase 2 `load_ruleset` trusted-base-ref wiring).

---

_Verified: 2026-06-13T12:00:00Z_  
_Verifier: Claude (gsd-verifier)_
