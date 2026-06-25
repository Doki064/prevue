# Phase 9: Classification-aligned skill loading + multi-call review — Research

**Researched:** 2026-06-21
**Domain:** Internal pipeline refactor (classify-first reorder + hybrid skill selection) + multi-call review orchestration (split / merge / dedupe / optional parallelism) inside `src/prevue`
**Confidence:** HIGH — every claim below is grounded in the current source (read this session), not the stale prior research.

> This file **overwrites** the 2026-06-17 research, which described a *surgical post-classify union* design that the 2026-06-21 re-discussion superseded. The codebase was re-read from scratch this session (Phase 8 has since shipped). All seam locations, function signatures, and line references reflect the code **as it exists now**.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

> 2026-06-21 re-discussion supersedes the 2026-06-17 decisions. The earlier design (D-01 surgical union, D-02 whole-bundle expansion) is REPLACED by a full pipeline reorder + hybrid B+D skill selection. Kept from original: LLM-fallback participation, re-trim→neutral budget discipline, sticky audit, gap-demo-sandbox regression.

**Thread 1 — Skill loading: pipeline & selection**

- **D-01 (REORDER — classify-first):** Rebuild the pipeline so classification drives skill selection up front. New order:
  ```
  filter → classify(all changed files) → route → bundles
        → SELECT skills (D-02)
        → label-weighted pack (budget)
        → assemble instructions (selected skill bodies + packed diff)
        → review
  ```
  Deterministic classify stays **zero-token** for clear-cut PRs (glob-only on the full changed set, pre-pack); only ambiguous (unmatched) files hit the LLM fallback — unchanged cost model.

- **D-02 (B+D hybrid skill selection — supersedes whole-bundle union):** Select individual skills within routed bundles via deterministic-first, LLM-fallback (mirrors CLSF-01 + CLSF-02):
  - **Deterministic keyword floor (zero-token):** score each candidate skill's `name`+`description` (and `applies-to`) against diff content/paths; load above a relevance threshold.
  - **LLM escalation:** below-threshold skills **within a routed bundle** escalate to an LLM relevance check (name+desc only — no bodies). When the classify LLM fallback is **already firing**, the *same call* returns both labels and relevant skill names (double-duty, near-zero marginal cost).
  - **Gap-closure guard:** a routed bundle's genuinely-relevant skill is NEVER silently pruned — below-threshold routed skills escalate rather than drop.

- **D-03 (LLM fallback labels participate — kept):** Labels recovered by `llm_classify()` flow into `result_cls.bundles` and trigger the same routing + selection path as deterministic labels. One code path.

- **D-04 (Post-select budget — kept):** After selection + assembly, run the existing `trim_packed_files` loop + byte-limit guard (`MAX_PROMPT_BYTES`) before review. If still over budget → **fail-closed neutral skip** with disclosure.

**Thread 2 — Multi-call review**

- **D-05 (Call trigger & count — ENGN-05):** Bundle-derived with small-bundle merge. Group files by routed bundle, greedily **merge under-budget bundle groups** toward `max_tokens_per_call` until each call is near-full. `calls =` merged count, capped at `max_review_calls` (**default 1** → single call).

- **D-06 (Split unit & cross-file context — ENGN-06):** Bundle + lightweight import scan. Group by routed bundle, then co-locate files with direct import/reference links via a cheap static scan. Language-specific import parsing in scope; degrade to bundle-only grouping when no parser exists for a file.

- **D-07 (Per-call skill scope):** Each call carries the skills D-02 selected **for its own files** PLUS a small **configurable always-on guardrail set** (e.g. `security/committed-secrets`, authz) injected into every call.

- **D-08 (Merge / gate / output — ENGN-07):** Merge findings from all calls → **fingerprint dedupe (reuse `fingerprint(path, title)`)** → **one gate** over the union → **one sticky** with per-bundle token meta. `review_concurrency` **default 1 (sequential)**; parallel opt-in via `ThreadPoolExecutor`. **Fail-soft:** one call fails → keep other results, mark review `degraded → neutral`.

**Cap system**

- **D-09 (Caps):**
  - `max_tokens_per_call` — NEW — per-call input ceiling.
  - `max_total_run_tokens` — NEW — whole-run ceiling: `classify + Σ review calls ≤ cap`.
  - `max_review_calls` — NEW (ENGN-05) — call-count cap. **Default 1**.
  - `review_concurrency` — NEW (ENGN-07) — parallel cap. **Default 1** (sequential).
  - Existing, reused: `max_input_tokens` (120k, becomes default per-call budget), `output_reserve_tokens` (12k, per call), `budget_seconds` (300, per-call timeout), `max_inline_comments` (10, over merged findings).
  - All new caps live in `ReviewConfig` (gate.py) / surface via `prevue.yml` `review:` block.

- **D-10 (Whole-run-cap overflow):** When `classify + projected review` would exceed `max_total_run_tokens`: reuse **DIFF-03 prioritized packing** — fit as many calls/files as the cap allows by priority, review those, **disclose `N files not reviewed (run token budget reached)`** in the sticky. Conclusion = **neutral (partial)**, never a false fail. The budget-reached alert must be **prominent**, not a buried metadata line.

**Audit / regression**

- **D-11 (Sticky audit):** Sticky Metadata reflects final loaded skills post-selection; distinguishes routed vs keyword-vs-LLM sources where useful; (multi-call) shows per-bundle/per-call token meta. `skill_ratios` denominators use the full merged `load_skills()` set.

