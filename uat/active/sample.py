"""UAT scenario 01 — backend-only PR (Phase 3 test 1, 4, 9).

Touch only this .py file so classification labels backend and skill loader
selects backend + security bundles, not frontend/data/infra.
"""


def uat_backend_only_marker() -> str:
    return "phase-03-uat-01"
