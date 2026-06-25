# Phase 9: Classification-aligned skill loading + multi-call review — Context

**Gathered:** 2026-06-17 (skill-loading thread)
**Re-discussed:** 2026-06-21 (full re-open: pipeline reorder + B+D skill selection + multi-call review)
**Status:** Ready for planning — RESEARCH.md is STALE (was written for the old surgical-union design; re-research required)

<domain>
## Phase Boundary

Two threads, deliberately combined into one phase by the user.

**Thread 1 — Classification-aligned skill loading (SKIL-01 gap closure).**
Today `classify()` + `route()` run **after** `select_skills()`, so routed labels never expand the review instructions — they only touch sticky Metadata. A PR classified `security` does not load the security bundle's skills if their per-skill `applies-to` globs don't match the changed paths. **Live proof:** gap-demo-sandbox PR #25 — `src/pages/Checkout.jsx`, consumer skill `gap-demo-auth-guard` (`applies-to: **/auth/**`). Loaded generic security skill via broad glob, NOT the demo skill; `Labels: frontend` only; no `GAP-DEMO-SKILL-LOADED` finding. Gap confirmed. Critical insight (2026-06-21): the LLM classify fallback fixes the *label* but NOT *which skills load* — routing works at bundle level, loading degraded to per-skill-glob level, and the two never reconcile.

**Thread 2 — Configurable multi-call review (ENGN-05/06/07).**
When a single LLM call can't cover a PR (too large for context, or quality benefits from splitting), split the diff into multiple review calls, run them sequentially (default) or in parallel (opt-in), and merge/dedupe findings. Default `max_review_calls=1` keeps single-call behavior backward-compatible.

**Master design principle (user, 2026-06-21):** Optimize tokens across the **whole run (classify + review), not per-phase.** Loading whole bundles is zero classify-token but bloats the *review* prompt with irrelevant skill bodies ("review takes the hammer"). A small selection cost upfront wins if it trims more review tokens than it spends. Minimize the **sum**.

**Out of scope:** per-path severity overrides (CUST-01); loading skills from PR head (SKIL-04 unchanged); native GitHub PR labels (CUST-05); cross-file call-graph *impact* analysis beyond the import-locality used for call splitting.

**Phase-size note:** This is a large phase (two substantial threads). The planner should consider splitting into sub-waves — Thread 1 (reorder + B+D selection) is a prerequisite for Thread 2 (multi-call), since multi-call splitting reuses the classify-first bundle grouping and per-bundle skill selection. Sequence Thread 1 before Thread 2.
</domain>

<decisions>
## Implementation Decisions

> **2026-06-21 re-discussion supersedes the 2026-06-17 decisions.** The earlier
> design (D-01 surgical post-classify union, D-02 whole-bundle expansion) is
> REPLACED by a full pipeline reorder + hybrid B+D skill selection. Kept from
> the original: LLM-fallback participation, re-trim→neutral budget discipline,
> sticky audit, gap-demo-sandbox regression.

### Thread 1 — Skill-loading: pipeline & selection

- **D-01 (REORDER — supersedes old D-01 surgical union):** Rebuild the pipeline to **classify-first**. New order:
  ```
  filter → classify(all changed files) → route → bundles
        → SELECT skills (D-02 below)
        → label-weighted pack (budget)
        → assemble instructions (selected skill bodies + packed diff)
        → review
  ```
  Classification now drives **both** pack-weighting and skill selection up front. Keep it performant: deterministic classify stays **zero-token** for clear-cut PRs; only ambiguous (unmatched) files hit the LLM fallback — unchanged cost model. Reorder runs deterministic classify on the full changed set pre-pack (glob-only, zero-token); LLM fallback still only sees the small unmatched set.

- **D-02 (B+D hybrid skill selection — supersedes old D-02 whole-bundle):** Select individual skills within routed bundles using a **deterministic-first, LLM-fallback** scheme that mirrors the classification architecture (CLSF-01 + CLSF-02):
  - **Deterministic keyword floor (zero-token):** score each candidate skill's `name`+`description` (and `applies-to`) against the diff content/paths; load skills above a relevance threshold.
  - **LLM escalation:** below-threshold skills **within a routed bundle** escalate to an LLM relevance check (name+desc only — no bodies). When the classify LLM fallback is **already firing**, the *same call* returns both labels and relevant skill names (double-duty, near-zero marginal cost).
  - **Rationale (whole-run tokens):** keyword floor avoids loading whole bundles of irrelevant skill bodies into the review prompt; LLM escalation guarantees a routed bundle's relevant-but-low-keyword-score skill (the gap-demo-sandbox shape) still gets a chance to load instead of being silently dropped.
  - **Gap-closure guard:** the design MUST ensure a routed bundle's genuinely-relevant skill is never silently pruned — below-threshold routed skills escalate rather than drop. (This is the explicit risk the user accepted keyword-first for, in exchange for whole-run token savings.)

