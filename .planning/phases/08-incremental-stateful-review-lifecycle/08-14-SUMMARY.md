---
phase: 08-incremental-stateful-review-lifecycle
plan: 14
subsystem: api
tags: [github, issue_comment, parser, authorization, pydantic]

requires:
  - phase: 08-incremental-stateful-review-lifecycle
    provides: Phase 08 incremental review foundation (08-13 dismiss store)
provides:
  - parse_command pure /prevue grammar parser (review/dismiss/resolve)
  - load_comment_context issue_comment event loader via get_pull
  - authorize_commenter write-access gate via collaborator permission API
affects: [08-15, 08-16]

tech-stack:
  added: []
  patterns:
    - "Pure Python command parsing — no shell/eval on untrusted comment bodies"
    - "Sibling event loader for issue_comment (load_pr_context untouched)"
    - "Authoritative authorization via get_collaborator_permission not author_association"

key-files:
  created:
    - src/prevue/commands.py
    - tests/test_commands.py
    - tests/test_client.py
    - tests/fixtures/issue_comment_event.json
  modified:
    - src/prevue/github/client.py

key-decisions:
  - "parse_command honors only first /prevue line outside fenced code blocks"
  - "id tokens accept fingerprint [0-9a-f]{16} OR thread_id [A-Za-z0-9_=-]{8,}"
  - "authorize_commenter uses permission API {write,admin} — author_association advisory only"
  - "load_comment_context cross-checks PREVUE_ISSUE_NUMBER against event issue number"

patterns-established:
  - "CommentContext sibling loader resolves PR SHAs via repo.get_pull (§L1)"
  - "Dismiss reason captured verbatim, bounded to 500 chars"

requirements-completed: [LIFE-03]

duration: 15min
completed: 2026-06-16
---

# Phase 08 Plan 14: /prevue Parser + Comment Context Summary

**Injection-safe /prevue command parser, issue_comment context loader via get_pull, and collaborator-permission write gate**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-16T00:00:00Z
- **Completed:** 2026-06-16T00:15:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `parse_command` pure grammar: review/dismiss/resolve with fingerprint/thread-id validation
- `load_comment_context` reads issue_comment payload (no `pull_request` KeyError) + get_pull SHAs
- `authorize_commenter` gates on `get_collaborator_permission ∈ {write, admin}`
- 31 new unit tests; full suite 557 passed

## Task Commits

1. **Task 1+2: parse_command + load_comment_context + authorize_commenter** - `9e8172b` (feat)

## Files Created/Modified

- `src/prevue/commands.py` - Command dataclass, parse_command, authorize_commenter
- `src/prevue/github/client.py` - CommentContext, load_comment_context (load_pr_context unchanged)
- `tests/test_commands.py` - parse + authorize tests including injection battery
- `tests/test_client.py` - comment_context loader tests + load_pr_context regression
- `tests/fixtures/issue_comment_event.json` - issue_comment event fixture (no top-level pull_request)

## Decisions Made

- Cross-check PREVUE_ISSUE_NUMBER against event issue.number (ValueError on mismatch)
- Code-fence tracking skips /prevue lines inside ``` blocks
- Uppercase hex accepted as thread_id charset (not fingerprint) — per dual-regex grammar

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 08-15 can wire `run_command`: load_comment_context → authorize_commenter → fork guard → parse_command → dispatch
- Fork guard inputs (head_repo_full vs base_repo_full) exposed on CommentContext

## Self-Check: PASSED

- FOUND: src/prevue/commands.py
- FOUND: src/prevue/github/client.py
- FOUND: tests/test_commands.py
- FOUND: tests/test_client.py
- FOUND: tests/fixtures/issue_comment_event.json
- FOUND: 9e8172b

---
*Phase: 08-incremental-stateful-review-lifecycle*
*Completed: 2026-06-16*
