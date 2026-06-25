# Prevue

## What This Is

Prevue is a token-efficient AI PR review framework consumed as a GitHub reusable workflow. When a PR is submitted, it fetches the diff, classifies the change content (security, frontend, backend, data, infra, etc.), routes to the matching bundled skillsets, loads exactly those skills, runs the AI review with them, and posts results back to the PR as comments and a pass/fail check. It is for engineering teams who want high-quality AI code review without burning context windows and tokens on irrelevant guidelines.

## Core Value

Optimal memory context and token usage when integrating with AI — load only the review skills the PR actually needs — while keeping review quality on par with a full-context review.

## Pipeline

```
PR submit -> fetch diff -> classify -> route -> load -> review -> output
```

- **Fetch diff** — pull the PR diff and changed-file metadata via the GitHub API.
- **Classify (hybrid)** — deterministic pass first (file globs, paths, lockfiles, extensions); a cheap/fast LLM call only for ambiguous diffs. Clear-cut PRs spend zero or minimal tokens on classification.
- **Route** — map classification labels to skill bundles.
- **Load** — load exactly the matched skills into the review context, nothing else.
- **Review** — run the AI review through a pluggable engine adapter.
- **Output** — PR summary comment + inline line-level comments + pass/fail GitHub Check (mergeable gate).

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Consumable as a GitHub reusable workflow (`workflow_call`) from any repo
- [ ] Fetch PR diff and changed-file metadata on PR events
- [ ] Hybrid classifier: deterministic glob/path/pattern rules with small-LLM fallback for ambiguous diffs
- [ ] Router that maps classification labels to skill bundles
- [ ] Skill loader that loads only matched skills into the review context
- [ ] Built-in skill bundles: security, frontend, backend, data, infra
- [ ] Consumer repos can add custom skills and override built-in ones
- [ ] Pluggable engine adapter interface; first adapter: GitHub Copilot CLI (programmatic mode)
- [ ] Review output: PR summary comment, inline line-level comments, pass/fail GitHub Check

### Out of Scope

- Remote/central skill registry pulled at runtime — adds network/auth complexity; built-in + consumer-local skills cover v1
- Non-GitHub platforms (GitLab, Bitbucket) — framework is a GitHub reusable workflow by definition
- Auto-fix / auto-commit of review findings — review-only for v1; keeps permissions minimal and trust high
- IDE or local pre-push review mode — CI-first; local usage may come later

## Context

- v1 milestone complete (2026-06-24): all 9 phases shipped, 55 plans complete, 720 tests passing, live UAT 14/14 pass. Full framework implemented: walking skeleton → classification → skill loading → structured findings → multi-engine adapters → reusable workflow → customization/hardening → incremental lifecycle → classify-first + multi-call review.
- GitHub Copilot CLI supports headless use on Actions runners: `copilot -p "<prompt>" -s --no-ask-user --allow-tool=...`, auth via `COPILOT_GITHUB_TOKEN` (PAT of a user with Copilot access), model selection via `COPILOT_MODEL` or `--model`. Verified against GitHub docs (2026). Three additional adapters (Claude Code, Cursor, Gemini) implemented and validated (Phase 5).
- The token-efficiency thesis: most PR review token waste comes from loading every guideline/skill for every PR. Classification + selective skill loading bounds context size per review while specialist skills keep depth. Proven: classify-first pipeline (Phase 9) closes the routing→skill loading gap; multi-call mode handles oversized PRs without full-context waste.
- Skills follow a bundled-skillset model (similar to Agent Skills / SKILL.md conventions): each bundle is a directory of markdown skill files with metadata for routing. Consumer custom skills and overrides supported (Phase 7).

## Constraints

- **Tech stack**: Python for framework scripts — user's choice; invoked from the reusable workflow steps
- **Platform**: GitHub Actions reusable workflow (`workflow_call`) — the delivery mechanism is fixed
- **Engine**: Pluggable adapter layer from day one — no hard-coding a single AI vendor; Copilot CLI is first adapter, others follow
- **Permissions**: Workflow must run with minimal GitHub token scopes (read contents, write PR comments/checks) — consumers must be able to trust it
- **Cost**: Classification step must be near-zero token cost for unambiguous PRs — hybrid deterministic-first design

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pluggable engine adapter layer from day one | Avoid vendor lock-in; teams have different AI subscriptions | Validated — Copilot, Claude Code, Cursor, Gemini adapters all pass same contract tests (Phase 5) |
| GitHub Copilot CLI as first adapter | Runs headless in Actions (`copilot -p`); consumers likely already pay for Copilot | Validated — live E2E on Actions runner (Phase 1); UAT confirmed multi-call and gap-closure with Copilot (Phase 9) |
| Hybrid classification (deterministic first, LLM fallback) | Zero-token classification for clear-cut PRs; LLM only when globs are ambiguous | Validated — deterministic classifier (Phase 2); LLM fallback wired in Phase 6; classify-first ordering enforced in Phase 9 |
| Built-in skill bundles + consumer overrides | Useful out of the box, customizable per repo; no remote registry complexity | Validated — five built-in bundles (Phase 3); consumer override/custom merge (Phase 7); classify-first gap closure (Phase 9) |
| Output = summary + inline comments + pass/fail check | Summary for humans scanning, inline for actionability, check for merge gating | Validated — all three outputs live since Phase 4; sticky upsert, batched review API, check run confirmed |
| Python implementation | User preference; strong ecosystem for GitHub API and CLI tooling | Validated — entire framework implemented in Python; uv + pytest + ruff toolchain solid across all phases |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-24 — v1 milestone complete; context and key decisions updated to reflect shipped state*
