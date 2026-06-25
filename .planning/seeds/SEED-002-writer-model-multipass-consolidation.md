---
id: SEED-002
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: when multi-call review (Phase 9) needs cost tiering, or when per-chunk/per-skill passes are added
scope: medium
research_flag: true
---

# SEED-002: Writer-model multi-pass consolidation (model tiering)

> ⭐ **Great research idea — needs a spike before tasking.**

## Why This Matters

Formalize model tiering as an adapter capability: a cheap model does N passes (per chunk / per
skill), a separate cheap model consolidates findings into the final review. Maps directly onto
Phase 9's multi-call review and the CLAUDE.md classification-fallback note (cheap classify →
strong review → cheap dedup). Cuts cost without losing coverage.

## When to Surface

**Trigger:** when multi-call review needs cost tiering, or per-chunk/per-skill passes are added.

## Scope Estimate

**Medium** — adapter contract change: `ReviewRequest`/`ReviewResult` gain a model-role notion
(classifier/reviewer/consolidator). Pairs naturally with SEED-001 chunking.

## Breadcrumbs

- Source: `bobmatnyc/ai-code-review` — separate "writer models" for cost-optimized consolidation.
- Prevue: Phase 9 multi-call split/execute/merge (09-05-PLAN); existing fingerprint dedup.
- CLAUDE.md: fallback classifier routed through the same adapter with `--model`.

## Notes

Spike: does a cheap consolidator model preserve finding quality vs the strong reviewer doing its
own merge? Measure against existing fingerprint dedup.
