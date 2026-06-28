---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
stopped_at: Phase 10 context gathered
last_updated: "2026-06-28T16:47:10.650Z"
last_activity: 2026-06-24 -- Phase 09 post-review fixes committed; VERIFICATION.md updated to 10/10
progress:
  total_phases: 15
  completed_phases: 9
  total_plans: 55
  completed_plans: 55
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-12)

**Core value:** Optimal memory context and token usage when integrating with AI — load only the review skills the PR actually needs — while keeping review quality on par with a full-context review.
**Current focus:** v1 milestone complete — all 9 phases shipped

## Current Position

Phase: 09 (classification-skill-loading-multi-call-review) — COMPLETE
Plan: 6 of 6 (all complete; UAT 14/14 pass; WR-01..WR-12 fixes applied)
Status: v1 complete — 720/720 tests, live UAT confirmed, verification report finalized
Last activity: 2026-06-24 -- Phase 09 post-review fixes committed; VERIFICATION.md updated to 10/10

Progress: [██████████] 6/6 plans complete (Phase 09) — All 9 phases complete

## Performance Metrics

**Velocity:**

- Total plans completed: 55
- Average duration: 16 min (46 plans with recorded duration)
- Total execution time: ~12.5 hours (46 plans with recorded duration; Phase 08/09 partially recorded)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | 123 min | 18 min |
| 02 | 3 | 22 min | 7 min |
| 03 | 4 | 38 min | 10 min |
| 04 | 5 | 107 min | 21 min |
| 05 | 3 | 90 min | 30 min |
| 06 | 4 | 48 min | 12 min |
| 07 | 7 | 53 min | 8 min |
| 08 | 16 | 133 min (10 recorded) | 13 min |
| 09 | 6 | 56 min | 9 min |

**Recent Trend:**

- Last 5 plans: 09-02 (6 min), 09-03 (4 min), 09-04 (16 min), 09-05 (12 min), 09-06 (11 min)

**By Plan:**

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 01-walking-skeleton-review-loop | P01 | 20min | 2 tasks | - |
| 01-walking-skeleton-review-loop | P02 | 14min | 3 tasks | - |
| 01-walking-skeleton-review-loop | P03 | 5min | 2 tasks | - |
| 01-walking-skeleton-review-loop | P04 | 12min | 2 tasks | - |
| 01-walking-skeleton-review-loop | P05 | 15min | 2 tasks | - |
| 01-walking-skeleton-review-loop | P06 | 12min | 2 tasks | - |
| 01-walking-skeleton-review-loop | P07 | 45min | 3 tasks | - |
| 02-zero-token-classification-routing | P01 | 12min | 3 tasks | - |
| 02-zero-token-classification-routing | P02 | 8min | 2 tasks | - |
| 02-zero-token-classification-routing | P03 | 2min | 2 tasks | - |
| 03-selective-skill-loading | P01 | 8min | 3 tasks | - |
| 03-selective-skill-loading | P02 | 12min | - | - |
| 03-selective-skill-loading | P03 | 10min | - | - |
| 03-selective-skill-loading | P04 | 8min | 2 tasks | - |
| 04-structured-findings-merge-gate | P01 | 12min | 2 tasks | - |
| 04-structured-findings-merge-gate | P02 | 35min | 3 tasks | - |
| 04-structured-findings-merge-gate | P03 | 15min | 3 tasks | - |
| 04-structured-findings-merge-gate | P04 | 25min | 3 tasks | - |
| 04-structured-findings-merge-gate | P05 | 20min | 3 tasks | - |
| 05-multi-engine-adapter-support | P01 | 45min | - | - |
| 05-multi-engine-adapter-support | P02 | 20min | - | - |
| 05-multi-engine-adapter-support | P03 | 25min | - | - |
| 06-reusable-workflow-hybrid-classification | P01 | 12min | 3 tasks | - |
| 06-reusable-workflow-hybrid-classification | P02 | 1min | 2 tasks | - |
| 06-reusable-workflow-hybrid-classification | P03 | 15min | 3 tasks | - |
| 06-reusable-workflow-hybrid-classification | P04 | 20min | 2 tasks | - |
| 07-customization-hardening | P01 | 15min | 3 tasks | - |
| 07-customization-hardening | P02 | 25min | 3 tasks | - |
| 07-customization-hardening | P03 | - | - | - |
| 07-customization-hardening | P04 | - | - | - |
| 07-customization-hardening | P05 | - | - | - |
| 07-customization-hardening | P06 | 8min | 2 tasks | - |
| 07-customization-hardening | P07 | 5min | 2 tasks | - |