- **D-03 (LLM fallback labels participate — kept):** Labels recovered by `llm_classify()` flow into `result_cls.bundles` and trigger the same routing + skill-selection path as deterministic labels. One code path; no "recovered a label but skills didn't reload" gap.

- **D-04 (Post-select budget — kept, = Q4):** After selection + assembly, run the existing `trim_packed_files` loop + a byte-limit guard (`MAX_PROMPT_BYTES`) before review. If still over budget → **fail-closed neutral skip** with disclosure. Same discipline as today.

### Thread 2 — Multi-call review

- **D-05 (Call trigger & count — ENGN-05):** **Bundle-derived with small-bundle merge.** Group files by routed bundle (the reorder already produces this), then greedily **merge under-budget bundle groups** toward `max_tokens_per_call` until each call is near-full. `calls = ` that merged count, capped at `max_review_calls` (**default 1** → always single call). Chosen for quality + low hallucination: fewest, most cohesive, near-full calls minimize both repeated overhead and context fragmentation.

- **D-06 (Split unit & cross-file context — ENGN-06, = M2 option C):** **Bundle + lightweight import scan.** Group by routed bundle, then co-locate files with direct import/reference links via a cheap static scan so no call reviews a file blind to its dependencies. User accepted higher implementation cost for fewer limitations. Language-specific import parsing is in scope for this strategy.

- **D-07 (Per-call skill scope — = M3):** Each call carries the skills D-02 selected **for its own files** PLUS a small **configurable always-on guardrail set** (e.g. `security/committed-secrets`, authz) injected into every call. Strongest whole-run token play that never skips universal safety checks.

- **D-08 (Merge / gate / output — ENGN-07, = M4):** Merge findings from all calls → **fingerprint dedupe (reuse Phase 8 `fingerprint(path, title)`)** → **one gate** over the union → **one sticky comment** with per-bundle token meta. `review_concurrency` **default 1 (sequential)**; parallel opt-in via `ThreadPoolExecutor` (engine calls are subprocess-bound, GIL releases on wait). **Fail-soft:** one call fails → keep the other results, mark review `degraded → neutral` (never lose good findings).

### Cap system (user asked to enumerate all caps)

- **D-09 (Caps):**
  - `max_tokens_per_call` — **NEW** — per-call input ceiling; each call's pack+skills must fit.
  - `max_total_run_tokens` — **NEW** — whole-run ceiling: `classify + Σ review calls ≤ cap`. Enforces the sum-optimization principle.
  - `max_review_calls` — **NEW** (ENGN-05) — call-count cap. **Default 1**.
  - `review_concurrency` — **NEW** (ENGN-07) — parallel cap. **Default 1** (sequential).
  - Existing, reused: `max_input_tokens` (120k, becomes the default per-call budget), `output_reserve_tokens` (12k, per call), `budget_seconds` (300, per-call subprocess timeout), `max_inline_comments` (10, over merged findings — NOIS-03).
  - All new caps live in `ReviewConfig` (gate.py) / surface through `prevue.yml` `review:` block.

- **D-10 (Whole-run-cap overflow — = answer A):** When `classify + projected review` would exceed `max_total_run_tokens`: reuse **DIFF-03 prioritized file packing** — fit as many calls/files as the cap allows by priority, review those, and **disclose `N files not reviewed (run token budget reached)`** in the sticky. Conclusion = **neutral (partial)**, never a false fail. **The budget-reached alert must be prominent / easy to notice** in the sticky comment (user emphasis) — not a buried metadata line.

### Audit / regression (kept from original)

- **D-11 (Sticky audit):** Sticky Metadata reflects final loaded skills post-selection, distinguishes routed vs keyword-vs-LLM-selected sources where useful, and (multi-call) shows per-bundle/per-call token meta. `skill_ratios` denominators use the full merged `load_skills()` set.
- **D-12 (Regression):** Keep the gap-demo-sandbox-shape regression — packed path NOT matching a skill's `applies-to`, but classify routes to the skill's bundle → the skill body appears in assembled instructions / loaded-skills audit. Add a multi-call merge/dedupe regression and a whole-run-cap-overflow disclosure regression.

### Claude's Discretion
- Exact keyword-scoring algorithm and relevance threshold for D-02 (term overlap, TF-style weighting, etc.) — research to recommend; must stay zero-token and deterministic.
- Exact import-scan depth/parsers per language for D-06 — start with the languages the built-in bundles cover; degrade gracefully (no parser → bundle-only grouping for that file).
- Whether new caps live as flat `ReviewConfig` fields or a nested `multicall:` sub-model.
- Exact sticky wording for routed/keyword/LLM skill-source disclosure and the prominent budget-reached alert.
- Plan/wave split (Thread 1 before Thread 2; loader+classify reorder unit tests vs multi-call orchestration vs docs pipeline fix).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline & requirements
- `.planning/REQUIREMENTS.md` — SKIL-01 (gap), ROUT-01, CLSF-01/02/03, OUTP-04, and **new ENGN-05/06/07** (multi-call); CUST-04 superseded note
- `.planning/phases/03-selective-skill-loading/03-CONTEXT.md` — original per-skill `applies-to` globs (D-03/D-04); **revised** by D-01/D-02 above
- `.planning/phases/07-customization-hardening/07-CONTEXT.md` — D-03 consumer `applies-to`; packed-set sequencing (D-19) — **reordered** by D-01
- `.planning/phases/07-customization-hardening/07-PATTERNS.md` — old pack → select_skills(packed) → classify order (now reordered)
- `.planning/phases/08-incremental-stateful-review-lifecycle/` — fingerprint dedupe + gate-over-open-set patterns reused by D-08

