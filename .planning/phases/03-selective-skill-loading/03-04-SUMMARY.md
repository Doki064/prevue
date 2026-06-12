---
phase: 03-selective-skill-loading
plan: "04"
subsystem: skills
tags: [tdd, content-quality, lean-floor, D-11, SKIL-02]
dependency_graph:
  requires: ["03-03"]
  provides: ["lean-content-floor-test", "enriched-component-state", "enriched-ci-workflow-hardening"]
  affects: ["tests/test_skills_builtin.py", "src/prevue/skills/frontend/component-state.md", "src/prevue/skills/infra/ci-workflow-hardening.md"]
tech_stack:
  added: []
  patterns: ["committed-secrets depth pattern: opener + backtick anti-patterns + severity framing"]
key_files:
  modified:
    - tests/test_skills_builtin.py
    - src/prevue/skills/frontend/component-state.md
    - src/prevue/skills/infra/ci-workflow-hardening.md
    - .planning/phases/03-selective-skill-loading/03-VALIDATION.md
decisions:
  - "Two-tier lean-floor rubric: baseline >=4 bullets for all 11 skills; strict committed-secrets bar only for THIN_SKILL_KEYS (avoids false positives on already-adequate skills)"
  - "THIN_SKILL_KEYS keyed by bundle/filename (matches select_skills key pattern) — two members: frontend/component-state.md, infra/ci-workflow-hardening.md"
  - "Full depth parity across all 11 skills + token-budget packing deferred to Phase 6 (OUTP-04) as documented in 03-VALIDATION.md"
metrics:
  duration: "~8 minutes"
  completed: 2026-06-12
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 03 Plan 04: Lean Content Floor Test + Skill Enrichment Summary

Closed UAT test 7 (minor): added automated two-tier lean-floor CI guard and enriched the two thinnest built-in skills (`component-state.md`, `ci-workflow-hardening.md`) to match the `committed-secrets.md` depth pattern — imperative opener, backtick-wrapped anti-patterns, explicit **error**/**warning** severity framing.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add lean content-floor test + update validation rubric (RED) | `98cc7ce` | tests/test_skills_builtin.py, 03-VALIDATION.md |
| 2 | Enrich thinnest flagged skills (D-11, GREEN) | `915324e` | frontend/component-state.md, infra/ci-workflow-hardening.md |

---

## What Was Built

**Automated lean-floor test (`test_builtin_skill_content_lean_floor`):**
- Two-tier rubric: baseline ≥4 checklist bullets for all 11 built-in skills; strict bar (`opener` + `backtick_lines >= 2` + `has_severity`) for `THIN_SKILL_KEYS` only.
- RED committed before any skill changes (test failed on missing opener/severity in thin skills).
- GREEN after enrichment — 114 tests pass, ruff clean.

**Enriched `frontend/component-state.md`:**
- Added imperative opener: "Review React/Vue component state management and render correctness for anti-patterns..."
- 6 bullets with backtick-wrapped examples: `useState`, `useEffect`, `key={i}`, `useMemo`/`useCallback`, `dangerouslySetInnerHTML`, state-in-render-body.
- Severity split: infinite re-render / missing effect deps → **error**; unnecessary memoization / derived-state duplication → **warning**.
- Closing: "For each finding: cite file + line."

**Enriched `infra/ci-workflow-hardening.md`:**
- Added imperative opener: "Review GitHub Actions workflows for supply-chain integrity, privilege escalation, and secret exposure risks..."
- 6 bullets with workflow-specific backtick examples: `actions/checkout@v4`, `@main`, `permissions: write-all`, `pull_request_target`, `secrets: inherit`, `github.event.*` injection, echoed secrets.
- Severity split: `pull_request_target` + PR-head checkout → **error**; unpinned refs + `secrets: inherit` → **warning**.
- Closing: "For each: cite workflow file + step name."

**Updated `03-VALIDATION.md`:**
- Replaced Manual-Only D-11 row with scoped manual note (full depth parity → Phase 6 OUTP-04).
- Added automated row for `test_builtin_skill_content_lean_floor`.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None. Both enriched skills have full imperative openers, backtick-wrapped concrete anti-patterns, severity framing, and closing action lines. No placeholder text.

---

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

---

## Self-Check

- [x] `tests/test_skills_builtin.py` — exists and committed (`98cc7ce`)
- [x] `src/prevue/skills/frontend/component-state.md` — exists and committed (`915324e`)
- [x] `src/prevue/skills/infra/ci-workflow-hardening.md` — exists and committed (`915324e`)
- [x] `03-VALIDATION.md` — updated and committed (`98cc7ce`)
- [x] `uv run pytest tests/test_skills_builtin.py::test_builtin_skill_content_lean_floor -x` — **1 passed**
- [x] `uv run pytest -q` — **114 passed**
- [x] `uv run ruff check` — **All checks passed**
- [x] No STATE.md or ROADMAP.md modifications

## Self-Check: PASSED
