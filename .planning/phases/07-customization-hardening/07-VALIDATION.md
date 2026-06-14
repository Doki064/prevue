---
phase: 7
slug: customization-hardening
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-14
validated: 2026-06-15
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed Req→Test map lives in `07-RESEARCH.md` § Validation Architecture; this file is the
> execution-time sampling contract with Task IDs wired in by the planner.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-cov 7.1.0 (installed; 351 tests baseline green) |
| **Config file** | `pyproject.toml` (pytest section); `tests/conftest.py` for fixtures |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_pack.py tests/test_tokens.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the touched file's quick run (e.g. `pytest tests/test_pack.py -x -q`)
- **After every plan wave:** Run `.venv/bin/python -m pytest -q` (full 351+ suite green)
- **Before `/gsd-verify-work`:** Full suite green + `ruff check` clean
- **Max feedback latency:** ~30 seconds

---

## Plan → Wave Map

| Plan | Wave | Slice | Type | Autonomous |
|------|------|-------|------|------------|
| 07-01 | 1 | Wave 0 scaffold: RED tests + fixtures + config knobs | tdd | yes |
| 07-02 | 2 | DIFF-03 packing (estimate_tokens, pack_files, partial→neutral, no-fit, disclosure) | tdd | yes |
| 07-03 | 3 | OUTP-04 transparency (token meta, per-bundle ratios, packed-set coverage) | tdd | yes |
| 07-04 | 4 | SKIL-03 consumer skill merge (override/custom/exclude/caps) | tdd | yes |
| 07-05 | 4 | SECR-02 hardening (reassertion, adversarial suite, tool-posture audit, SECURITY.md, docs) | tdd | no (human-verify) |

> Wave 4 runs Plan 04 and Plan 05 in parallel — zero `files_modified` overlap.

---

## Per-Task Verification Map

