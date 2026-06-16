---
phase: 08-incremental-stateful-review-lifecycle
verified: 2026-06-16T21:30:00Z
status: passed
score: 16/16
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 16/16
  gaps_closed:
    - "Sticky Findings table diverges from live inline on engine rephrase-at-same-line (LIFE-02 major)"
    - "INLINE_MARKER renders raw HTML in inline comments (cosmetic)"
    - "cursor-cli runs from .prevue cwd — framework context leaks into Review prose (minor)"
    - "Same-SHA noop re-run still executes full workflow install (~40s) (minor)"
    - "Sticky Review prose scoped to incremental diff only — omits carried findings context (minor)"
  gaps_remaining: []
  regressions: []
---

# Phase 8: Incremental & Stateful Review Lifecycle Verification Report

**Phase Goal:** Make PR review incremental and stateful across pushes — scope classification and review to the diff since the last-reviewed SHA stored in the sticky marker (LIFE-01); carry forward and dedupe prior findings so incremental scoping never drops still-valid comments (LIFE-02); and auto-resolve outdated inline threads when their underlying lines change (LIFE-04).

**Verified:** 2026-06-16T21:30:00Z
**Status:** passed
**Re-verification:** Yes — regression check after gap-closure pass; all 5 prior gaps remain closed; UAT 14/14 confirmed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LIFE-01: Classification and review scoped to diff since last-reviewed marker SHA | ✓ VERIFIED | `review.py:283-285` `parse_marker_sha` + `decide_scope`; `fetch_diff_in_scope` at incremental path; UAT tests 1-2 pass |
| 2 | Marker head SHA round-trips; legacy head-less marker → None (first-run full) | ✓ VERIFIED | `comments.py:46-47` `parse_marker_sha`; marker format `MARKER_WITH_SHA` line 21 |
| 3 | `decide_scope`: incremental only when `ahead` + `merge_base==lastSHA`; full on diverged/no marker; noop on identical | ✓ VERIFIED | `diff.py:9-31`; compare fixtures present; UAT tests 4, 7 pass |
| 4 | Force-push never produces bogus incremental range — falls back to full | ✓ VERIFIED | `decide_scope` returns `"full"` when not ahead-with-merge-base; UAT test 7 pass |
| 5 | Identical re-run is noop: marker/check refreshed, engine not re-invoked | ✓ VERIFIED | `_finish_noop_review` at `review.py:204-228`; scope `"noop"` branch at 287-288; UAT test 4 pass |
| 6 | LIFE-02: Fingerprint identity = `sha(path\|normalize(title))`; line/severity/suggestion excluded | ✓ VERIFIED | `fingerprint.py:10-19`; path+title only in payload |
| 7 | Prior comments on out-of-scope files left untouched on incremental run | ✓ VERIFIED | `post_inline_review` stale filter scoped by `in_scope_paths` at `comments.py:705-710`; UAT test 3/9 pass |
| 8 | Same-fingerprint/location match keeps inline comment unless severity escalates | ✓ VERIFIED | `post_inline_review:722-728` skip edit when no escalation; `test_escalation_equal_severity_skips_edit` |
| 9 | Known-issues list: in-scope priors only, capped at `max_known_issues`, fenced UNTRUSTED DATA | ✓ VERIFIED | `_build_known_issues_items` `review.py:190-201`; `build_known_issues_block` `prompt.py:81-97` |
| 10 | Prior findings + severities re-derived from live comments for gate open-set | ✓ VERIFIED | `derive_prior_findings` wired at `review.py:469`; `_derive_prior_findings_with_threads` |
| 11 | Gate verdict over union(new + carried-unresolved) − resolved — false-green blocked | ✓ VERIFIED | `apply_gate(_open_set_findings(...))` at `review.py:582-583`; UAT test 5 pass |
| 12 | LIFE-04: Outdated in-scope finding attempts thread RESOLVE not delete | ✓ VERIFIED | `resolve_outdated_prior_findings` at `comments.py:194+`; wired at `review.py:570-571`; UAT test 6 pass |
| 13 | GraphQL 403/FORBIDDEN logged and skipped — never fails the run | ✓ VERIFIED | `resolve_review_thread` best-effort at `graphql.py:128-135`; `test_resolve_review_thread_forbidden_returns_false` |
| 14 | Config knobs `incremental`/`resolve_outdated`/`max_known_issues` exist with defaults + `extra=forbid` | ✓ VERIFIED | `gate.py:21,27-29`; UAT test 8 pass |
| 15 | Minimal workflow permissions unchanged; consumer docs document 403 caveat + knobs | ✓ VERIFIED | `prevue-review.yml:29-32`; `docs/consumer-setup.md:97-118` |
| 16 | Sticky Findings table matches live open inline comments on incremental carry-forward | ✓ VERIFIED | `_open_set_findings` rephrase fix `review.py:166-187`; `test_open_set_dedupes_carried_prior_at_same_line_as_current`; UAT test 9 pass |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/fingerprint.py` | D-04 identity pure unit | ✓ VERIFIED | Exists, substantive, tested |
| `src/prevue/github/diff.py` | `decide_scope` + incremental fetch | ✓ VERIFIED | Wired from `review.py` |
| `src/prevue/github/comments.py` | Marker SHA, carry-forward, resolve, prior re-derivation, GFM marker, incremental disclaimer | ✓ VERIFIED | `INLINE_MARKER` line 23; `render_body` scope/disclaimer lines 498-504; `upsert_sticky` forwards params 590-609 |
| `src/prevue/github/graphql.py` | GraphQL thread fetch/resolve transport | ✓ VERIFIED | Best-effort resolve; fixtures present |
| `src/prevue/github/positions.py` | Region-changed hunk overlap | ✓ VERIFIED | Used by `finding_region_changed` import in comments |
| `src/prevue/gate.py` | Open-set gate + config knobs | ✓ VERIFIED | Defaults + `extra=forbid` |
| `src/prevue/review.py` | Incremental orchestration seam + rephrase-at-same-line fix | ✓ VERIFIED | Full orchestration path lines 279-583 |
| `src/prevue/engines/cursor_cli.py` | cwd isolation to consumer repo | ✓ VERIFIED | `PREVUE_CONSUMER_ROOT` lines 45-46,54 |
| `src/prevue/engines/prompt.py` | Known-issues UNTRUSTED fence | ✓ VERIFIED | `~~~UNTRUSTED DATA` fence lines 93-96 |
| `tests/fixtures/compare_*.json` | Compare API mocks | ✓ VERIFIED | 3 fixtures |
| `tests/fixtures/graphql_*.json` | GraphQL mocks | ✓ VERIFIED | 3 fixtures |
| `.github/workflows/prevue-review.yml` | Minimal permissions + pre-flight noop gate | ✓ VERIFIED | `preflight` id at 67-68; install gated line 98; `per_page=100` line 82 |
| `docs/consumer-setup.md` | Consumer knobs + scope caveat | ✓ VERIFIED | Knobs + 403 caveat documented |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `review.py` | `parse_marker_sha` / `decide_scope` | read sticky → classify scope | ✓ WIRED | Lines 282-285 |
| `review.py` | `fetch_diff_in_scope` | incremental in-scope file set | ✓ WIRED | Called when scope incremental |
| `review.py` | `derive_prior_findings` | re-derive priors before engine + gate | ✓ WIRED | Line 469 |
| `review.py` | `build_prompt` known_issues | capped list injection | ✓ WIRED | `_build_known_issues_items` |
| `review.py` | `resolve_outdated_prior_findings` | before `apply_gate` | ✓ WIRED | Lines 570-571 |
| `review.py` | `apply_gate(_open_set_findings(...))` | union minus resolved fingerprints | ✓ WIRED | Lines 582-583 |
| `review.py` | `upsert_sticky` → findings table | open-set placed findings | ✓ WIRED | Rephrase fix keeps sticky/inline titles aligned |
| `comments.py` | `post_inline_review` skip-edit | same location, no severity escalation | ✓ WIRED | Lines 722-728 |
| `comments.py` | `resolve_review_thread` | outdated → GraphQL resolve | ✓ WIRED | Via `resolve_outdated_prior_findings` |
| `cursor_cli.py` | consumer repo context | `cwd=PREVUE_CONSUMER_ROOT` | ✓ WIRED | Contract tests pass |
| `prevue-review.yml` | preflight → engine CLI install gate | `noop != 'true'` | ✓ WIRED | YAML guard tests pass |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `review.py` scope decision | `last_sha` | `parse_marker_sha(sticky_body)` | Yes | ✓ FLOWING |
| `review.py` in-scope paths | `in_scope_paths` | compare API filenames | Yes | ✓ FLOWING |
| `review.py` open-set gate | `carried` priors | `derive_prior_findings(pr)` | Yes | ✓ FLOWING |
| Sticky Findings table | `gate.placed[].finding.title` | `_open_set_findings` rephrase contract | Yes | ✓ FLOWING |
| Inline comments on rephrase | prior comment body | skip-edit in `post_inline_review` | Yes | ✓ FLOWING |
| Sticky Review prose | `result.summary_markdown` | engine + deterministic disclaimer | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gap #1: open-set keeps carried title on rephrase-at-same-line | `uv run pytest tests/test_review_flow.py::test_open_set_dedupes_carried_prior_at_same_line_as_current -q` | 1 passed | ✓ PASS |
| Gap #1: true-duplicate still drops prior (current wins) | `uv run pytest tests/test_review_flow.py::test_open_set_drops_true_duplicate_at_same_line -q` | 1 passed | ✓ PASS |
| Gap #2: GFM marker + legacy HTML detection | `uv run pytest tests/test_comments.py::TestInlineMarkerDetection -q` | 6 passed | ✓ PASS |
| Gap #5: incremental disclaimer in render_body | `uv run pytest tests/test_comments.py::TestRenderBodyIncrementalDisclaimer -q` | 6 passed | ✓ PASS |
| Gap #3: cursor-agent cwd=PREVUE_CONSUMER_ROOT or None | `uv run pytest tests/test_engine_contract.py::test_cursor_invoked_with_consumer_cwd_when_env_set tests/test_engine_contract.py::test_cursor_invoked_with_none_cwd_when_env_unset -q` | 2 passed | ✓ PASS |
| Gap #4: preflight precedes install, install gated on noop | `uv run pytest tests/test_workflow_yaml.py::test_preflight_noop_step_precedes_engine_install_in_reusable tests/test_workflow_yaml.py::test_engine_install_gated_on_preflight_noop_in_reusable -q` | 2 passed | ✓ PASS |
| Full suite regression | `uv run pytest tests/ -q` | 479 passed, 0 failed | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` declared for this phase.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| LIFE-01 | 08-03, 08-06, 08-07, 08-10 | Incremental review since last-reviewed SHA in sticky marker | ✓ SATISFIED | `decide_scope` + preflight noop; UAT 1,2,4,7,13 pass |
| LIFE-02 | 08-01, 08-04, 08-05, 08-06, 08-08, 08-09 | Comment dedupe + carry-forward; never drop still-valid comments | ✓ SATISFIED | `_open_set_findings` rephrase fix; GFM marker; UAT 3,5,9,10,11 pass |
| LIFE-04 | 08-02, 08-04, 08-05, 08-06, 08-07 | Auto-resolve outdated inline threads when lines change | ✓ SATISFIED | GraphQL resolve best-effort; UAT 6 pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No TBD/FIXME/XXX in `src/prevue/` production paths |

### UAT Status (08-UAT.md)

| Metric | Value |
|--------|-------|
| Total tests | 14 |
| Passed | 14 |
| Issues | 0 |
| Round-1 major gap (test 3) | Fixed and re-verified in test 9 |

Supplemental gap-closure tests 9-14 confirm all five prior verification gaps remain closed on live PR #24 and workflow run 27572927811.

### Human Verification Required

None. UAT 14/14 complete; all gap-closure behaviors covered by unit tests and live sandbox runs documented in `08-UAT.md`.

### Gaps Summary

No gaps. Re-verification confirms all 16 must-haves hold in code, wiring, and tests. Prior gap-closure fixes (08-08 rephrase open-set, 08-09 GFM marker + incremental disclaimer, 08-10 preflight noop gate) show no regressions.

---

_Verified: 2026-06-16T21:30:00Z_
_Verifier: Claude (gsd-verifier) — re-verification regression pass_
