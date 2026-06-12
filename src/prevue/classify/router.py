"""Route classified labels to skill bundle ids (ROUT-01, D-06)."""

from __future__ import annotations


def route(labels: list[str], routing_map: dict[str, str]) -> list[str]:
    """Map each label to a bundle id; consumer override wins, else 1:1 by name."""
    return [routing_map.get(label, label) for label in labels]