> Task ID = `{plan}-{wave}-{task#}` of the plan that turns the test GREEN. All RED scaffolds are
> created in Plan 07-01 (Wave 1, Task 3) and `tests/test_config.py` / fixtures in Task 1/2.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-02-2-1 | 07-02 | 2 | DIFF-03 | T-07-04 | greedy pack stops at budget, no mid-file split | unit | `pytest tests/test_pack.py::test_packs_whole_files_to_budget -x` | ✅ | ✅ green |
| 07-02-2-1 | 07-02 | 2 | DIFF-03 | — | security file prioritized over docs file | unit | `pytest tests/test_pack.py::test_priority_security_first -x` | ✅ | ✅ green |
| 07-02-2-2 | 07-02 | 2 | DIFF-03 | T-07-03 | partial coverage → neutral, never success | unit | `pytest tests/test_gate.py::test_partial_coverage_neutral -x` | ✅ extend | ✅ green |
| 07-02-2-3 | 07-02 | 2 | DIFF-03 | T-07-04 | no-file-fits → neutral skip + disclosure | unit/integration | `pytest tests/test_review_flow.py::test_no_fit_neutral_skip -x` | ✅ extend | ✅ green |
| 07-03-3-3 | 07-03 | 3 | DIFF-03 | T-07-07 | paid llm_classify scoped to packed set only | integration | `pytest tests/test_review_flow.py::test_fallback_only_on_packed -x` | ✅ extend | ✅ green |
| 07-02-2-1 | 07-02 | 2 | OUTP-04 | — | estimator bytes/4 | unit | `pytest tests/test_tokens.py::test_estimate_tokens -x` | ✅ | ✅ green |
| 07-03-3-2 | 07-03 | 3 | OUTP-04 | T-07-06 | token line shows review+classify, marked ~est | unit | `pytest tests/test_comments.py::test_token_line_estimated -x` | ✅ extend | ✅ green |
| 07-03-3-2 | 07-03 | 3 | OUTP-04 | T-07-06 | per-bundle ratio line shape | unit | `pytest tests/test_comments.py::test_per_bundle_ratio_line -x` | ✅ extend | ✅ green |
| 07-02-2-3 | 07-02 | 2 | DIFF-03 | T-07-05 | "N files not reviewed" + collapsible disclosure | unit | `pytest tests/test_comments.py::test_skipped_files_disclosure -x` | ✅ extend | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | T-07-10 | override replaces same `bundle/filename` | unit | `pytest tests/test_skills_merge.py::test_override_replaces_builtin -x` | ✅ | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | — | custom adds alongside built-ins | unit | `pytest tests/test_skills_merge.py::test_custom_adds_alongside -x` | ✅ | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | — | non-canonical bundle sorts after the five | unit | `pytest tests/test_skills_merge.py::test_noncanonical_bundle_sorts_last -x` | ✅ | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | T-07-10 | malformed consumer skill → fail-closed | unit | `pytest tests/test_skills_merge.py::test_malformed_consumer_fails -x` | ✅ | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | — | `skills.exclude` removes path regardless of source | unit | `pytest tests/test_skills_merge.py::test_exclude_removes_builtin -x` | ✅ | ✅ green |
| 07-04-4-1 | 07-04 | 4 | SKIL-03 | T-07-09 | over-cap consumer skill → skip + disclose | unit | `pytest tests/test_skills_merge.py::test_over_cap_skips_and_discloses -x` | ✅ | ✅ green |
| 07-05-4-1 | 07-05 | 4 | SECR-02 | T-07-injection-1 | reassertion present after untrusted block | unit | `pytest tests/test_injection_adversarial.py::test_reassertion_after_untrusted -x` | ✅ | ✅ green |
| 07-05-4-1 | 07-05 | 4 | SECR-02 | T-07-injection-3 | classify prompt fences untrusted paths | unit | `pytest tests/test_injection_adversarial.py::test_classify_fences_paths -x` | ✅ | ✅ green |
| 07-05-4-1 | 07-05 | 4 | SECR-02 | T-07-injection-5 | injection cannot force PASS / alter findings | unit | `pytest tests/test_injection_adversarial.py::test_injection_cannot_force_pass -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Sampling continuity: no 3 consecutive tasks lack an `<automated>` verify — every task in
> Plans 01–05 carries an `<automated>` command except the single `checkpoint:human-verify`
> (07-05 Task 2, D-08 tool-posture), which is backed by the automated adversarial suite
> (07-05 Task 1) as its regression guard.

---

## Wave 0 Requirements

> Created in Plan 07-01 (Wave 1).

- [x] `tests/test_pack.py` — DIFF-03 packing (NEW) — 07-01 Task 3
- [x] `tests/test_tokens.py` — OUTP-04 estimator (NEW) — 07-01 Task 3
- [x] `tests/test_skills_merge.py` — SKIL-03 merge/exclude/caps (NEW) — 07-01 Task 3
- [x] `tests/test_injection_adversarial.py` — SECR-02 regression guard (NEW) — 07-01 Task 3
- [x] `tests/fixtures/skills/consumer/` — override + custom + over-cap + malformed + non-canonical fixtures (NEW) — 07-01 Task 2
- [x] Config knobs (`SkillsConfig`, `review.max_input_tokens`, `output_reserve_tokens`) — 07-01 Task 1
- [x] Extend `tests/test_comments.py`, `tests/test_gate.py`, `tests/test_review_flow.py`, `tests/test_config.py`, `tests/test_prompt.py`

*Framework install: none — pytest/responses already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Plan/Task |
|----------|-------------|------------|-------------------|-----------|
| Each adapter's default headless tool posture cannot reach PR metadata/network | SECR-02 (D-08, vector 4) | No `--allow-tool` flags passed today; verifying a CLI's *default* sandbox requires a live run, not a unit assertion | Run each engine in headless mode against a PR-injection fixture; confirm no PR title/body/comment fetch occurs; add a deny flag if any tool reachable | 07-05 Task 2 |

*Automated regression guard (injection fixtures) still covers verdict/findings/label stability (07-05 Task 1).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (sole exception: 07-05 Task 2 human-verify, backed by 07-05 Task 1 automated suite)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (07-01)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned 2026-06-14 · validated 2026-06-15

---

## Validation Audit 2026-06-15

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap filled:** `test_fallback_only_on_packed` — DIFF-03 T-07-07 (llm_classify scoped to packed set only). All 18 automated verify commands green; 1 manual-only (SECR-02 D-08 tool-posture) unchanged.