- **D-12 (Regression):** Keep the gap-demo-sandbox-shape regression (packed path NOT matching a skill's `applies-to`, but classify routes to the skill's bundle → skill body appears in assembled instructions / loaded-skills audit). Add a multi-call merge/dedupe regression and a whole-run-cap-overflow disclosure regression.

### Claude's Discretion

- Exact keyword-scoring algorithm and relevance threshold for D-02 (term overlap, TF-style weighting) — must stay zero-token and deterministic.
- Exact import-scan depth/parsers per language for D-06 — start with languages the built-in bundles cover; degrade gracefully (no parser → bundle-only grouping).
- Whether new caps live as flat `ReviewConfig` fields or a nested `multicall:` sub-model.
- Exact sticky wording for routed/keyword/LLM skill-source disclosure and the prominent budget-reached alert.
- Plan/wave split (Thread 1 before Thread 2).

### Deferred Ideas (OUT OF SCOPE)

- **Embedding-based skill relevance** (vs keyword scoring) for D-02 — only if keyword floor proves too crude.
- **Cross-call call-graph impact** beyond import-locality — out of scope (no full codebase graph).
- **Native GitHub PR labels from classification** (CUST-05) — separate v2 item.
- **SKIL-01 wording amend** in REQUIREMENTS traceability — planner may note "matched bundle" now means classify-routed + B+D-selected, not glob-only.
- Per-path severity overrides (CUST-01); loading skills from PR head (SKIL-04 unchanged); full call-graph impact analysis.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SKIL-01 (gap) | Skill loader loads matched skill **bundles**, not glob-only | Root-caused below: `select_skills()` is glob-only and never reads `result_cls.bundles`. Fix = classify-first reorder (D-01) + bundle-scoped selection (D-02). Seams: `review.py` lines 546–611, `loader.py:select_skills`. |
| ROUT-01 | Router maps labels → bundles with precedence | Already works (`router.py:route`). Phase 9 *consumes* `result_cls.bundles` to scope selection; no routing change needed. Default `routing: {}` means bundle id == label (verified). |
| CLSF-03 | Labels + matched rules auditable in output | Reorder must preserve the existing sticky audit (`result_cls` → `upsert_sticky`, review.py:783). D-11 extends it with skill-source provenance. |
| OUTP-04 | Summary shows tokens used + skills loaded vs skipped | `token_meta` + `skill_ratios` + `loaded_skills` (review.py:782–808). Multi-call adds per-bundle/per-call token meta; whole-run cap adds prominent budget alert (D-10/D-11). |
| ENGN-05 | Configurable multi-call (`max_review_calls`, default 1) | New cap in `ReviewConfig`; orchestrate N `engine.review()` calls. Single-call path unchanged when default 1 (D-05). |
| ENGN-06 | Context-preserving split (imports/bundle in same call) | Bundle grouping (already produced by route) + lightweight import scan via stdlib `ast` / regex (D-06). |
| ENGN-07 | Optional parallel calls (`review_concurrency`, default 1) | `ThreadPoolExecutor` over the sync subprocess-bound `engine.review()` (D-08); GIL released during subprocess wait. |
</phase_requirements>

## Summary

Phase 9 is **entirely internal Python refactoring** of `src/prevue` — there is **no new external dependency** and **no new technology to learn**. Every primitive the two threads need already exists in the codebase: classification (`classify` + `route`), skill loading/selection (`load_skills`/`select_skills`/`assemble_instructions`), budget packing (`pack_files`/`trim_packed_files`/`readmit_files`), the sync engine port (`EngineAdapter.review`), and the fingerprint dedupe (`fingerprint(path, title)`). The work is restructuring the orchestration in `review.py` and extending three pure functions (`select_skills`, `llm_classify`, `ReviewConfig`).

**Thread 1 (the gap):** Today `run_review()` packs first, then `select_skills()` matches skills by `applies-to` glob against the *packed* paths (review.py:546, 562, 583, 599), and only *after that* does `classify()`/`route()` run (review.py:674, 713) — its `result_cls.bundles` output is used **only** for the sticky Metadata and never feeds skill loading. That is the SKIL-01 gap exactly: a PR routed to the `security` bundle does not load `security/authn-authz.md` unless a changed path matches `**/auth/**`. The fix (D-01) moves classify+route ahead of pack/select, and (D-02) replaces glob-only `select_skills` with a bundle-scoped hybrid: deterministic keyword floor over `name`+`description`+`applies-to`, with LLM escalation for below-threshold skills inside routed bundles.

**Thread 2 (multi-call):** The single-call site is one line — `result = engine.review(req)` (review.py:731). Multi-call wraps that into an N-call loop: group `packed_files` by routed bundle (D-05/D-06), build one `ReviewRequest` per group (each with its own per-group `instructions` from the skills selected for its files plus a guardrail set, D-07), run them sequentially or via `ThreadPoolExecutor` (D-08/ENGN-07), then merge all `result.findings`, dedupe by `fingerprint(path, title)`, and feed the union into the existing single `apply_gate` → one sticky path (D-08). Default `max_review_calls=1` makes the loop run exactly once = today's behavior.

