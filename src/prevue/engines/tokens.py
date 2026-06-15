"""Hybrid token estimation — bytes/4 heuristic (OUTP-04, D-13)."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count from UTF-8 byte length (bytes/4, ~est)."""
    return (len(text.encode("utf-8")) + 3) // 4