*Updated after each plan completion*
| Phase 08-incremental-stateful-review-lifecycle P01 | 5 | 3 tasks | 8 files |
| Phase 08-incremental-stateful-review-lifecycle P02 | 2 | 2 tasks | 4 files |
| Phase 08-incremental-stateful-review-lifecycle P03 | 18 | 3 tasks | 6 files |
| Phase 08-incremental-stateful-review-lifecycle P04 | 2 | 2 tasks | 4 files |
| Phase 08-incremental-stateful-review-lifecycle P05 | 8 | 2 tasks | 2 files |
| Phase 08-incremental-stateful-review-lifecycle P06 | 35 | 2 tasks | 3 files |
| Phase 08-incremental-stateful-review-lifecycle P07 | 45 | 2 tasks | 5 files |
| Phase 08-incremental-stateful-review-lifecycle P08 | 7 | 3 tasks | 3 files |
| Phase 08-incremental-stateful-review-lifecycle P10 | 6 | 2 tasks | 4 files |
| Phase 08-incremental-stateful-review-lifecycle P09 | 5 | 2 tasks | 2 files |
| Phase 09-classification-skill-loading-multi-call-review P01 | 7 | 3 tasks | 7 files |
| Phase 09-classification-skill-loading-multi-call-review P02 | 6 | 3 tasks | 5 files |
| Phase 09-classification-skill-loading-multi-call-review P03 | 4 | 3 tasks | 1 files |
| Phase 09-classification-skill-loading-multi-call-review P04 | 16 | 2 tasks | 3 files |
| Phase 09-classification-skill-loading-multi-call-review PP05 | 12 | 3 tasks | 4 files |
| Phase 09-classification-skill-loading-multi-call-review P06 | 11 | 2 tasks (+ 1 checkpoint) | 6 files |

## Accumulated Context

### Roadmap Evolution

