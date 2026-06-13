# Phase 4: Structured Findings & Merge Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 4-Structured Findings & Merge Gate
**Areas discussed:** Engine JSON contract & degrade ladder, Verdict & merge-gate semantics, Severity thresholds & config surface, Inline placement fallback & comment budget, Summary findings-overview layout

---

## Engine JSON contract & degrade ladder

| Option | Description | Selected |
|--------|-------------|----------|
| Single response: summary + fenced JSON | One call; prose + one ```json fence; summary survives malformed JSON | ✓ |
| JSON-only output | Single JSON doc; one syntax error kills summary too | |
| Two engine calls | Robust separation; doubles token spend | |

**User's choice:** Single response: summary + fenced JSON (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| One retry with error feedback | Re-invoke once with validation error + schema reminder; 2x worst case | ✓ |
| No retry — degrade immediately | Cheapest; loses recoverable findings | |
| Two retries | 3x worst-case spend, weak marginal gain | |

**User's choice:** One retry with error feedback (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Salvage valid, drop invalid | Per-finding pydantic validation; dropped count in Metadata | ✓ |
| All-or-nothing | Any invalid finding rejects the array | |
| Salvage + coerce near-misses | Repairs slips; coercion is guesswork | |

**User's choice:** Salvage valid, drop invalid (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Summary + neutral check + visible notice | Prose posts, Metadata notes parse failure, check neutral; hard failures stay D-09 red-run | ✓ |
| Summary + neutral check, silent | No notice; degraded indistinguishable from clean | |
| Treat as engine failure (red run) | Violates ENGN-03 | |

**User's choice:** Summary + neutral check + visible notice (recommended)

---

## Verdict & merge-gate semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Always-green informational | Check success regardless of findings; opt-in blocking | |
| Neutral when findings exist | No findings → success; findings → neutral yellow nudge | ✓ |
| Blocking on by default at error severity | Strongest gate; against opt-in wording | |

**User's choice:** Neutral when findings exist — user diverged from the recommended always-green default, preferring a visible signal when findings exist.

| Option | Description | Selected |
|--------|-------------|----------|
| fail ≥ threshold > neutral > success | One consistent ladder with or without blocking | ✓ |
| fail ≥ threshold, else success | Sub-threshold findings show green | |
| You decide | | |

**User's choice:** fail ≥ threshold > neutral > success (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror check + counts | Verdict matches check conclusion + severity counts + thresholds | ✓ |
| Counts only, no verdict word | Check is the only verdict surface | |
| You decide | | |

**User's choice:** Mirror check + counts (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Check Run via API | create_check_run; only way to express neutral | ✓ |
| Job exit code as the gate | Binary; conflates D-09 and findings-fail | |
| Both | Redundant gates can disagree | |

**User's choice:** Dedicated Check Run via API (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Skipped → success; fork → no check | Trivial PRs never wedge; fork absence is honest | ✓ |
| Both neutral | Yellow noise on lockfile bumps | |
| Skipped → neutral; fork → no check | Stricter; friction on safe PRs | |

**User's choice:** Skipped → success; fork → no check (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Compact verdict + counts, link to sticky | Check panel is a pointer; sticky is source of truth | ✓ |
| Full duplicate of sticky body | Two copies to sync | |
| Minimal — conclusion only | Checks tab says nothing | |

**User's choice:** Compact verdict + counts, link to sticky (recommended)

---

## Severity thresholds & config surface

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 3 levels | error/warning/info — locked Finding contract | ✓ |
| 4 levels (add critical) | Breaks locked contract; LLMs inflate | |
| You decide | | |

**User's choice:** Keep 3 levels (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| comment≥warning, fail unset | Info summary-only; blocking off by default | ✓ |
| comment≥info, fail unset | Everything inlines; bot-noise risk | |
| comment≥warning, fail≥error | Blocking day one; contradicts neutral default | |

**User's choice:** comment≥warning, fail unset (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| prevue.yml `review:` section | Extends Phase 2 config surface; trusted base ref | ✓ |
| Workflow inputs only | Nothing to attach to until Phase 5 | |
| Env vars | Unaudited side-channel | |

**User's choice:** prevue.yml `review:` section (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Summary overview + counts, no inline | Below-threshold findings visible in summary + verdict counts | ✓ |
| Fully suppressed | Silently discards findings | |
| Counts only | Tally without text | |

**User's choice:** Summary overview + counts, no inline (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — short fixed rubric in prompt | Anchors severity; gate-stable; ~50 tokens | ✓ |
| No — schema enum only | Engine-dependent severity scale | |
| Consumer-overridable rubric | New injection surface | |

**User's choice:** Yes — short fixed rubric in prompt (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed: red run with clear error | Raise at startup before engine spend | ✓ |
| Fall back to defaults + warn | Silent gate downgrade is dangerous | |
| You decide | | |

**User's choice:** Fail-closed: red run with clear error (recommended)

---

## Inline placement, fallback & comment budget

| Option | Description | Selected |
|--------|-------------|----------|
| Summary findings section | One fallback surface; matches roadmap wording | ✓ |
| File-level review comment | Second placement mechanism; easy to miss | |
| Nearest valid line | Wrong-line comments mislead | |

**User's choice:** Summary findings section (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| 10 | Tight but roomy enough; overflow to summary | ✓ |
| 20 | Flood perception territory | |
| 5 | May undercut review value | |

**User's choice:** 10 (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Severity rank, engine order within tier | Errors first; deterministic; overflow noted | ✓ |
| Severity then file-spread | Fairer spread; splits attention from worst file | |
| You decide | | |

**User's choice:** Severity rank, engine order within tier (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Always COMMENT | Check Run is the only gate | ✓ |
| REQUEST_CHANGES when fail threshold met | Second sticky gate; re-approve friction | |
| You decide | | |

**User's choice:** Always COMMENT (recommended)

**Notes:** At wrap-up the user added a freeform requirement: review comments must follow 4C (Clarity, Conciseness, Correctness, Completeness) and all comments must share the same structure via a template.

| Option | Description | Selected |
|--------|-------------|----------|
| Badge + title / body / suggestion block | Severity badge + bold title, 4C body, plain fenced suggestion, attribution footer | ✓ |
| Minimal: severity prefix + body | Loses scannable title | |
| You decide | | |

**User's choice:** Badge + title / body / suggestion block (recommended)

---

## Summary findings-overview layout

(Added by user at the "remaining gray areas" checkpoint.)

| Option | Description | Selected |
|--------|-------------|----------|
| Complete index of all findings | Inlined = one-line entry; non-inlined = full body; counts reconcile | ✓ |
| Only non-inlined findings | No single full picture | |
| You decide | | |

**User's choice:** Complete index of all findings (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Table grouped by severity | badge \| path:line \| title \| placement column | ✓ |
| Grouped lists per severity heading | Longer comment | |
| Flat list, file order | Buries severity | |

**User's choice:** Table grouped by severity (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsible details, collapsed | Full 4C bodies one click away | ✓ |
| Expanded bodies | Wall of text on busy PRs | |
| Table only, no bodies | Hides explanations | |

**User's choice:** Collapsible details, collapsed (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict → prose → table → details | Keeps D-04 shell; narrative first | ✓ |
| Verdict → table → prose | Gate data first | |
| You decide | | |

**User's choice:** Verdict → prose → table → details (recommended)

---

## Claude's Discretion

- Parser module location and JSON-extraction implementation
- Check Run name string; in_progress status at start
- Exact rubric/4C prompt wording and retry feedback message
- Emoji/badge choices and details-block formatting
- unidiff position-validation details (RIGHT/LEFT sides)
- Pipeline placement of threshold/budget evaluation in run_review()

## Deferred Ideas

- GitHub one-click suggestion blocks → v2 (CUST-02)
- Stale inline-comment auto-resolve on re-runs → v2 (LIFE-04)
- Comment dedupe across runs → v2 (LIFE-02)
- Workflow-input config pass-through → Phase 5 (WKFL-03)
- Token/cost transparency in summary → Phase 6 (OUTP-04)
