---
name: CI / GitHub Actions Hardening
description: Review CI workflow changes for supply-chain and permission risks.
applies-to:
  - ".github/workflows/**"
  - "**/*.yml"
  - "**/*.yaml"
---
Review GitHub Actions workflows for supply-chain integrity, privilege escalation, and secret exposure risks:

- Action refs pinned to mutable tags (`actions/checkout@v4`, `@main`) instead of full commit SHA — enables tag-hijack supply-chain attack.
- `permissions:` absent or overly broad (`permissions: write-all`) — any step compromise gets repository write access.
- `pull_request_target` trigger combined with checkout of PR-head code (`ref: ${{ github.event.pull_request.head.sha }}`) — executes untrusted PR code with base-branch secrets.
- `secrets: inherit` passed to reusable workflows — leaks all caller secrets regardless of need.
- Untrusted `github.event.*` values (PR title, branch name, body) interpolated directly into `run:` shell scripts — command injection.
- Secrets echoed via `echo "${{ secrets.TOKEN }}"` or set in `ACTIONS_STEP_DEBUG` — credential exposure in logs.

For each: cite workflow file + step name. `pull_request_target` + PR-head checkout → **error**. Unpinned action refs on privileged jobs and `secrets: inherit` → **warning**.
