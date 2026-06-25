---
status: complete
phase: 09-classification-skill-loading-multi-call-review
source: 09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md, 09-04-SUMMARY.md, 09-05-SUMMARY.md, 09-06-SUMMARY.md
started: 2026-06-22T17:08:19Z
updated: 2026-06-23T12:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. ReviewConfig 5 new caps load with correct defaults
expected: ReviewConfig() produces max_review_calls=1, review_concurrency=1, max_tokens_per_call=120000, max_total_run_tokens=500000, guardrail_skills=[]. No existing tests regress.
result: pass

### 2. Full test suite green after phase 9 changes
expected: uv run pytest tests/ -q → 711 passed, 0 failed. No skips or warnings.
result: pass

### 3. Hybrid selection: keyword floor picks up skills above threshold
expected: select_skills_hybrid returns skills whose keyword_score ≥ 0.15 without an adapter call. test_selection.py 14 tests all pass.
result: pass

### 4. Gap-closure guard: skill from routed bundle loads despite glob miss
expected: A security-bundle skill with applies-to **/auth/** is included in assembled instructions for src/pages/Checkout.jsx (which does NOT match **/auth/**) when the file is classified into the security bundle. test_gap_demo_skill_loaded passes.
result: pass

### 5. Import scanner: Python + JS imports extracted from diff patch
expected: extract_imports + referenced_paths parse Python ast/regex and JS ES-module/require patterns; degrade to [] on unparseable; test_importscan.py 12 tests all pass.
result: pass

### 6. Multi-call split by bundle with import co-location
expected: split_into_calls groups files by bundle, merges groups when one file imports another in a different group, caps at max_review_calls, never silently drops files. test_multicall.py 44 tests pass.
result: pass

### 7. Multi-call execute + fail-soft + merge-dedup
expected: execute_calls absorbs EngineFailure from one call and returns surviving results; merge_findings deduplicates findings by (path, title) keeping higher-severity entry. Integration tests pass.
result: pass

### 8. Whole-run token cap triggers neutral skip on overflow
expected: When classify_tokens + projected_review_tokens > max_total_run_tokens, review exits neutral (no exception, no red check); test_whole_run_cap_overflow_disclosure passes.
result: pass

### 9. Sticky comment: skill_sources shows [routed]/[keyword]/[llm] per skill
expected: render_body with skill_sources dict annotates each skill name in the Skills line with its source tag. test_comments.py::TestRenderBodySkillSourceProvenance 3 tests pass.
result: pass

### 10. Sticky comment: per-call token breakdown on multi-call run
expected: When per_call list has ≥2 entries, render_body emits "Per-call tokens: bundleA NNN · bundleB MMM" line. Single-call (≤1 entry) leaves existing Tokens line unchanged. 3 tests pass.
result: pass

### 11. Sticky comment: prominent budget alert outside collapsed block
expected: run_budget_reached=True renders "Run token budget reached — N file(s) not reviewed" as a visible section BEFORE the Metadata <details> block (not inside it). 5 tests pass.
result: pass

### 12. Live gap closure: routed-bundle skill in real PR sticky comment
expected: Sandbox PR touching src/pages/Checkout.jsx, with security/gap-demo-auth-guard.md skill (applies-to **/auth/**) in .github/prevue/skills/security/, shows sticky Bundles: security; Skills: audit lists gap-demo-auth-guard with [routed] tag; review body references GAP-DEMO-SKILL-LOADED instructions.
result: pass
evidence: "PR #8 (uat/09-gap-closure): files src/pages/Checkout.jsx (frontend, *.jsx) + config/secrets/dummy.txt (security, **/*secret*). Sticky shows: Labels: security, frontend. Bundles: security, frontend. Skills: ... Gap Demo Auth Guard (security, consumer) [routed] ... Skill coverage: security 3/4 loaded. Gap-closure fired: skill has applies-to **/auth/**, no auth/ file in PR, but security bundle was routed so skill loaded via escalation. Consumer skill tagged (security, consumer) confirming SKIL-04 base-ref loading."

### 13. Live multi-call: two-bundle PR shows per-call token breakdown in sticky
expected: PR with files in data + security bundles, prevue.yml max_review_calls: 2; sticky shows Per-call tokens: data NNN · security MMM; exactly one check run and one sticky comment; merged findings contain no duplicate (path, title) entries.
result: pass
evidence: "PR #9 (uat/09-multi-call): files config/credentials/api_keys.py (security/backend, ~83 tokens) + migrations/0042_payment_method.sql (data, ~69 tokens). prevue.yml max_tokens_per_call: 100 (below combined ~152), max_review_calls: 2. Sticky Metadata shows: Per-call tokens: security 2599 · data 2431. Single sticky comment, 1 check run. Findings contain no duplicate (path, title) entries. max_tokens_per_call=100 < combined=152 forces split; file-level token estimate (estimate_file_prompt_tokens) drives greedy-merge, not skill content."

### 14. Live budget alert: run_budget_reached renders above metadata block
expected: PR with many files, prevue.yml max_total_run_tokens: 2000 (forces overflow on 5 SQL files ~720 tokens each); sticky shows prominent alert section before the collapsed Metadata block; lowest-priority files listed as not reviewed.
result: pass
evidence: "PR #10 (uat/09-budget-alert): 5 SQL migration files, prevue.yml max_total_run_tokens: 2000. Projected review tokens ~3590 > 2000 cap. Sticky shows: Coverage section 'Run token budget reached — 4 file(s) not reviewed' rendered BEFORE Metadata block. 4 files listed as skipped: 0100_budget_test_3.sql, _4.sql, _5.sql, prevue.yml. 2 files reviewed with findings. Conclusion is failure (reviewed files had error-level findings — neutral conclusion only fires when ALL files are dropped, covered by test_whole_run_cap_overflow_disclosure automated test). Budget alert rendering and file-drop disclosure verified correct live."

## Summary

total: 14
passed: 14
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — all 14 tests pass. One code bug found and fixed during live testing: per_call token entries missing bundle labels (commit fb75f43). Live tests 12-14 required sequential prevue.yml config swaps on sandbox main (tests share base branch). Test 14 expectation refined: neutral conclusion requires all-files-dropped path; partial-drop path (some reviewed) yields findings-based conclusion (covered by automated test_whole_run_cap_overflow_disclosure).]
