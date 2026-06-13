"""Skip policy — bot/label/title detection before engine spend (NOIS-01)."""

from __future__ import annotations

import re

from prevue.config import SkipConfig


def should_skip(pr, cfg: SkipConfig) -> str | None:
    """Return skip reason string, or None if review should proceed."""
    if getattr(pr.user, "type", None) == "Bot":
        login = pr.user.login
        if login not in cfg.review_bots:
            return f"bot author {login}"

    label_names = {label.name for label in pr.labels}
    for skip_label in cfg.skip_labels:
        if skip_label in label_names:
            return f"skip label {skip_label}"

    for pattern in cfg.skip_title_patterns:
        if re.search(pattern, pr.title):
            return f"title matched /{pattern}/"

    return None