**Primary recommendation:** Sequence Thread 1 first (reorder + hybrid selection + gap-demo-sandbox regression), then Thread 2 (multi-call orchestration), then the docs/sticky updates. Keep the single-call default byte-identical to today's flow so the large `tests/test_review_flow.py` (98 KB) stays green as a regression backstop. Add new caps to `ReviewConfig` with backward-compatible defaults. Do not introduce asyncio — use `concurrent.futures.ThreadPoolExecutor` (subprocess-bound work, GIL released on wait).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Classify-first reorder | Orchestration (`review.py`) | — | `run_review()` owns stage sequencing; the gap is a sequencing bug, fixed in the orchestrator. |
| Bundle-scoped hybrid skill selection (D-02) | Skills (`loader.py:select_skills`) | Engine (LLM escalation) | Pure selection logic belongs in `loader.py`; LLM escalation reuses the `EngineAdapter.classify` port. |
| LLM double-duty (labels + skill names) | Classify fallback (`llm_fallback.py` / engine `classify`) | Skills | Extend the already-firing fallback call; skill-name selection rides the same subprocess invocation. |
| Diff split into bundle groups (D-05/D-06) | Orchestration + new split helper | Pack (`pack.py` weight reuse) | Splitting is run-level orchestration; reuses `make_file_weight` priority for greedy fill. |
| Import scan for cross-file locality (D-06) | New pure module (stdlib `ast`/regex) | Skills/Pack | Static analysis is self-contained; degrade to bundle-only when no parser. |
| Multi-call execution (seq/parallel, D-08) | Orchestration + `ThreadPoolExecutor` | Engine (`review()` unchanged) | Concurrency is an orchestration concern; the engine port stays synchronous. |
| Merge + dedupe findings (D-08) | Orchestration | `fingerprint.py` (reused) | Cross-call dedupe is the same fingerprint mechanism Phase 8 already uses for cross-push dedupe. |
| New caps + config surface (D-09) | Config (`gate.py:ReviewConfig`, `config.py`) | — | All review thresholds already live in `ReviewConfig`; new caps belong there. |
| Sticky audit + budget alert (D-10/D-11) | Output (`github/comments.py` sticky, `review.py` token_meta) | Gate | Presentation is owned by Python; review.py assembles the meta dict. |

## Standard Stack

This phase adds **no external libraries**. All dependencies are already pinned in `pyproject.toml` and used by the existing pipeline.

### Core (already installed — reuse)
| Library | Version (pinned) | Purpose in Phase 9 | Why Standard |
|---------|------------------|--------------------|--------------|
| pydantic | 2.13.* | New cap fields on `ReviewConfig`; multi-call config sub-model if chosen | Already the validation layer for every config/model in the project [VERIFIED: pyproject.toml] |
| pathspec | 1.1.* | `GitIgnoreSpec` already used by `select_skills`/`classify`/`make_file_weight` for glob matching; D-02 keyword scoring reuses `applies_to` | Already standard; do not add a second glob lib [VERIFIED: pyproject.toml] |
| unidiff | 0.7.* | Already used for hunk/region mapping; available if import-scan wants hunk-level context | Already the project's diff parser [VERIFIED: pyproject.toml] |
| python-frontmatter | 1.3.* | Skill `name`/`description` already parsed into `Skill` model — D-02 scores those fields | Already the skill loader [VERIFIED: pyproject.toml] |

