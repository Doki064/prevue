# Deferred Items — Phase 10 (boundary-contracts)

Items discovered during plan execution that are out of scope for the task that found them
(pre-existing, unrelated to the current plan's file changes) — logged per executor scope
boundary rules, not auto-fixed.

| Found during | Item | File | Status |
|---------------|------|------|--------|
| 10-10 (`bash scripts/ci-local.sh` verification) | `ruff check` E501: line too long (103 > 100 chars) | `tests/test_pricing.py:147` | Pre-existing — introduced in commit `fbabe40` (test(10): WR-01 add regression test for null pricing override fallback), not touched by 10-10's file set (`spec.py`, `cli_adapter.py`, `test_copilot_adapter.py`, `test_engine_contract.py`, `docs/configuration.md`). Out of scope per executor scope-boundary rule; left unfixed. |
