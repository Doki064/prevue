---
name: API Contracts & Compatibility
description: Review API surface changes for backward compatibility and correctness.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/api/**"
  - "**/*controller*"
  - "**/routes/**"
---
- Breaking changes to request/response shape, status codes, or required fields are flagged (versioning or migration path needed).
- Input is validated at the boundary; responses don't over-expose internal fields.
- Pagination/limits on list endpoints; no unbounded result sets.
- Idempotency for retryable mutations where appropriate.
