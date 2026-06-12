---
name: SQL Safety
description: Review raw SQL and queries for injection and performance footguns.
applies-to:
  - "**/*.sql"
  - "**/*repository*"
  - "**/*queries*"
---
- No string-built SQL with untrusted input — parameterize.
- Queries have bounded result sets and use indexes for filter/join columns; flag obvious N+1 patterns.
- Transactions wrap multi-statement invariants; isolation level appropriate.
- Destructive statements (`DELETE`/`UPDATE` without `WHERE`, `TRUNCATE`, `DROP`) are intentional and guarded.
