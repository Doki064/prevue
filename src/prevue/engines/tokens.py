"""Hybrid token estimation — bytes/4 heuristic (OUTP-04, D-04, D-13).

This module is the LABELED FALLBACK used only when an engine cannot report real
usage data (i.e. ``capture_usage`` returns None).  Real per-engine token
counts are captured in ``prevue.engines.usage`` and set ``estimated=False``
on the token-meta dict.  The bytes/4 path sets ``estimated=True`` and is
clearly flagged as an approximation in all rendered output.

Do not use this as the primary accounting path for engines that DO report
usage (Claude Code via stdout-json, Copilot via OTEL JSONL).
"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count from UTF-8 byte length (bytes/4, labeled fallback).

    This is the labeled fallback used only when an engine cannot report real
    usage data.  ``estimated=True`` is set on the token-meta dict by the caller
    (``flow._token_meta``) when this function is used as the primary source.
    """
    return (len(text.encode("utf-8")) + 3) // 4
