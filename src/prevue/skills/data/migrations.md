---
name: Database Migrations
description: Review schema migrations for safety and reversibility.
applies-to:
  - "**/migrations/**"
  - "**/*.sql"
  - "**/schema.prisma"
---
- Migration is reversible (or the irreversibility is intentional + noted); a down/rollback exists where the tool supports it.
- No long table locks on large tables (avoid blocking `ALTER`; prefer additive + backfill + switch).
- New non-null columns have defaults or a backfill step; no data loss on column drop/rename without a deprecation window.
- Index changes considered for query impact; created concurrently where supported.
