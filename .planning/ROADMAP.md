# Roadmap: Prevue

## Overview

Prevue ships as a vertical MVP: Phase 1 stands up a complete working review loop (fetch diff → AI review → PR summary comment) on the riskiest integration (Copilot CLI on Actions runners) with the security posture locked in from day one. Phases 2–4 then slice in the core thesis — zero-token classification, selective skill loading, and structured findings with a merge gate — each keeping the loop working end-to-end. Phase 5 proves the engine abstraction is genuinely engine-agnostic with additional adapters (Claude Code, Cursor) before any consumer-facing surface locks. Phase 6 then packages everything as a consumable reusable workflow with hybrid classification and config surface (the first externally shippable milestone), and Phase 7 hardens it into a framework: consumer custom skills, prompt-injection verification, token transparency, and large-PR budgets.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Walking Skeleton Review Loop** - End-to-end PR review: fetch diff via API, Copilot CLI review, sticky summary comment, secure trigger posture (completed 2026-06-11)
- [x] **Phase 2: Zero-Token Classification & Routing** - Deterministic glob/path classifier with path filters and auditable label→bundle routing (completed 2026-06-12)
- [x] **Phase 3: Selective Skill Loading** - SKILL.md bundle loader, five built-in bundles, trusted-ref-only loading (completed 2026-06-12)
- [x] **Phase 4: Structured Findings & Merge Gate** - Schema-validated findings, position-validated inline comments, severity thresholds, comment budget, pass/fail/neutral check (completed 2026-06-13)
- [x] **Phase 5: Multi-Engine Adapter Support** - Additional `EngineAdapter`s (Claude Code, Cursor, Gemini) via the same interface, config-selectable, validating engine-agnosticism before public packaging (completed 2026-06-13)
- [x] **Phase 6: Reusable Workflow & Hybrid Classification** - `workflow_call` packaging, consumer config, LLM classification fallback, skip conditions — first shippable (completed 2026-06-13)
- [ ] **Phase 7: Customization & Hardening** - Consumer custom skills/overrides, prompt-injection verification, token transparency, large-PR budget

## Phase Details

### Phase 1: Walking Skeleton Review Loop

**Goal**: A PR opened against a test repo receives an AI-generated review summary comment, end-to-end, with the trust architecture (trigger model, no untrusted checkout) decided and enforced from day one
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: DIFF-01, ENGN-01, ENGN-02, OUTP-01, SECR-01
**Success Criteria** (what must be TRUE):

  1. Opening or updating a PR triggers a run that fetches the diff and changed-file metadata via the GitHub API, without checking out untrusted PR code for analysis
  2. The pluggable `EngineAdapter` interface is engine-agnostic by design; the Copilot CLI adapter (the first adapter) runs headless on a real Actions runner (auth via `COPILOT_GITHUB_TOKEN`) and returns a review through that interface — additional adapters (Claude Code, Cursor) land in Phase 5
  3. A summary comment appears on the PR and is updated in place (not duplicated) on subsequent runs
  4. The workflow uses the `pull_request` trigger only, and fork PRs are documented as unsupported

**Plans**: 7 plans

**Wave 1**

- [x] 01-01-PLAN.md — Copilot CLI spike (D-12 de-risk: auth/output/timing on a clean runner)
- [x] 01-02-PLAN.md — Project scaffold + test infrastructure + CI (zizmor SECR-01 gate)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-03-PLAN.md — Adapter contract models (pydantic ReviewRequest/ReviewResult, TDD)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — GitHub I/O: diff fetch + sticky comment upsert (TDD)
- [x] 01-05-PLAN.md — Copilot CLI adapter (headless, zero-tool, fail-closed, TDD)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-06-PLAN.md — Orchestration + `prevue review` CLI + fork guard + D-09

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-07-PLAN.md — Secure `pull_request` wrapper workflow + docs + live E2E (sandbox)

### Phase 2: Zero-Token Classification & Routing

**Goal**: Clear-cut PRs are classified into category labels and routed to skill bundles deterministically, spending zero LLM tokens, with the decision trail auditable
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DIFF-02, CLSF-01, CLSF-03, ROUT-01
**Success Criteria** (what must be TRUE):

  1. A PR touching only clearly-typed files (e.g. `.tsx` components, Terraform files) receives correct category labels (security, frontend, backend, data, infra) with zero LLM calls
  2. Lockfiles, generated, vendored, and binary files — plus consumer-defined ignore globs — are filtered out before classification
  3. Classification rules live in data (configurable/overridable), and the review output shows which labels were assigned and which rules matched
  4. Labels resolve to skill bundles with documented precedence: consumer override > consumer custom > built-in

