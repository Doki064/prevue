# Phase 9: Classification-aligned skill loading + multi-call review - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21 (re-discussion; original context 2026-06-17)
**Phase:** 9-classification-skill-loading-multi-call-review
**Areas discussed:** Selection model, Routed-bundle expansion, LLM fallback labels, Post-union budget, Skill-selection granularity, Multi-call trigger, Split unit, Per-call skill scope, Merge & parallel, Cap system, Run-cap overflow

> User directed: discard all "locked" framing from the 2026-06-17 context and force-discuss everything again. Both threads (skill-loading gap + multi-call review) re-opened.

---

## Selection model (skill-loading pipeline)

| Option | Description | Selected |
|--------|-------------|----------|
| Post-classify surgical union | Keep current order; union routed-bundle skills after route(), re-trim before review | |
| Full pipeline reorder | Classify ALL files first; labels drive packing weight + skill selection before pack | ✓ |
| Hybrid: route early, pack order kept | Classify+route early but keep packing order | |

**User's choice:** "Choose what clean and optimal and performant wise" → then explicitly: "I actually want to rebuild the pipeline order, but still need to keep it performant and optimal." → Full reorder (classify-first).
**Notes:** Reorder keeps deterministic classify zero-token for clear-cut PRs; only ambiguous files hit LLM fallback (cost model unchanged).

---

## Routed-bundle expansion / skill-selection granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Whole-bundle load (all skills in routed bundle, ignore applies-to) | Gap-safe, zero-token, coarse | |
| applies-to match OR bundle-default flag | Per-skill frontmatter opt-in | |
| Keep glob-only | Rely on labels + authors fixing narrow globs (re-gaps) | |
| LLM select by name+description | Pass skill name+desc to LLM, load chosen subset | |
| **B+D hybrid: keyword floor + LLM escalation** | Deterministic keyword match floor, LLM fallback for ambiguous — mirrors classification architecture | ✓ |

**User's choice:** "Doesn't LLM call for classify mean to fix this?" → clarified that LLM fixes the LABEL not the LOADING → "is there a way classify LLM call can help pick only relevant skill, not whole bundle? Maybe based on skill name and description?" → "Is A-Hybrid a combination of B-LLM select and D-deterministic match?" → "Go with B+D then."
**Notes:** User added the master principle: "Try to optimize token at a whole run (classify + review) not just a phase." Loading whole bundles bloats the review prompt; B+D keyword floor trims irrelevant skill bodies, LLM escalation prevents silently dropping a routed bundle's relevant skill (gap-closure guard). When the classify LLM fallback fires, the same call returns labels + relevant skill names (double-duty).

---

## LLM fallback labels

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — fallback participates | LLM-recovered labels trigger same routing + skill selection | ✓ |
| No — deterministic only | Fallback affects Metadata only | |

**User's choice:** Yes — fallback participates.
**Notes:** One code path; deterministic and fallback behave identically.

---

## Post-select budget

| Option | Description | Selected |
|--------|-------------|----------|
| Re-trim files, then neutral skip | Existing trim loop + byte guard; fail-closed neutral if still over | ✓ |
| Skills win — trim files first/harder | Protect skills, drop diff lines | |
| Drop lowest-priority routed skills | Keep files, shed skills | |

**User's choice:** Re-trim files, then neutral skip.
**Notes:** Consistent with existing fail-closed discipline.

---

## Multi-call trigger & count (ENGN-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle-derived, capped | calls = min(bundles, max_review_calls) | |
| Budget-overflow only | Single call unless over budget | |
| **Bundle-derived, merge small bundles** | Group by bundle, bin-pack toward per-call budget, fewest cohesive calls | ✓ |

**User's choice:** "Which option will review has good quality, no hallucination, and still token-efficient? Also I think we will need a cap for token per call, and a cap for whole run." → Claude chose merge-small-bundles on quality/hallucination grounds (cohesive near-full calls minimize fragmentation + overhead).
**Notes:** User requested explicit cap inventory (per-call, whole-run, and any others).

---

## Split unit & cross-file context (ENGN-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle-aligned, document cross-bundle limit | Cheapest, accepts import gaps | |
| Bundle + same-directory cohesion | Keep dir together | |
| **Bundle + lightweight import scan** | Co-locate mutually-importing files via static scan | ✓ |

**User's choice:** "I actually don't mind implementation cost, as long as it can run best with less limitation. By that, I think C is the choice here?" → C (import scan).
**Notes:** Language-specific import parsing accepted as in-scope cost.

---

## Per-call skill scope (M3)

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle-selected + always-on guardrails | Selected skills + injected secrets/authz set every call | ✓ |
| Only its own selected skills | Minimum tokens, guardrail may be absent in some calls | |
| Full selected set every call | Consistent, N× skill cost | |

**User's choice:** Bundle-selected + always-on guardrails.
**Notes:** Max savings while keeping universal safety checks in every call.

---

## Merge & parallel posture (ENGN-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Union+dedupe, fail-soft, sequential default | Merge → fingerprint dedupe → one gate → one sticky; seq default; one call fails → partial+neutral | ✓ |
| Union+dedupe, fail-hard, sequential default | Any call failure fails whole review | |
| Parallel default on | concurrency >1 by default | |

**User's choice:** Union+dedupe, fail-soft, sequential default.
**Notes:** Reuses Phase 8 fingerprint dedupe; parallel opt-in via ThreadPoolExecutor.

---

## Whole-run-cap overflow

| Option | Description | Selected |
|--------|-------------|----------|
| Prioritized pack + disclose + review what fits | DIFF-03 packing, review by priority, disclose N unreviewed, neutral(partial) | ✓ |
| Neutral skip whole review | All-or-nothing | |
| Drop skills before dropping files | Coverage over skill context | |

**User's choice:** "A. And make the budget reached alert easy to notice."
**Notes:** Budget-reached alert must be prominent in sticky, not a buried metadata line.

## Claude's Discretion

- Keyword-scoring algorithm + relevance threshold for B+D selection (must stay zero-token/deterministic).
- Import-scan depth/parsers per language; graceful degradation when no parser available.
- Flat `ReviewConfig` fields vs nested `multicall:` sub-model for new caps.
- Sticky wording for routed/keyword/LLM skill-source disclosure + the prominent budget-reached alert.
- Plan/wave split (Thread 1 before Thread 2).

## Deferred Ideas

- Embedding-based skill relevance (vs keyword) — only if keyword floor too crude.
- Cross-call call-graph impact beyond import-locality — out of scope.
- Native GitHub PR labels from classification (CUST-05) — v2.
- SKIL-01 traceability wording amend — planner may note "matched bundle" now means classify-routed + B+D-selected.
