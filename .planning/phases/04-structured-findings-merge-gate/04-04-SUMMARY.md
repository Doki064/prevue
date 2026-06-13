---
phase: 04-structured-findings-merge-gate
plan: 04
subsystem: api
tags: [pygithub, markdown-rendering, github-reviews-api, gate-result, injection-hardening]

requires:
  - phase: 04-03
    provides: GateResult, verdict_title/severity_counts_line/thresholds_line, apply_gate pipeline
provides:
  - D-21 uniform inline comment template (Python-rendered)
  - D-24 findings table and D-25 collapsed details in sticky
  - D-26 sticky section order with gate-aware Verdict mirror (D-07)
  - D-20 single batched COMMENT create_review via post_inline_review
  - Upsert functions return IssueComment for D-10 check-run linking
affects: [04-05, run_review wiring, check-run sticky link]

tech-stack:
  added: []
  patterns:
    - "Engine text never controls layout — Python owns all consumer-visible markdown"
    - "4-backtick fences with triple-backtick escape for untrusted suggestions"
    - "Table cell pipe/newline escaping for markdown-injection mitigation"
    - "One-way github→gate import for verdict strings (no drift from check run)"

key-files:
  created: []
  modified:
    - src/prevue/github/comments.py
    - tests/test_comments.py

key-decisions:
  - "Plain 4-backtick suggestion fences in v1 — GitHub one-click suggestion blocks deferred to CUST-02"
  - "post_inline_review uses default commit_id — concurrency group cancels superseded runs"
  - "create_review failure returns False with sanitized stderr — never crashes the run"

patterns-established:
  - "render_inline_comment: single uniform template for inline + details blocks"
  - "render_body(gate=None) preserves Phase 3 byte-identical output for skip/transition paths"

requirements-completed: [OUTP-02, OUTP-03, NOIS-02, NOIS-03]

duration: 25min
completed: 2026-06-13
---

# Phase 4 Plan 4: Findings Rendering + Batched Inline Review Summary

**Python-owned D-21 inline template, D-26 sticky with reconciling findings index, and D-20 single batched COMMENT review POST — all verdict strings imported from gate.py**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-13T06:15:00Z
- **Completed:** 2026-06-13T06:40:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Uniform inline-comment template with severity badges, optional escape-hardened suggestion fence, and Prevue footer
- Sticky restructured: Verdict (gate helpers) → Review → Findings table → collapsed details → Metadata with findings accounting
- `post_inline_review` posts one atomic COMMENT review, skips when empty, swallows GithubException safely
- Upsert functions return the created/edited comment object for 04-05 check-run linking

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: Uniform inline-comment template + escaping helpers (D-21)** — `cc54cf1` (test), `cfe805b` (feat)
2. **Task 2: Sticky restructure — Verdict, findings table, details, metadata (D-07/D-23/D-24/D-25/D-26)** — `b4af705` (test), `3daea0a` (feat)
3. **Task 3: post_inline_review — single batched COMMENT review (D-20)** — `5e51cda` (test), `f89301c` (feat)

## Files Created/Modified

- `src/prevue/github/comments.py` — SEVERITY_BADGES, PLACEMENT_BADGES, render_inline_comment, render_findings_table, render_finding_details, gate-aware render_body, post_inline_review; upsert return plumbing
- `tests/test_comments.py` — TestInlineTemplate, TestStickyWithGate, TestPostInlineReview (35 tests total, all green)

## Decisions Made

- Plain fenced suggestions (not ```suggestion blocks) per D-21 v1 scope — CUST-02 deferred
- Default commit_id on create_review acceptable because workflow concurrency cancels superseded runs
- Thresholds line appears in both Verdict section and Metadata per D-26 accretion spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed uniform-template test comparison**
- **Found during:** Task 1 (GREEN)
- **Issue:** Test compared findings with/without suggestion — skeletons legitimately differ
- **Fix:** Compare two findings both without suggestion
- **Files modified:** tests/test_comments.py
- **Committed in:** cfe805b

**2. [Rule 1 - Bug] Fixed pipe-escape table column assertion**
- **Found during:** Task 2 (GREEN)
- **Issue:** Naive `split("|")` on escaped `\|` cell still breaks into extra columns
- **Fix:** Assert full expected table row string instead
- **Files modified:** tests/test_comments.py
- **Committed in:** 3daea0a

---

**Total deviations:** 2 auto-fixed (2 bugs in test assertions)
**Impact on plan:** Test-only fixes; no implementation scope change.

## Issues Encountered

None — gsd-tools CLI unavailable in executor environment; STATE/ROADMAP updated manually.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Rendering surface complete — 04-05 can wire `post_inline_review`, gate-aware `upsert_sticky`, and check run creation in `run_review`
- Upsert return values ready for D-10 sticky URL → check-run `details_url` linking

## Self-Check: PASSED

- FOUND: src/prevue/github/comments.py
- FOUND: tests/test_comments.py
- FOUND: .planning/phases/04-structured-findings-merge-gate/04-04-SUMMARY.md
- FOUND: cc54cf1, cfe805b, b4af705, 3daea0a, 5e51cda, f89301c

---
*Phase: 04-structured-findings-merge-gate*
*Completed: 2026-06-13*