**Plans**: 3 plans

**Wave 1**

- [x] 02-01-PLAN.md — Foundation + thin end-to-end slice: deps (pathspec/PyYAML), default_rules.yml, RuleSet/ClassificationResult models, filter/classify/route wired into run_review with labels in the sticky Metadata (TDD)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Classifier refinement: multi-label union (D-01), PR-level `general` fallback (D-03), canonical ordering + matched-rule provenance, general routing (TDD)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Edge cases + configurability: consumer additive merge (D-05/D-06/D-07), D-10 empty-PR neutral skip, dropped-count audit (TDD)

### Phase 3: Selective Skill Loading

**Goal**: The review context contains exactly the skill bundles the PR's classification matched — nothing else — loaded only from the trusted base ref
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SKIL-01, SKIL-02, SKIL-04
**Success Criteria** (what must be TRUE):

  1. A PR classified as backend-only gets a review context containing the backend bundle and not the frontend/data/infra bundles
  2. Five built-in skill bundles (security, frontend, backend, data, infra) exist as SKILL.md-style markdown with routing metadata
  3. Skills are loaded from the trusted base ref only; skill files modified by the PR under review are never used in the same run

**Plans**: 4 plans

**Wave 1**

- [x] 03-01-PLAN.md — Wave 0 scaffold: add python-frontmatter (legitimacy checkpoint), skills-fixture tree + conftest, failing loader/builtin test scaffolds (RED)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Loader core + security bundle wired end-to-end: Skill model, load/select/order/dedupe/assemble (GREEN), security skills, run_review + sticky-audit (D-13) (TDD)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — Broaden to frontend/backend/data/infra bundles + finalize SKIL-02 builtin tests + test_review_flow behavior-change update

**Wave 4** *(gap closure — UAT test 7)*

- [x] 03-04-PLAN.md — Enrich thinnest built-in skills (D-11) + lean content-floor test + validation rubric update

### Phase 4: Structured Findings & Merge Gate

**Goal**: Reviews produce trustworthy, bounded output — schema-validated findings as correctly-placed inline comments, severity-filtered, capped by a hard budget, with a pass/fail/neutral check that never falsely blocks
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: ENGN-03, OUTP-02, OUTP-03, NOIS-02, NOIS-03
**Success Criteria** (what must be TRUE):

  1. Engine output is schema-validated with retry-then-degrade handling; a parse failure produces a neutral check and summary-only review, never a crash or red X
  2. Inline comments land on the correct diff lines via the Reviews API; findings outside valid diff hunks fall back to the summary instead of erroring
  3. Findings carry severity levels, and the consumer can configure min-severity-to-comment and min-severity-to-fail thresholds
  4. The check reports pass/fail/neutral and is usable as a merge gate, with blocking opt-in via severity threshold
  5. No review ever posts more inline comments than the configured hard budget

**Plans**: 5 plans

**Wave 1**

- [x] 04-01-PLAN.md — Wave 0: unidiff dep (audited) + RED contract scaffolds for parsing/positions/gate/checks

