---
id: SEED-006
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: when expanding the bundled skillset catalog beyond the core security/frontend/backend/data/infra set
scope: medium
---

# SEED-006: Niche future skillsets (extract-patterns, evaluation, unused-code)

## Why This Matters

`bobmatnyc/ai-code-review` ships 16 named review types — validation that Prevue's classify→route→
specialized-skill shape is right. Three of their types are interesting catalog candidates beyond
Prevue's core bundles:
- **extract-patterns** — surface reusable patterns/conventions from the diff.
- **evaluation** — score the change against a rubric (hiring/quality gate flavor).
- **unused-code** — dead-code / unreachable detection.

## When to Surface

**Trigger:** when expanding the bundled skillset catalog beyond the core set.

## Scope Estimate

**Medium** — each is a SKILL.md bundle + routing rules; no framework change.

## Breadcrumbs

- Source: `bobmatnyc/ai-code-review` — 16 review types.
- Prevue: bundled skillsets routed by the classifier (security/frontend/backend/data/infra).

## Notes

Catalog expansion, not architecture. Pick based on consumer demand.
