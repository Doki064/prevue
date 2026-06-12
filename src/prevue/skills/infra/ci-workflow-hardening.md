---
name: CI / GitHub Actions Hardening
description: Review CI workflow changes for supply-chain and permission risks.
applies-to:
  - ".github/workflows/**"
  - "**/*.yml"
  - "**/*.yaml"
---
- Actions are pinned to a full commit SHA, not a mutable tag.
- `permissions:` is least-privilege (default read; write only where needed); no blanket `write-all`.
- No `pull_request_target` with checkout of PR head + secrets; untrusted input not interpolated into `run:` shells.
- Secrets passed explicitly, never `secrets: inherit` to reusable workflows; no secrets echoed to logs.
