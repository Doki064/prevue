---
id: SEED-005
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: when a second engine adapter lands, or an engine needs a flag Prevue's typed inputs don't expose
scope: small
---

# SEED-005: Adapter raw-args passthrough escape hatch

## Why This Matters

`anthropics/claude-code-action` exposes `claude_args` — a raw passthrough for engine-specific flags
without redesigning the typed inputs. Prevue's adapter contract should have an equivalent so a new
engine's flags don't force a schema change. Validates the pluggable-adapter bet (their
Bedrock/Vertex/Foundry/direct-API support is the same pattern).

## When to Surface

**Trigger:** when a second engine adapter lands, or an engine needs a flag the typed inputs don't cover.

## Scope Estimate

**Small** — an optional `extra_args`/`engine_args` field on the adapter `ReviewRequest`.

## Breadcrumbs

- Source: `anthropics/claude-code-action` — `claude_args` passthrough; multi-provider auth.
- Prevue: adapter contract pydantic pair (`ReviewRequest` → `ReviewResult`); Copilot CLI first adapter.

## Notes

Keep it an explicit escape hatch, not the primary config surface.
