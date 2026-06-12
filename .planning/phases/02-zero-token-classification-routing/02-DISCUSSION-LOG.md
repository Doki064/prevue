# Phase 2: Zero-Token Classification & Routing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 2-zero-token-classification-routing
**Areas discussed:** Multi-label policy, Unmatched-file seam, Rules + routing config, Filters + audit trail, General-label scope, Empty-PR edge

---

## Multi-label policy

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-label union | All matched labels apply; downstream loads union of bundles | ✓ |
| Single dominant label | Pick one label; needs tie-break; risks under-review | |
| Multi-label, capped | Union capped at N; overflow noted | |

**User's choice:** Multi-label union
**Notes:** Honors "load only what's needed" without missing a real secondary domain.

---

## Unmatched-file seam

| Option | Description | Selected |
|--------|-------------|----------|
| 'general' fallback label | Unmatched → general bundle; Phase 5 upgrades later | ✓ |
| Mark ambiguous, reserve for Phase 5 | Record unclassified, no bundle yet | |
| Reviewed with all bundles | Load everything; burns budget | |

**User's choice:** 'general' fallback label
**Notes:** Deterministic, zero-token, never un-reviewed; named seam to Phase 5 LLM fallback.

---

## Rules + routing config

| Option | Description | Selected |
|--------|-------------|----------|
| Built-in data file + additive override | YAML defaults; consumer additive/override-by-label; 1:1 routing overridable | ✓ |
| Built-in only for v1 | Hardcode defaults; defer override | |
| Consumer full-replace | Consumer rules replace built-ins | |

**User's choice:** Built-in data file + additive override
**Notes:** Rules stay data (CLSF-03); routing overridable from the start (ROUT-01).

---

## Filters + audit trail

| Option | Description | Selected |
|--------|-------------|----------|
| Additive; drop from review entirely | Consumer globs add to built-ins; filtered dropped from classify AND engine diff; audit = labels + matched rule | ✓ |
| Additive; filter classify only | Filtered skip classify but still sent to engine | |
| Consumer globs replace defaults | Consumer ignore list replaces built-ins | |

**User's choice:** Additive; drop from review entirely
**Notes:** Don't spend review tokens on lockfiles; modifies DiffBundle before engine.

---

## General-label scope (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Only when NO file matched | Any real label → route to those only; general only for fully-unclassified PR | ✓ |
| Per unmatched file | Every unmatched file adds 'general' | |

**User's choice:** Only when NO file matched
**Notes:** Keeps mixed PRs clean; avoids tagging nearly every PR 'general'.

---

## Empty-PR edge (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Neutral skip, note in summary | No engine call; sticky note "no reviewable files (N filtered)" | ✓ |
| Route to 'general' anyway | General review of nothing meaningful | |
| Fail / error | Treat empty as failure | |

**User's choice:** Neutral skip, note in summary
**Notes:** Lockfile-only PR is valid; zero tokens; DIFF-02 disclosure.

---

## Claude's Discretion

- Classifier module layout, rule-data file path/schema, glob-matching impl
  (STACK.md: pathspec 1.1.1 `GitIgnoreSpec`, PyYAML 6.0.3).
- How classification result attaches to existing pydantic models.
- Default rule set contents (which globs → which of the 5 labels).

## Deferred Ideas

- LLM fallback classification (→ Phase 5, CLSF-02) — upgrade 'general'/ambiguous via cheap LLM.
- Skill bundle loading + 5 built-in SKILL.md bundles (→ Phase 3, SKIL-01/02/04).
- Inline comments / merge gate (→ Phase 4).
