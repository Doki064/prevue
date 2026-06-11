# Phase 1: Walking Skeleton Review Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 1-Walking Skeleton Review Loop
**Areas discussed:** Engine output shape, Summary comment design, Review prompt composition, Failure visibility, E2E verification setup

---

## Engine output shape

| Option | Description | Selected |
|--------|-------------|----------|
| Freeform markdown | Prose review wrapped in minimal typed result; structured findings deferred to Phase 4 | ✓ |
| Structured JSON findings from day one | ENGN-01 shape immediately; riskier prompt work up front | |
| Hybrid | Prose summary + best-effort findings list, no validation | |

| Option | Description | Selected |
|--------|-------------|----------|
| Final interface now | Lock pydantic ReviewRequest → ReviewResult now; skeleton leaves findings empty | ✓ |
| Minimal interface | Prompt in → text out; evolve in Phase 4 | |

| Option | Description | Selected |
|--------|-------------|----------|
| CLI default model + COPILOT_MODEL passthrough | Zero config, escape hatch exists | ✓ |
| Pin a specific model | Reproducibility | |
| You decide during planning | | |

---

## Summary comment design

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | Header + engine review text + footer | |
| Sectioned shell | Fixed sections (Verdict / Review / Metadata) later phases fill in | ✓ |
| Rich layout | Collapsible details, emoji status, metadata table now | |

| Option | Description | Selected |
|--------|-------------|----------|
| No verdict yet | Review summary only; verdicts arrive with the Phase 4 merge gate | ✓ |
| Informal verdict line | Cosmetic only | |

| Option | Description | Selected |
|--------|-------------|----------|
| Replace in place entirely | One comment, always current | ✓ |
| Replace with collapsed history | Keep previous-runs section | |

---

## Review prompt composition

| Option | Description | Selected |
|--------|-------------|----------|
| Diff + changed-file list only | No PR title/body at all — cleanest injection posture | ✓ |
| Diff + file list + quoted PR title/body | More context, larger injection surface | |
| Raw diff only | Absolute minimum | |

| Option | Description | Selected |
|--------|-------------|----------|
| Diff hunks only | Simple, token-cheap skeleton | ✓ |
| Full changed-file contents from base ref | Deeper reviews, more tokens/API calls | |

| Option | Description | Selected |
|--------|-------------|----------|
| Claude drafts baseline review instructions | Skills replace most of it in Phase 3 | ✓ |
| User writes/approves baseline prompt | | |

---

## Failure visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Fail the workflow run, comment untouched | Honest signal, no PR-thread noise | ✓ |
| Error notice in sticky comment + non-zero exit | | |
| Silent skip | Failures go unnoticed | |

| Option | Description | Selected |
|--------|-------------|----------|
| ~5 minute timeout | Generous for one review call, bounds runner cost | ✓ |
| ~10 minute timeout | | |
| Decide during planning/spike | | |

---

## E2E verification setup

| Option | Description | Selected |
|--------|-------------|----------|
| Separate sandbox repo | Real consumer path | |
| Self-test in prevue repo | Fewer moving parts, less realistic | |
| Both | Wrapper workflow for iteration + sandbox repo for proof | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Copilot PAT ready | User has Copilot access, will create the secret | ✓ |
| Not yet — flag as prerequisite blocker | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Spike first | Tiny throwaway workflow running `copilot -p` on a clean runner before building | ✓ |
| Build adapter directly | Debug on the runner as needed | |

---

## Claude's Discretion

- Baseline review prompt preamble (generic high-quality review instructions)
- Sticky-comment marker mechanism, repo layout, CLI invocation details

## Deferred Ideas

Raised by the user as coverage questions; recorded in CONTEXT.md `<deferred>` and as requirement notes:

- LLM classification call context: diff hunks + PR summary/keywords as quoted data (→ Phase 5, CLSF-02)
- Logical review splitting with cross-reference-safe chunking (→ v2, CUST-04)
- Output-token reservation in shared token pool (→ Phase 6, DIFF-03 note)
- Committed-secret alerting in the security skill bundle (→ Phase 3, SKIL-02 note)
