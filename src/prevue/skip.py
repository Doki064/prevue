"""Skip policy — bot/label/title detection before engine spend (NOIS-01)."""

from __future__ import annotations

import re

from prevue.config import SkipConfig


def should_skip(pr, cfg: SkipConfig) -> str | None:
    """Return skip reason string, or None if review should proceed."""
    if getattr(pr.user, "type", None) == "Bot":
        # A missing login is treated as a skip-eligible unknown bot rather than
        # crashing or formatting "bot author None" (WR-05).
        login = getattr(pr.user, "login", None)
        if login not in cfg.review_bots:
            return f"bot author {login or 'unknown'}"

    label_names = {label.name for label in pr.labels}
    for skip_label in cfg.skip_labels:
        if skip_label in label_names:
            return f"skip label {skip_label}"

    # Coerce defensively: a None/empty title would make re.search raise TypeError
    # and abort the whole review before any check is published (WR-05).
    title = pr.title or ""
    for pattern in cfg.skip_title_patterns:
        if re.search(pattern, title):
            return f"title matched /{pattern}/"

    return None
