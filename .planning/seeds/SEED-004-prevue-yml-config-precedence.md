---
id: SEED-004
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: before consumers depend on prevue.yml resolution order, or when adding a second config source
scope: small
---

# SEED-004: Declare prevue.yml config precedence hierarchy

## Why This Matters

`bobmatnyc/ai-code-review` uses an explicit precedence chain (CLI flags > project config > env >
defaults). Prevue should declare `prevue.yml` resolution order *before* consumers build
expectations on ambiguous behavior — config precedence is hard to change once depended on.

## When to Surface

**Trigger:** before consumers depend on resolution order, or when a second config source is added.

## Scope Estimate

**Small** — a documented, tested precedence chain in the config loader.

## Breadcrumbs

- Source: `bobmatnyc/ai-code-review` config precedence.
- Prevue: consumer-facing `prevue.yml` routing/rules config (PyYAML loader).

## Notes

Validation note, not a research spike. Cheap to lock in early.
