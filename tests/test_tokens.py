"""RED scaffold — token estimator tests (OUTP-04). Target implemented in Plan 07-02."""

from __future__ import annotations


def test_estimate_tokens() -> None:
    from prevue.engines.tokens import estimate_tokens

    assert estimate_tokens("abcd") == 1  # 4 bytes / 4
    assert estimate_tokens("abcdefgh") == 2  # 8 bytes / 4, round up