### Supporting (Python stdlib — no install)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `concurrent.futures.ThreadPoolExecutor` | Parallel multi-call execution (ENGN-07) over subprocess-bound `engine.review()` | When `review_concurrency > 1`; cap workers at the config value [VERIFIED: python3 import check this session] |
| `ast` | Python import extraction for D-06 import scan (`import x`, `from x import y`) | Python files; the data/backend bundles cover `.py`. Degrade to regex/bundle-only for non-Python [VERIFIED: python3 import check] |
| `re` | Lightweight import/reference regex for JS/TS (`import … from "…"`, `require("…")`) and other languages D-06 covers | Non-Python files where `ast` does not apply [ASSUMED — exact per-language patterns are Claude's discretion per CONTEXT] |
| `hashlib` (via `fingerprint`) | Cross-call dedupe — already wrapped by `fingerprint(path, title)` | Merge step (D-08); call the existing helper, do not re-implement [VERIFIED: src/prevue/fingerprint.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ThreadPoolExecutor` | `asyncio` / `ProcessPoolExecutor` | Rejected — CLAUDE.md says "adapters stay sync; don't introduce asyncio until two+ engines run concurrently"; `engine.review()` is subprocess-bound so threads release the GIL on wait. Processes add pickling/IPC cost for no gain. [CITED: CLAUDE.md "Stack Patterns by Variant"] |
| stdlib `ast`/regex import scan | tree-sitter / language servers | Rejected for v1 — heavy dependency surface; CONTEXT D-06 explicitly says "degrade gracefully (no parser → bundle-only grouping)". Start minimal. [CITED: 09-CONTEXT.md D-06 discretion] |
| keyword scoring for D-02 | embedding similarity | Deferred by CONTEXT ("only if keyword floor proves too crude"). [CITED: 09-CONTEXT.md Deferred] |

**Installation:** None. No `uv add`. Verify the venv already resolves the pinned versions: `uv sync --locked`.

## Package Legitimacy Audit

> Not applicable — Phase 9 installs **no new external packages**. It is an internal refactor using already-pinned dependencies (pydantic 2.13.*, pathspec 1.1.*, unidiff 0.7.*, python-frontmatter 1.3.*) plus Python stdlib (`concurrent.futures`, `ast`, `re`, `hashlib`).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram — target pipeline (after D-01 reorder)

```
PR event
   │
   ▼
load_pr_context → fork guard (SECR-01) → load_config → should_skip
   │
   ▼
decide_scope (incremental/full/noop)  ── noop ─▶ _finish_noop_review
   │
   ▼
fetch_diff(_in_scope) → filter_diff ── empty ─▶ skip
   │
   ▼  CHANGED FILES (full set, pre-pack)
┌──────────────────────────────────────────────────────────┐
│ D-01 CLASSIFY-FIRST                                        │
│   classify(reduced.files, label_rules)   [zero-token]     │
│   llm_classify(unmatched) if ambiguous   [bills tokens;   │
│        D-02 double-duty: also returns relevant skill names]│
│   route(labels) → result_cls.bundles                      │
└──────────────────────────────────────────────────────────┘
   │  bundles + (optional) llm skill names
   ▼
┌──────────────────────────────────────────────────────────┐
│ D-02 SELECT SKILLS (bundle-scoped hybrid)                 │
│   load_skills() → all candidates                          │
│   for skill in skills:                                    │
│     keyword_score(name+desc+applies_to, diff) ≥ thresh?   │
│       → keep   (zero-token floor)                          │
│     else if skill.bundle in result_cls.bundles:           │
│       → escalate to LLM relevance (name+desc only)         │
│           (reuses the already-firing fallback call)        │
│       → keep if LLM says relevant   (gap-closure guard)    │
│     else → drop                                            │
│   union with glob select_skills for non-routed bundles    │
└──────────────────────────────────────────────────────────┘
   │  selected skills
   ▼
make_file_weight(label_rules, skills) → pack_files(budget)
   │
   ▼
assemble_instructions(BASELINE, selected) → trim_packed_files → readmit_files
   │   (D-04 byte-limit guard; over budget → neutral skip)
   ▼
┌──────────────────────────────────────────────────────────┐
│ THREAD 2 — MULTI-CALL (default max_review_calls=1)        │
│   split packed_files into bundle groups (D-05)            │
│     + import-scan co-location (D-06)                      │
│     + greedy merge under-budget groups → near-full calls  │
│     + cap at max_review_calls / max_total_run_tokens(D-10)│
│   per group: ReviewRequest(instructions = group skills    │
│              + guardrail set D-07)                        │
│   execute: sequential (concurrency 1) OR ThreadPoolExec   │
│   fail-soft: failed call → skip its findings, degrade     │
│   merge findings → dedupe fingerprint(path,title) (D-08)  │
└──────────────────────────────────────────────────────────┘
   │  merged + deduped findings
   ▼
_open_set_findings (carry priors) → suppress dismissed → reconcile positions
   │
   ▼
apply_gate (ONE gate over union)  → post_inline_review → upsert_sticky → check_run
                                     (D-11 per-call token meta + D-10 budget alert)
```

### Recommended Structure (new/changed modules)
```
src/prevue/
├── review.py                # MAJOR: reorder run_review(); add multi-call loop
├── skills/
│   ├── loader.py            # select_skills → add keyword scoring + LLM escalation (D-02)
│   └── selection.py         # NEW (optional): pure keyword_score() + threshold helpers
├── classify/
│   └── llm_fallback.py      # llm_classify → optionally also return relevant skill names (D-02)
├── engines/
│   └── base.py              # classify() port may gain optional skill-name return (or new method)
├── multicall.py             # NEW: split_into_calls(), execute_calls(), merge_findings()
├── importscan.py            # NEW: extract_imports(path, patch) → referenced paths (D-06)
└── gate.py                  # ReviewConfig: new caps (D-09)
```

### Pattern 1: Hybrid deterministic-first + LLM-fallback (mirror classification)
**What:** D-02 selection copies the proven CLSF-01/CLSF-02 shape: a zero-token deterministic floor, LLM only for the ambiguous remainder.
**When to use:** Every skill-selection decision.
**Example (target shape, derived from existing `select_skills` + `llm_classify`):**
```python
# Source: pattern mirrors src/prevue/classify/llm_fallback.py:llm_classify (this session)
def select_skills_hybrid(skills, paths, diff_text, bundles, *, adapter=None,
                         llm_skill_names: set[str] | None = None):
    selected, escalate = [], []
    for skill in skills:
        if keyword_score(skill, paths, diff_text) >= THRESHOLD:
            selected.append(skill)                      # zero-token floor
        elif skill.bundle in bundles:                   # routed but low score
            escalate.append(skill)                      # gap-closure guard: never drop silently
    if escalate:
        # Prefer names already returned by the firing classify fallback (double-duty);
        # only make a NEW call if none are available and adapter is provided.
        names = llm_skill_names if llm_skill_names is not None else _llm_relevant(escalate, adapter)
        selected += [s for s in escalate if s.name in names]
    return _dedupe_sort(selected)   # reuse loader.py dedupe/sort (canonical_index, filename)
```

### Pattern 2: Bundle-grouped multi-call with greedy merge
**What:** Group `packed_files` by routed bundle; merge under-budget groups toward `max_tokens_per_call`; cap at `max_review_calls`.
**When to use:** Thread 2 split step.
**Example:**
```python
# Source: composition over existing pack.estimate_file_prompt_tokens + route() bundles
def split_into_calls(packed_files, bundles, file_bundle, cfg):
    groups = group_by_bundle(packed_files, file_bundle)        # bundle → [files]
    groups = colocate_imports(groups, file_bundle)             # D-06 import scan
    calls = greedy_merge(groups, max_tokens=cfg.max_tokens_per_call)
    return calls[: cfg.max_review_calls]                       # default 1 → single call
```

### Pattern 3: Sequential-or-parallel execution with fail-soft
```python
# Source: concurrent.futures stdlib (verified available this session)
def execute_calls(reqs, engine, concurrency):
    results, failures = [], 0
    if concurrency <= 1:
        for req in reqs:
            try: results.append(engine.review(req))
            except (EngineFailure, AuthError): failures += 1   # fail-soft, keep others
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(engine.review, r) for r in reqs]
            for f in as_completed(futs):
                try: results.append(f.result())
                except (EngineFailure, AuthError): failures += 1
    return results, failures   # failures>0 → degrade → neutral (D-08)
```

### Pattern 4: Cross-call merge + fingerprint dedupe (reuse Phase 8)
```python
# Source: src/prevue/fingerprint.py (this session) — same mechanism as cross-push dedupe
def merge_findings(results):
    seen, merged = set(), []
    for r in results:
        for f in r.findings:
            fp = fingerprint(f.path, f.title)
            if fp in seen: continue
            seen.add(fp); merged.append(f)
    return merged   # feed into existing _open_set_findings → apply_gate (one gate)
```

### Anti-Patterns to Avoid
- **Calling `classify()` on the packed set (status quo bug):** classify must run on the **full filtered changed set** pre-pack (D-01), else dropped files never contribute labels/bundles. Today's code classifies `packed_files` (review.py:674) — the reorder must change this input to `reduced.files`.
- **Re-implementing dedupe:** use `fingerprint(path, title)`; do not write a new hash. There is also `_dedupe_findings_by_location` (review.py:160) for (path,line,side) collisions — the open-set path already handles location collisions; cross-call merge handles title collisions.
- **asyncio:** forbidden by CLAUDE.md until multiple engines run concurrently; use threads.
- **Mutating module-level prompt state:** per-call `instructions` must ride on each `ReviewRequest` (review.py:722 already does this per the WR-05 note) — do not stuff per-call skills into a global.
- **Letting a parallel call failure fail the whole run:** D-08 mandates fail-soft (keep good findings, degrade to neutral).
- **Forgetting the `noop` and `incremental` paths:** the reorder must not break `_finish_noop_review` (review.py:316) or the incremental scope logic (review.py:436–453) — both run before/around the classify+pack block.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding identity / dedupe | new hash of finding fields | `fingerprint(path, title)` (fingerprint.py) | NFKC+casefold normalization already handles rephrasing; Phase 8 depends on it |
| Glob matching for skill `applies_to` / keyword paths | custom `**` matcher | `pathspec.GitIgnoreSpec.from_lines(...).check_file(p).include` | Stdlib `fnmatch` mishandles `**`; project standardized on `check_file().include` (negation-safe) — see loader.py:154 note |
| Per-file token cost for greedy split | byte counting in the splitter | `pack.estimate_file_prompt_tokens(f)` + `estimate_prompt_overhead_tokens` | Matches the assembly the engine actually sends; prevents over/under-pack |
| Budget trimming after selection | new trim loop | `trim_packed_files` / `readmit_files` (pack.py) | Already battle-tested in the re-admission cascade (review.py:548–611) |
| Label → bundle mapping | new routing | `route()` (router.py) | ROUT-01 precedence already correct; default `routing:{}` → bundle==label |
| Parallel subprocess orchestration | manual thread/Process mgmt | `concurrent.futures.ThreadPoolExecutor` | stdlib, GIL released on subprocess wait; bounded by `max_workers` |
| Gate over merged findings | per-call gating | one `apply_gate(union)` (gate.py) | D-08 requires a single gate/sticky over the union; per-call gating would double-count |

**Key insight:** This phase is a *recomposition* of existing well-tested functions, not new machinery. The risk is in **wiring order and budget bookkeeping**, not in any algorithm. Maximize reuse; the only genuinely new code is `keyword_score`, the import scan, and the split/execute/merge orchestration.

## Common Pitfalls

### Pitfall 1: classify still runs on packed_files after reorder
**What goes wrong:** Files dropped by packing never contribute labels → bundles, so a security file dropped for budget silently disables the security bundle.
**Why it happens:** Copy-paste of `classify(packed_files, ...)` (review.py:674) into the new position.
**How to avoid:** classify on `reduced.files` (full filtered set) BEFORE packing (D-01). Pack-weighting still uses the same selected skills.
**Warning signs:** Test "large PR drops a security file" shows no security skills loaded.

### Pitfall 2: LLM fallback now runs pre-pack → cost/scope change
**What goes wrong:** Moving classify before pack means `llm_classify(unmatched)` sees the full unmatched set, not the packed-unmatched subset — potentially more files → more tokens.
**Why it happens:** The reorder changes what "unmatched" means.
**How to avoid:** Deterministic classify is glob-only/zero-token on the full set (fine). The LLM fallback still only sees *unmatched* files; CONTEXT D-01 explicitly accepts this ("LLM fallback still only sees the small unmatched set"). Account for it in `max_total_run_tokens` (D-09/D-10). Verify `estimate_classify_tokens` is billed on the pre-pack unmatched set.
**Warning signs:** classify token_meta jumps on PRs with many unmatched-but-droppable files.

### Pitfall 3: Per-call skill scope breaks the global sticky audit
**What goes wrong:** Each call carries different skills (D-07), but `loaded_skills`/`skill_ratios` (review.py:782–793) expect one `matched` list.
**Why it happens:** Multi-call has N skill sets, the sticky has one.
**How to avoid:** Build the sticky audit from the **union** of per-call selected skills (D-11: `skill_ratios` denominators use full `load_skills()` set). Compute `matched = dedupe(union of all call skill sets)` for the audit even though each call only sends its own.
**Warning signs:** Sticky shows fewer skills than were actually used across calls.

### Pitfall 4: Fingerprint merge hides a real escalation at the same location
**What goes wrong:** Two calls report the same (path,title) at different severities; naive fingerprint dedupe keeps the first, dropping a higher-severity duplicate.
**Why it happens:** `fingerprint(path, title)` ignores severity and line.
**How to avoid:** When merging, on fingerprint collision keep the higher-severity finding (mirror `_dedupe_findings_by_location`'s SEVERITY_RANK tie-break, review.py:160–172). Then the existing open-set/gate logic handles the rest.
**Warning signs:** A call's `error` finding silently downgraded to another call's `warning`.

### Pitfall 5: Multi-call double-counts review tokens / breaks token_meta
**What goes wrong:** `engine_meta["tokens"]["review"]` is per-call; the sticky expects one number.
**Why it happens:** `flow.review_with_retry` returns per-call token meta (flow.py:15–34).
**How to avoid:** Sum `review` token estimates across calls into the aggregate `token_meta` (review.py:794), and add per-call/per-bundle breakdown for D-11. Keep `classify` separate as today.
**Warning signs:** Token transparency (OUTP-04) under-reports on multi-call runs.

### Pitfall 6: Import scan crashes on syntactically-invalid PR diffs
**What goes wrong:** `ast.parse` raises `SyntaxError` on a partial/invalid hunk (you only have the diff, not the full file).
**Why it happens:** Diffs are fragments; `ast` needs whole modules.
**How to avoid:** D-06 operates on *changed-file paths* and *patch text*, not full ASTs — extract import statements with a tolerant regex over patch added-lines, or parse only when you have full content. Wrap any `ast.parse` in try/except → degrade to bundle-only grouping for that file. (CONTEXT D-06: "no parser → bundle-only grouping".)
**Warning signs:** A run errors out instead of degrading on an exotic file.

### Pitfall 7: `routing: {}` assumption — bundle id equals label
**What goes wrong:** Code assumes `result_cls.bundles` contains arbitrary ids; a consumer routing override could remap `security → my-security-bundle`.
**Why it happens:** Default `routing:{}` makes bundle==label (verified: default_rules.yml), but consumers can override (ROUT-01).
**How to avoid:** D-02 selection must filter skills by `skill.bundle in result_cls.bundles` (the *routed* bundle ids), NOT by label. `route()` already resolves the mapping; consume its output, not the labels.
**Warning signs:** A consumer with a custom routing map loads the wrong/no skills.

## Code Examples

### Current single-call site (the thing multi-call wraps)
```python
# Source: src/prevue/review.py:731 (this session)
result = engine.review(req)
result.engine_meta["engine"] = engine.name
```

### Current glob-only selection (the gap — D-02 replaces this)
```python
# Source: src/prevue/skills/loader.py:145 (this session)
def select_skills(skills: list[Skill], paths: list[str]) -> list[Skill]:
    """Select skills whose applies-to globs match any changed path (D-03/D-04)."""
    matched = []
    for skill in skills:
        spec = GitIgnoreSpec.from_lines(skill.applies_to)
        if not any(spec.check_file(path).include for path in paths):
            continue   # ← glob-only; never consults result_cls.bundles → SKIL-01 gap
        ...
```

### Current classify/route placement (D-01 moves these above pack/select)
```python
# Source: src/prevue/review.py:674,713 (this session)
result_cls = classify(packed_files, ruleset.label_rules)   # ← uses PACKED set; D-01 → reduced.files
# ... llm_classify(unmatched_packed) ...
result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
# bundles used only for sticky (review.py:783) — never feeds select_skills → the gap
```

### Reuse target: fingerprint for cross-call dedupe
```python
# Source: src/prevue/fingerprint.py:17 (this session)
def fingerprint(path: str, title: str) -> str:
    payload = f"{path}|{normalize_title(title)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

### New cap fields (target — Claude's discretion: flat vs nested)
```python
# Source: extends src/prevue/gate.py:19 ReviewConfig (this session)
class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # ... existing fields ...
    max_review_calls: int = Field(default=1, ge=1)          # ENGN-05
    review_concurrency: int = Field(default=1, ge=1)         # ENGN-07
    max_tokens_per_call: int = Field(default=120000, ge=1)   # D-09 (= max_input_tokens default)
    max_total_run_tokens: int = Field(default=480000, ge=1)  # D-09 whole-run ceiling
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pack → select_skills(packed) → classify (metadata only) | classify(full) → route → select(bundle-scoped) → pack | This phase (D-01) | Closes SKIL-01; classification finally drives loading |
| glob-only skill match | hybrid keyword floor + LLM escalation within routed bundles | This phase (D-02) | Whole-run token optimization; gap-closure guard |
| single `engine.review()` | configurable N-call split/merge/dedupe | This phase (ENGN-05/06/07) | Large PRs reviewable; optional parallelism |
| surgical post-classify union (2026-06-17 design) | full reorder + B+D selection | superseded 2026-06-21 | Prior 09-RESEARCH.md is obsolete (this file overwrites it) |

**Deprecated/outdated:**
- The 2026-06-17 "surgical union" recommendation (old 09-RESEARCH.md) — superseded by D-01/D-02. Do not plan from it.
- `routing: {}` is still the shipped default (verified) — bundle ids equal labels unless a consumer overrides.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | JS/TS import extraction can be done with a tolerant regex over patch added-lines (`import…from`, `require(…)`) | Supporting / Pitfall 6 | If regex misses a reference, two related files split into different calls → cross-file context loss (degrades quality, not correctness). CONTEXT marks parser choice as Claude's discretion. |
| A2 | Engine `classify()` can be extended to also return relevant skill names in the same call (double-duty) without breaking the existing `parse_classify_response` contract | Pattern 1 / D-02 | If the CLI cannot reliably return both in one structured response, D-02 needs a separate (still name+desc-only) escalation call — slightly higher token cost, same correctness. |
| A3 | `max_total_run_tokens` default (480k) is a reasonable whole-run ceiling | Code Examples (caps) | Wrong default could over/under-constrain; user should confirm. Existing `max_input_tokens` is 120k per call; 4× is a starting point only. |
| A4 | Per-bundle/per-call token meta can be threaded through the existing `token_meta` dict and `upsert_sticky` kwargs without a sticky schema break | Pitfall 5 / D-11 | If the sticky renderer needs a structural change, more output-layer work than estimated. |

**If this table is empty:** it is not — these four need confirmation during planning/discuss before becoming locked.

## Open Questions

1. **Does the Copilot CLI reliably return both labels and skill-relevance in one structured JSON response (D-02 double-duty)?**
   - What we know: `adapter.classify()` returns `{path: label}` JSON parsed by `parse_classify_response` (prompt.py:194). The prompt is fully controllable.
   - What's unclear: whether adding a `skills: [...]` field to the same response stays reliable across engines (Copilot/Claude/Cursor/Gemini all implement the port).
   - Recommendation: design D-02 so it *prefers* names from the firing call but *falls back* to a separate name+desc escalation call if the combined response is missing/malformed (A2). Keep both paths tested.

2. **Flat caps vs nested `multicall:` sub-model (CONTEXT discretion)?**
   - What we know: all current review knobs are flat on `ReviewConfig` with `extra="forbid"`.
   - Recommendation: flat fields keep parity with existing config and avoid a nested validator; choose nested only if the multi-call knob count grows past ~4. Lean flat for v1.

3. **Whole-run-cap overflow interaction with incremental scope (D-10).**
   - What we know: incremental runs already scope to delta paths; DIFF-03 prioritized packing exists (`pack_files`).
   - What's unclear: ordering — does the run-token cap apply before or after incremental scoping?
   - Recommendation: apply `max_total_run_tokens` AFTER incremental scoping (scope first, then budget the scoped set), reusing `pack_files` priority for the "fit as many as the cap allows" step. Disclose the prominent budget-reached alert (D-10).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All framework code | ✓ | ≥3.12 (pyproject) | — |
| `concurrent.futures` (stdlib) | Parallel multi-call (ENGN-07) | ✓ | stdlib | sequential (concurrency=1) |
| `ast` (stdlib) | Python import scan (D-06) | ✓ | stdlib | regex / bundle-only grouping |
| pydantic / pathspec / unidiff / python-frontmatter | All reuse | ✓ (pinned) | 2.13.* / 1.1.* / 0.7.* / 1.3.* | — |
| Copilot CLI (`@github/copilot`) | LLM escalation (D-02) + each review call | ✓ in Actions | 1.0.x | escalation degrades to keyword-floor-only; tests mock the adapter |

**Missing dependencies with no fallback:** none — this phase ships entirely on existing deps + stdlib.
**Missing dependencies with fallback:** Copilot CLI is only present on the runner; all unit tests mock `EngineAdapter`, so local TDD needs no live CLI.

## Validation Architecture

> `workflow.nyquist_validation` not found in `.planning/config.json` lookup path during research; treated as ENABLED per the absent=enabled rule.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.* + pytest-cov 7.1.* (CLAUDE.md dev tools) |
| Config file | `pyproject.toml` (project standard); test fixtures in `tests/conftest.py` |
| Quick run command | `uv run pytest tests/test_skills_loader.py tests/test_classify_router.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKIL-01 (gap) | Classified bundle ≠ glob path → bundle skill still loads (gap-demo-sandbox shape) | unit | `uv run pytest tests/test_skills_loader.py -k bundle_routed -x` | ❌ Wave 0 (new test) |
| SKIL-01 (gap) | Reorder: classify runs on full set, not packed | integration | `uv run pytest tests/test_review_flow.py -k classify_first -x` | ❌ Wave 0 |
| D-02 | Keyword floor selects high-score skill; below-threshold routed skill escalates not drops | unit | `uv run pytest tests/test_skills_loader.py -k hybrid_select -x` | ❌ Wave 0 |
| D-03 | LLM fallback label triggers same bundle selection as deterministic | unit/integration | `uv run pytest tests/test_review_flow.py -k fallback_bundle -x` | ❌ Wave 0 |
| D-04 | Post-select over-budget → neutral skip | integration | `uv run pytest tests/test_review_flow.py -k budget_neutral -x` | ✅ existing budget tests adapt |
| ENGN-05 | `max_review_calls=1` → exactly one `engine.review` call (unchanged path) | unit | `uv run pytest tests/test_multicall.py -k single_call -x` | ❌ Wave 0 |
| ENGN-06 | Bundle grouping + import co-location keeps related files together | unit | `uv run pytest tests/test_multicall.py -k split -x` | ❌ Wave 0 |
| ENGN-06 | Import scan degrades to bundle-only on unparseable file | unit | `uv run pytest tests/test_importscan.py -x` | ❌ Wave 0 |
| ENGN-07 | `review_concurrency>1` runs calls via pool; failure is fail-soft | unit | `uv run pytest tests/test_multicall.py -k parallel -x` | ❌ Wave 0 |
| ENGN-07 / D-08 | Cross-call merge dedupes by fingerprint; severity tie-break | unit | `uv run pytest tests/test_multicall.py -k merge_dedupe -x` | ❌ Wave 0 |
| OUTP-04 / D-11 | Sticky shows union skills + per-call token meta; prominent budget alert | integration | `uv run pytest tests/test_review_flow.py -k sticky_multicall -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_skills_loader.py tests/test_multicall.py tests/test_importscan.py -x` + `uv run ruff check`
- **Per wave merge:** `uv run pytest` (full suite; `test_review_flow.py` is the integration backstop)
- **Phase gate:** Full suite green + live re-run of gap-demo-sandbox PR #25/#26 confirming `GAP-DEMO-SKILL-LOADED` finding appears when `security` routes.

### Wave 0 Gaps
- [ ] `tests/test_multicall.py` — split/execute/merge/dedupe (ENGN-05/06/07, D-08)
- [ ] `tests/test_importscan.py` — import extraction + graceful degrade (D-06)
- [ ] `tests/test_skills_loader.py` — add hybrid-select + bundle-routed cases (SKIL-01 gap, D-02)
- [ ] `tests/test_review_flow.py` — add classify-first reorder + gap-demo-sandbox regression + multi-call sticky (D-12)
- [ ] Conftest fixtures: a skill whose `applies_to` does NOT match a path, but whose bundle is routed (the gap shape)

## Security Domain

> `security_enforcement` not explicitly disabled in config; included per absent=enabled. This phase touches prompt assembly and skill loading — both security-relevant.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Reorder must preserve SKIL-04 (skills from trusted base ref only) and SECR-01 (fork guard) — both run before the classify/pack block; do not move them after. |
| V5 Input Validation | yes | Skill frontmatter is already pydantic-validated (`Skill.model_validate`); diff/paths are UNTRUSTED DATA — keep all multi-call prompts going through `build_prompt` fencing (prompt.py). |
| V5 Injection (prompt) | yes | SECR-02: per-call prompts must reuse `_safe_diff_block` / `INSTRUCTION_REASSERTION`. Import scan reads patch text — treat as untrusted, never `eval`/`exec`; `ast.parse` only (no execution). |
| V6 Cryptography | no | `fingerprint` uses sha256 for identity, not secrets — unchanged. |
| V12 Files/Resources | yes | Import scan must not follow paths outside the diff; skill loader symlink guards (loader.py:59) stay intact. |

### Known Threat Patterns for {Python framework / GitHub Actions}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via diff content reaching per-call prompts | Tampering | All N calls route through `build_prompt` UNTRUSTED DATA fencing + reassertion (prompt.py) — no raw concatenation |
| PR-head skill/config weakening review (SKIL-04 bypass) | EoP | Reorder keeps `_consumer_skills_root` base-ref guard (review.py:77) and `resolve_consumer_config_path` sentinel (config.py:80) untouched |
| Code execution via import scan parsing untrusted diff | Tampering/EoP | `ast.parse` only (parse, never exec); regex fallback is read-only; wrap in try/except |
| Token-cost DoS via huge PR forcing many parallel subprocesses | DoS | `review_concurrency` cap + `max_review_calls` cap + `max_total_run_tokens` whole-run ceiling (D-09/D-10) |
| Secret leakage in multi-call stderr | Info Disclosure | Existing `sanitize_stderr` / token redaction in EngineFailure stays — each call uses the same adapter invoke path |

## Sources

### Primary (HIGH confidence — read this session)
- `src/prevue/review.py` — `run_review()` full orchestration; gap at lines 546/562/674/713; single-call at 731
- `src/prevue/skills/loader.py` — `select_skills` (glob-only, line 145), `assemble_instructions`, `load_skills`
- `src/prevue/skills/models.py` — `Skill` (name/description/applies_to/bundle/body/source)
- `src/prevue/classify/{classifier,router,llm_fallback,models}.py` — classify/route/fallback + `routing:{}` default
- `src/prevue/pack.py` — `make_file_weight`, `pack_files`, `trim_packed_files`, `readmit_files`, `estimate_file_prompt_tokens`
- `src/prevue/gate.py` — `ReviewConfig` (new caps target), `apply_gate`, `SEVERITY_RANK`
- `src/prevue/fingerprint.py` — `fingerprint(path, title)` dedupe
- `src/prevue/engines/{base,flow,prompt,copilot_cli,tokens}.py` — engine port, retry flow, prompt fencing, token estimate
- `src/prevue/config.py` — `PrevueConfig`/`ReviewConfig` load path
- `pyproject.toml` — dependency pins (pydantic/pathspec/unidiff/python-frontmatter); `requires-python >=3.12`
- `.planning/phases/09-.../09-CONTEXT.md` — D-01..D-12 decisions (2026-06-21 re-discussion)
- `.planning/REQUIREMENTS.md` — SKIL-01, ROUT-01, CLSF-03, OUTP-04, ENGN-05/06/07
- `docs/ARCHITECTURE.md` — current pipeline diagram (MUST update to classify-first + multi-call)

### Secondary (verified this session)
- `python3 -c "import concurrent.futures, ast"` → stdlib available
- CLAUDE.md "Stack Patterns by Variant" — adapters stay sync; ThreadPoolExecutor over subprocess; no asyncio

### Tertiary (LOW confidence — flagged in Assumptions Log)
- JS/TS import regex patterns (A1) and combined classify+skill-name response (A2) — to confirm during planning

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all reuse, verified against pyproject + source
- Architecture (reorder + gap location): HIGH — exact lines read this session
- Multi-call orchestration shape: HIGH for composition; MEDIUM on engine double-duty (A2) and import-scan parsing (A1)
- Pitfalls: HIGH — derived from the actual budget/open-set/token bookkeeping in review.py

**Research date:** 2026-06-21
**Valid until:** ~2026-07-21 (internal-refactor, stable deps; re-verify only if review.py is refactored before planning)
