"""Route classified labels to skill bundle ids (ROUT-01, D-06)."""

from __future__ import annotations

from prevue.classify.models import CANONICAL_LABEL_ORDER


def _canonical_index(label: str) -> int:
    try:
        return CANONICAL_LABEL_ORDER.index(label)
    except ValueError:
        return len(CANONICAL_LABEL_ORDER)


def route(labels: list[str], routing_map: dict[str, str]) -> list[str]:
    """Map each label to a bundle id; preserve canonical label order."""
    ordered = sorted(labels, key=_canonical_index)
    bundles: list[str] = []
    seen: set[str] = set()
    for label in ordered:
        bundle = routing_map.get(label, label)
        if bundle in seen:
            continue
        seen.add(bundle)
        bundles.append(bundle)
    return bundles