### Implementation seams (verified 2026-06-21)
- `src/prevue/review.py` — `run_review()` pack/select/classify/route/engine block (the reorder target)
- `src/prevue/skills/loader.py` — `select_skills` (keyword+LLM rework), `assemble_instructions`, `trim_packed_files`, `load_skills`
- `src/prevue/skills/models.py` — `Skill` model (`name`, `description`, `applies_to`, `bundle`, `body`, `source`) — name+desc drive D-02
- `src/prevue/classify/router.py` — `route()` + `ClassificationResult.bundles`
- `src/prevue/classify/llm_fallback.py` — `llm_classify()` — extend to also return relevant skill names (D-02 double-duty)
- `src/prevue/config.py` — `PrevueConfig`, `SkillsConfig`; `src/prevue/gate.py` — `ReviewConfig` (new caps land here)
- `src/prevue/models.py` — `ReviewRequest` (one diff/call), `ReviewResult` (merge N), `Finding`
- `src/prevue/fingerprint.py` — `fingerprint(path, title)` (Phase 8) — cross-call dedupe
- `src/prevue/engines/base.py` — `review()` / `classify()` interface; `engines/flow.py` `review_with_retry`
- `docs/ARCHITECTURE.md` — pipeline diagram (MUST update: new classify-first order + multi-call)

### Live validation
- gap-demo-sandbox PR #25 (gap demo), PR #26 — re-run after ship to confirm `GAP-DEMO-SKILL-LOADED` when `security` routes
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `select_skills()` / dedupe / sort in `loader.py` — extend with keyword scoring + LLM escalation (D-02), don't fork
- `trim_packed_files`, `assemble_instructions`, `load_skills` — reuse for post-select budget pass (D-04)
- `route()` + `ClassificationResult.bundles` — already computed; wire to selection
- `fingerprint(path, title)` — Phase 8 dedupe backstop, reused for cross-call merge (D-08)
- DIFF-03 prioritized file packing (`pack.py`) — reused for whole-run-cap overflow (D-10)
- `ThreadPoolExecutor` over the sync `engine.review()` — parallel calls (D-08); subprocess-bound so GIL is not a blocker

### Established Patterns
- Hybrid deterministic-first + LLM-fallback (classification) — D-02 mirrors this for skill selection
- Fail-closed skill load (`ValidationError` → red check); fail-closed neutral skip on budget overflow
- Sticky `skill_ratios` from `Counter(bundle)` over merged skills
- One sticky comment, batched COMMENT review POST (Phase 4)

### Integration Points
- The reorder (D-01) is the largest change: move classify+route ahead of pack/select in `run_review()`
- `llm_classify()` extended to return labels **and** relevant skill names (D-02)
- New caps in `ReviewConfig`; multi-call orchestration wraps the single `engine.review()` into an N-call loop/pool with merge+dedupe before gate
</code_context>

<specifics>
## Specific Ideas

- User explicitly wants the LLM classify call to **double as a skill selector** ("based on skill name and description") — the Agent Skills progressive-disclosure pattern; pass `name`+`description` only, never bodies, into selection.
- User priority order for multi-call: **quality + no hallucination first, then token efficiency** — drove D-05 (fewest cohesive near-full calls) and D-06 (import-aware grouping).
- Whole-run-cap budget-reached alert must be **prominent / easy to notice** (D-10), not a buried metadata line.
- User does not mind implementation cost on D-06 if it removes limitations (chose import-scan over cheaper directory grouping).
</specifics>

<deferred>
## Deferred Ideas

- **Embedding-based skill relevance** (vs keyword scoring) for D-02 — heavier; only if keyword floor proves too crude in practice.
- **Cross-call call-graph impact** beyond import-locality — stays out of scope (Out of Scope: full codebase graph).
- **Native GitHub PR labels from classification** (CUST-05) — separate v2 item.
- **SKIL-01 wording amend** in REQUIREMENTS traceability — planner may note that "matched bundle" now means classify-routed + B+D-selected, not glob-only.

None of these block this phase.
</deferred>

---

*Phase: 09-classification-skill-loading-multi-call-review*
*Context gathered: 2026-06-17; re-discussed 2026-06-21*
