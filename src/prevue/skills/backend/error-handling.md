---
name: Error Handling & Resilience
description: Review error handling, logging, and failure modes in backend code.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/*.rb"
  - "**/*.java"
---
- Errors are handled or propagated deliberately — no bare `except:`/swallowed errors that hide failures.
- External calls (DB, HTTP, queue) have timeouts and handle failure; no unbounded retries without backoff.
- Logs include enough context to debug but never secrets/PII; correct log levels.
- Resources (files, connections, locks) released on all paths (context managers / `defer` / `finally`).
