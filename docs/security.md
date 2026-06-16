# Security Overview

Prevue treats PR diffs and paths as **untrusted data**. Consumer config and skills on the base ref are trusted.

## Prompt injection

Review and classify prompts fence untrusted content in `UNTRUSTED DATA` blocks and append an instruction-reassertion constant after each block. Engine output is schema-validated; findings on invalid diff lines fall back to the summary without changing the gate verdict.

## Base-ref-only skills

Skills under `.github/prevue/skills/` load from the base ref checkout only — never from the PR head. See [SECURITY.md](../SECURITY.md) for the full threat model.

## Workflow posture

- `pull_request` trigger (not `pull_request_target`)
- Fork PRs skipped in v1
- Minimal token scopes: `contents: write` (GraphQL thread resolve), `pull-requests: write`, `checks: write`

## Engine tools

Prevue adapters do not pass tool-enable flags to engine CLIs. Verify your chosen engine's default headless posture in your environment before enabling merge gates.
