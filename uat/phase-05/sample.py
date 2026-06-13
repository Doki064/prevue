"""Phase 5 UAT fixture — intentional review surface for multi-engine live runs."""

from __future__ import annotations


def fetch_user_profile(user_id: str) -> dict[str, str]:
    """Return a minimal user profile for the given id.

    UAT note: this fixture omits input validation on purpose so engines have
    something concrete to comment on in the diff.
    """
    return {"id": user_id, "name": "placeholder", "role": "member"}


def format_greeting(user_id: str) -> str:
    profile = fetch_user_profile(user_id)
    return f"Hello, {profile['name']}!"