- Phase 8 added: Incremental & Stateful Review Lifecycle (LIFE-01/02/04)
- Phase 8 edited: shortened title; LIFE-01/02/04 detail moved into Goal; dir slug → 08-incremental-stateful-review-lifecycle
- Phase 9 added: Classification-aligned skill loading — reconcile classify/route with selective skill selection (SKIL-01 gap; gap-demo-sandbox PR #25 proof)
- Phase 9 scope expanded 2026-06-21: added multi-call review (ENGN-05/06/07 — configurable max_review_calls, context-preserving split, optional parallelism); CUST-04 superseded; dir slug → 09-classification-skill-loading-multi-call-review; old 3 plans deleted (re-plan after discuss)
- Phases 10–13 added 2026-06-25 (prioritized by cost-of-delay — adapter/config contracts first): Phase 10 Boundary Contracts (WKFL-05, PERF-03, ENGN-08/09, OUTP-05); Phase 11 Skills as Pinned External Repo (SKIL-06/07); Phase 12 Cross-File Dependency Context (PERF-04); Phase 13 Finding Signal Quality (QUAL-01). 9 reqs promoted v2 → v1; LIFE-03/05 relocated v2 → v1 (Phase 8, complete). All four phases unplanned — run /gsd-plan-phase 10 next.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Pluggable engine adapter layer from day one; Copilot CLI is the first adapter
- [Init]: Hybrid classification — deterministic first, LLM fallback only for ambiguous diffs
- [Init]: `pull_request` trigger only; fork PRs unsupported in v1; skills/config loaded from trusted base ref
- [Roadmap]: Vertical MVP — Phase 1 delivers a full working review loop (fetch → review → comment) before slicing in classification/skills
- [01-02]: Wave 0 scaffold — uv package, pytest fixtures, CI with actionlint+zizmor SECR-01 gate
- [01-02]: conftest stub types until Plan 03 models; smoke test for pytest collection
- [01-03]: Locked ENGN-01 pydantic contract — findings defaults [], no PR title/body on DiffBundle (D-02, D-07)
- [Phase 01]: PrContext in client.py with head/base repo for fork guard (Plan 04)
- [Phase 01]: Marker-based sticky upsert — deterministic Python owns GitHub writes (P3)
- [Phase 01]: Zero --allow-tool Copilot adapter per spike A1 (Plan 05)
- [Phase 01]: github_pat_ auth guard per spike A2 (Plan 05)
- [Phase 01]: Token redaction in EngineFailure stderr (T-05) (Plan 05)
- [Phase 01]: run_review() orchestration with fork guard + D-09 fail-closed (Plan 06)
- [Phase 01]: prevue review CLI — fork no-op exit 0, engine failure exit 1 (Plan 06)
- [Phase 01]: Copilot prompt via stdin (ARG_MAX fix); live E2E on PR #2 (Plan 07)
- [Phase 01]: setup-uv SHA-pinned; checkout SHA-pinned (# v6); copilot@1.0.61; spike deleted post-E2E
- [02-01]: GitIgnoreSpec.from_lines for pathspec 1.x classify stage
- [02-01]: ClassificationResult threaded to upsert_sticky Metadata (D-09)
- [02-01]: filter→classify→route wired into run_review; engine gets reduced diff (D-08)
- [02-02]: CANONICAL_LABEL_ORDER pinned to models.py — presentation never imports classifier
- [02-02]: Multi-label union (D-01) + PR-level general fallback (D-03) + canonical Metadata order
- [02-03]: merge_rules D-07 ignore append, D-05 label replace-by-label, D-06 routing override
- [02-03]: D-10 filter-first empty-PR skip; upsert_skip_note idempotent sticky; D-09 dropped count audit
- [04-01]: Wave 0 RED scaffolds pin Phase 4 API contracts; unidiff 0.7.* locked
- [04-02]: engines/parsing.py prose+fence parser; strict salvage; adapter retry-then-degrade (ENGN-03)
- [04-02]: Strip all json fences from prose; parse last fence only (decoy defense)
- [04-02]: Fully-dropped salvage → degraded=True (false-green avoidance)
- [04-03]: Position validation before budget — unplaceable findings never consume inline slots
- [04-03]: load_review_config owned by gate.py; unidiff header synthesis for GitHub patch fragments
- [04-04]: Python owns all findings markdown — D-21 uniform template, gate-aware sticky (D-26), batched COMMENT review (D-20)
- [04-04]: Markdown-injection hardening — _escape_table_cell, _safe_suggestion_block; verdict strings from gate.py only (D-07)
- [04-05]: Single completed-only create_check_run — no in_progress dangling check on engine hard-fail
- [04-05]: load_review_config before fetch_diff — D-16 fail-closed before engine spend
- [04-05]: Write order inline → sticky → check; check links to sticky html_url (D-10)
- [04-05]: checks:write pinned in workflow; fork PR creates no check (D-09 absence holds pending)
- [Roadmap 2026-06-13]: Inserted Phase 5 "Multi-Engine Adapter Support" (ENGN-04, promoted from CUST-03) — Claude Code + Cursor adapters validate the engine abstraction BEFORE public packaging; old Phase 5→6, 6→7. Phase 1 criterion 2 reworded to engine-agnostic (--force edit)
- [06-01]: PrevueConfig single-read bundle (ruleset+review+skip+fallback+engine); SkipConfig skip_labels default ["skip-review"]
- [06-01]: EngineAdapter.classify() default-raising; build_classify_prompt fences paths; ClassificationResult.unmatched per-file signal
- [06-02]: Shippable prevue-review.yml workflow_call; self-checkout v0.6.0 + consumer base.sha; named secrets no inherit
- [06-02]: review.yml thin dogfood caller; docs/consumer-setup.md with skip≠auto-merge note
- [06-03]: llm_classify(unmatched, adapter, model) -> (labels, disclosure); degrade to general on failure (D-12)
- [06-03]: run_review single-read load_config(.github/prevue.yml); same adapter for fallback (D-10)
- [06-03]: Classification disclosure on sticky Metadata line (Open Question 3 lock)

- [07-02]: make_file_weight re-runs GitIgnoreSpec per file for pack priority (A4)
- [07-02]: partial=True degrades would-be success to neutral (D-23)
- [07-02]: No-fit PR reuses neutral skip path with budget disclosure (D-24)
- [Phase 08-incremental-stateful-review-lifecycle]: LAST_SHA fixture deadbeef... equals compare_ahead merge_base for incremental scope tests — Downstream compare mocks need consistent last-reviewed SHA convention (08-01)
- [Phase 08-incremental-stateful-review-lifecycle]: D-04 fingerprint: NFKC+casefold normalize, sha256(path|title)[:16], stdlib only — LIFE-02 deterministic dedupe backstop without new dependencies (08-01)
- [Phase 08-incremental-stateful-review-lifecycle]: D-12 parse_severity_from_body: first-line badge anchor only, None fail-safe — no eval; inverse of SEVERITY_BADGES for gate-over-open-set (08-02)
- [Phase 08-incremental-stateful-review-lifecycle]: D-09 finding_region_changed: C=3 conservative hunk overlap via unidiff PatchSet — fail-safe empty regions on bad/None patch (08-02)
- [Phase 08-incremental-stateful-review-lifecycle]: D-01 marker SHA: hex-bound _MARKER_RE; legacy head-less → None; _is_prevue_sticky regex-anchored at body start (08-03)
- [Phase 08-incremental-stateful-review-lifecycle]: D-03 decide_scope: repo.compare status + merge_base==last_sha for incremental; diverged/behind/mismatch → full (08-03)
- [Phase 08-incremental-stateful-review-lifecycle]: D-11 open-set gate: caller union via fingerprint(path,title); apply_gate policy unchanged (08-03)
- [Phase 08-incremental-stateful-review-lifecycle]: D-08/D-10 GraphQL: raw requests transport; resolve best-effort 403-skip; isResolved for caller idempotency (08-04)
- [Phase 08-incremental-stateful-review-lifecycle]: D-07 known-issues: build_known_issues_block UNTRUSTED DATA fence, max_known_issues cap kwarg (08-04)
- [Phase 08-incremental-stateful-review-lifecycle]: D-05/D-06 reconciliation: in_scope_paths stale scope; SEVERITY_RANK escalation-only .edit() (08-05)
- [Phase 08-incremental-stateful-review-lifecycle]: D-01/D-11 orchestration: decide_scope before fetch; resolve-before-gate open set; noop skips engine; head_sha sticky marker (08-06)
- [Phase 08-incremental-stateful-review-lifecycle]: resolveReviewThread 403 under pull-requests:write on live sandbox — best-effort skip ships LIFE-01/02; resolve_outdated opt-out documented; no contents:write (WKFL-04) (08-07)
- [Phase 08-incremental-stateful-review-lifecycle]: Live UAT PASS incremental scoping + noop re-run on gap-demo-sandbox PR #21/#22 (08-07)
- [Phase 08-gap-closure]: Rephrase-at-same-line open-set fix: keep carried prior when fingerprint differs at same location; post_inline_review _severity_escalated already handles quiet path — no fingerprint gating needed in comments.py (08-08)
- [Phase 08-gap-closure]: Engine CLI install only (not checkout/uv sync) skipped on noop — prevue review step still runs for marker/check refresh via _finish_noop_review (08-10)
- [Phase 08-gap-closure]: GFM _posted by Prevue_ replaces HTML sub INLINE_MARKER; LEGACY_INLINE_MARKER for backward-compat; deterministic incremental disclaimer in render_body (08-09)
- [Phase 09]: Flat ReviewConfig caps (not nested multicall: sub-model) — parity with existing knobs, extra=forbid preserved (09-01)
- [Phase 09]: KEYWORD_THRESHOLD=0.15 with Jaccard 0.7/path_signal 0.3 weighting — strong content overlap crosses threshold; weak content + path match also crosses (09-02)
- [Phase 09]: Gap-closure guard pass-through: no adapter + no llm_skill_names conservatively includes all routed below-threshold skills (prefer over-loading to silent drop) (09-02)
- [Phase 09]: _dedup_sort shared between select_skills and select_skills_hybrid — loader.py imports from selection.py (09-02)
- [Phase 09]: referenced_paths(path, patch) two-arg signature matches 09-01 RED scaffold contract (importscan)
- [Phase 09]: Python ast-first + regex-fallback; JS/TS regex-only; unknown lang degrades to [] (importscan D-06/09-03)
- [Phase 09]: Classify-first: classify(reduced.files) before pack fixes SKIL-01 gap
- [Phase 09]: Double-duty llm_select_skills gated on fallback ran — no extra adapter call on fully-matched PRs
- [Phase 09]: Empty llm_select_skills degrade leaves llm_skill_names=None preserving gap-closure escalation path in select_skills_hybrid
- [Phase 09]: Single-call EngineFailure propagates (D-09 preserved); multi-call fail-soft only when len(call_requests)>1 (09-05)
- [Phase 09]: Whole-run cap (D-10): repack with budget=max_total_run_tokens-classify_tokens; all-dropped→skip neutral; partial→skipped_reason with 'run token budget reached' (09-05)
- [Phase 09]: merge_findings fingerprint dedup with SEVERITY_RANK tie-break: error beats warning on collision (Pitfall 4); per_call token breakdown in engine_meta for 09-06 (Pitfall 5) (09-05)
- [Phase 09]: skill_sources built via keyword_score re-eval per matched skill: crossed KEYWORD_THRESHOLD→'keyword', LLM double-duty names→'llm', below-threshold routed→'routed' (09-06)
- [Phase 09]: run_budget_alert rendered as standalone section BEFORE Metadata <details> block (T-09-20 D-10 prominent alert requirement) (09-06)
- [Phase 09]: ARCHITECTURE.md classify-first pipeline + multi-call section; configuration.md routing drives hybrid skill loading not metadata-only (CLSF-03/09-06)

### Pending Todos

None yet.

### Blockers/Concerns

None — all pre-v1 research risks resolved. Phase 1 spike confirmed Copilot CLI headless auth. Phase 4 solved diff-hunk position mapping. v1 milestone complete.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260613-w0q | Fix Phase 6 Prevue self-review findings (#5 upsert, #2 fork guard, #4 config warn, #1 cursor install, #3/#6 docs) | 2026-06-13 | 8ee8968 | [260613-w0q-fix-phase-6-prevue-self-review-findings](./quick/260613-w0q-fix-phase-6-prevue-self-review-findings/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| lint | Pre-existing ruff E501/I001 in test_copilot_adapter.py, test_positions.py | resolved (commit 418a1f0, 2026-06-23) | 04-05 |
| lifecycle | LIFE-05 smarter inline thread resolve/dismiss (see REQUIREMENTS.md v2) | open (v2 backlog) | 08-ship |

## Session Continuity

Last session: 2026-06-28T13:14:04.525Z
Stopped at: Phase 10 context gathered
Resume file: .planning/phases/10-boundary-contracts/10-CONTEXT.md