**Wave 2** *(parallel, blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Engine JSON contract: fence parsing + strict salvage + rubric/4C prompt + retry-then-degrade (ENGN-03, TDD)
- [x] 04-03-PLAN.md — Gate policy: ReviewConfig + conclusion ladder + budget allocation + unidiff position validity (NOIS-02/NOIS-03/OUTP-02/OUTP-03 logic, TDD)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-04-PLAN.md — Rendering: D-21 uniform inline template, Verdict/table/details sticky restructure, batched COMMENT review POST (TDD)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-05-PLAN.md — `prevue/review` check run + run_review post-engine wiring + `checks: write` permission (TDD)

### Phase 5: Multi-Engine Adapter Support

**Goal**: The `EngineAdapter` abstraction is proven engine-agnostic — Claude Code, Cursor, and Gemini adapters run headless through the same interface as Copilot, selectable via config, before the public reusable workflow locks the engine-selection surface
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: ENGN-04
**Success Criteria** (what must be TRUE):

  1. Three additional adapters (Claude Code CLI, Cursor CLI, Gemini CLI) implement the same `EngineAdapter` interface and pass the same contract tests as the Copilot adapter
  2. The active engine is selectable via config (workflow input / `prevue.yml`) with Copilot as the default; an unknown engine name fails closed with a clear error
  3. Each adapter runs headless on an Actions runner with its own auth env var and returns schema-valid findings through the shared retry-then-degrade path
  4. Adding the new adapters required no change to the orchestration, findings, or gate layers — confirming the abstraction boundary held (any interface leak is fixed here, not in consumer-facing packaging)

**Plans**: 3 plans

**Wave 1**

- [x] 05-01-PLAN.md — Shared foundation: hoist prompt/errors/flow into shared modules + fail-closed registry + Gemini skeleton + wire PREVUE_ENGINE selection (Copilot stays green; TDD)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Claude Code CLI adapter (`claude --bare -p`), registered + contract-suite green (D-01, TDD)

**Wave 3** *(blocked on Wave 2 completion; not autonomous — D-12 live verify)*

- [x] 05-03-PLAN.md — Cursor CLI adapter (`cursor-agent -p -f`) + workflow curl-installs (reject npm impostor) + D-12 live sandbox verification of Claude + Cursor (D-01, TDD)

### Phase 6: Reusable Workflow & Hybrid Classification

**Goal**: Any repo can adopt Prevue with a minimal caller snippet — the workflow self-checkouts, runs the full hybrid pipeline under minimal permissions, and respects consumer config and skip conditions
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04, CLSF-02, NOIS-01
**Success Criteria** (what must be TRUE):

  1. A separate consumer repo adopts Prevue by calling the reusable workflow (`workflow_call`) at a pinned ref with a minimal caller snippet, and gets a working review
  2. The reusable workflow self-checkouts the Prevue repo and the consumer repo, then runs the pipeline via a single CLI invocation
  3. Run behavior is configurable via workflow inputs and a `.github/prevue.yml` read from the trusted base ref
  4. Ambiguous diffs fall back to a cheap LLM classification call; clear-cut PRs still spend zero classification tokens
  5. Draft PRs, bot authors (e.g. dependabot), and title/label-filtered PRs are skipped by default (configurable), and required token scopes are minimal and documented

**Plans**: 4 plans

**Wave 1**

- [x] 06-01-PLAN.md — Foundation: classify() ABC capability + label prompt + single-read .github/prevue.yml config loader + classifier surfaces unmatched paths + Wave 0 RED scaffolds (WKFL-03, CLSF-02, TDD)

**Wave 2** *(parallel, blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Reusable workflow_call workflow + thin pull_request caller (dogfood) + consumer-setup docs + static YAML guards (WKFL-01/02/04)
- [x] 06-03-PLAN.md — Hybrid per-file LLM fallback: per-engine classify() + llm_fallback degrade-to-general + run_review single-read config wiring (CLSF-02, WKFL-03, TDD)

**Wave 3** *(blocked on Wave 2 completion; not autonomous — live sandbox verify)*

- [x] 06-04-PLAN.md — Skip pipeline: should_skip bot/label/title + neutral skip check/sticky reason + run_review skip hook + live consumer-repo verification (NOIS-01, WKFL-01/02, TDD)

### Phase 7: Customization & Hardening

**Goal**: Prevue behaves as a framework — consumers extend and override skills safely, prompt-injection defenses are verified, and every review proves the token-efficiency thesis with transparent budgets
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: SKIL-03, SECR-02, OUTP-04, DIFF-03
**Success Criteria** (what must be TRUE):

  1. A consumer repo adds a custom skill bundle under `.github/prevue/skills/` and it is routed to; a same-named consumer bundle overrides the built-in
  2. Untrusted PR text (titles, bodies, comments) is never interpolated into engine prompts as instructions; prompt-injection attempts are red-team tested and documented as mitigated
  3. The summary comment reports tokens used and which skills were loaded vs skipped on every review
  4. Oversized PRs are reviewed within a token budget using prioritized file packing, with an explicit "N files not reviewed" disclosure in the summary

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Walking Skeleton Review Loop | 7/7 | Complete    | 2026-06-11 |
| 2. Zero-Token Classification & Routing | 3/3 | Complete    | 2026-06-12 |
| 3. Selective Skill Loading | 4/4 | Complete    | 2026-06-12 |
| 4. Structured Findings & Merge Gate | 5/5 | Complete    | 2026-06-13 |
| 5. Multi-Engine Adapter Support | 3/3 | Complete   | 2026-06-13 |
| 6. Reusable Workflow & Hybrid Classification | 4/4 | Complete    | 2026-06-13 |
| 7. Customization & Hardening | 0/TBD | Not started | - |

---
*Roadmap created: 2026-06-12*
