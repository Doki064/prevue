---
id: SEED-003
status: dormant
planted: 2026-06-25
planted_during: post-Phase-9 (research capture)
trigger_when: when review latency is user-visible and a single end-of-run comment feels slow
scope: small
research_flag: true
---

# SEED-003: track_progress live-checkbox comment

> ⭐ **Great research idea — needs a spike before tasking.**

## Why This Matters

UX win for slow reviews. Post a "reviewing…" comment up front, update checkboxes as work
proceeds, finalize as "Completed". Prevue currently posts once at the end via PyGithub
`create_review`. Low effort: one comment create + a few edits.

## When to Surface

**Trigger:** when review latency is user-visible and the single end-of-run comment feels slow.

## Scope Estimate

**Small** — one create + N edits on a PR comment. Watch GitHub API write-rate/secondary limits;
keep edits coarse (per-phase, not per-finding).

## Breadcrumbs

- Source: `anthropics/claude-code-action` — `track_progress: true` checkbox comment lifecycle.
- Prevue: single `create_review(comments=[...])` post path.

## Notes

Spike: verify edit cadence stays under secondary rate limits on large PRs.
