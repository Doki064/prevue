---
id: SEED-001
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: when token budget per review becomes the binding constraint, or when whole-file context (beyond the diff) is needed for review quality
scope: large
research_flag: true
---

# SEED-001: Semantic chunking for sub-file token reduction

> ⭐ **Great research idea — needs a spike before tasking.** Do not plan directly.

## Why This Matters

Biggest remaining token lever after classify→route→skill-load. Today Prevue selects context at
file granularity (pathspec globs) and ships changed hunks via unidiff. Semantic chunking would
parse files into function/class units (TreeSitter) and feed only the chunks relevant to a finding,
instead of whole files. `bobmatnyc/ai-code-review` claims **95%+ token reduction** this way
(196K → ~4K tokens) across 5 chunking strategies adapted per review type.

## When to Surface

**Trigger:** when token budget per review becomes the binding constraint, or when review quality
demands whole-file context beyond the diff.

## Scope Estimate

**Large** — and **costly**: TreeSitter needs per-language grammars (real complexity). Payoff is
strongest for *whole-file context fetch*, weaker for diff-only review where context is already
minimal. **Spike first** to measure actual token savings on Prevue's diff-centric flow before
committing — the 95% claim is for whole-codebase review, not necessarily diff review.

## Breadcrumbs

- Source: `bobmatnyc/ai-code-review` — "AI-Guided Semantic Chunking", TreeSitter-based.
- Prevue current context selection: unidiff hunk-level + pathspec glob classifier.

## Notes

Park as a researched future phase. Spike question: "What % token reduction does chunking give on
a diff-only review vs the current hunk+skill approach, and is it worth per-language grammar cost?"
