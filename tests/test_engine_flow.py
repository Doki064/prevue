"""Direct unit tests for review_with_retry token accounting (WR: no double-count)."""

from __future__ import annotations

import pytest

from prevue.engines.flow import _retry_token_meta, review_with_retry
from prevue.engines.prompt import _build_retry_prompt
from prevue.engines.tokens import estimate_tokens
from tests.engine_helpers import PROSE_REVIEW, VALID_FINDING, make_sample_request, stdout_with_fence


def _build_prompt(req, **kwargs) -> str:
    from prevue.engines.prompt import build_prompt

    return build_prompt(req, **kwargs)


def test_retry_review_tokens_count_each_invocation_once() -> None:
    """On a bad-fence-then-good retry, review tokens must equal the sum of both
    invocations' real inputs/outputs once each — never the original prompt twice."""
    req = make_sample_request()
    prompt = _build_prompt(req)
    retry_stdout = stdout_with_fence(payload=[VALID_FINDING])

    calls: list[str] = []

    def invoke(p: str) -> str:
        calls.append(p)
        return PROSE_REVIEW if len(calls) == 1 else retry_stdout

    result = review_with_retry(
        req,
        invoke=invoke,
        secret="tok",
        build_prompt=_build_prompt,
        max_prompt_bytes=10_000_000,
        model_label="fake",
    )

    assert len(calls) == 2
    assert result.engine_meta["retried"] is True

    # Accurate per-invocation accounting: each invocation's input and output counted
    # once. The retry prompt (calls[1]) embeds the full original prompt and is counted
    # on its own — _retry_token_meta never concatenates it onto `prompt`.
    expected = (
        estimate_tokens(prompt)
        + estimate_tokens(PROSE_REVIEW)
        + estimate_tokens(calls[1])  # actual retry prompt sent
        + estimate_tokens(retry_stdout)
    )
    tokens = result.engine_meta["tokens"]
    assert tokens["review"] == expected
    # Sanity: the retry prompt embeds the original, so per-invocation summing equals
    # the engine's true input (original sent standalone + re-sent inside the retry).
    assert _build_retry_prompt(prompt, "x").startswith(prompt)


def test_retry_token_meta_sums_both_real_captures() -> None:
    """T-04 (10-THERMOS): when both the original and retry invocations return real
    captures, their input/output/cache/cost must be summed, not one discarded.

    Regression for `best_capture = captured_retry or captured`, which silently
    dropped the first invocation's real tokens whenever both calls succeeded.
    """
    captured = {
        "input": 1000,
        "output": 200,
        "cache_read": 50,
        "cost_usd": 0.01,
        "estimated": False,
    }
    captured_retry = {
        "input": 300,
        "output": 80,
        "cache_read": 10,
        "cost_usd": 0.004,
        "estimated": False,
    }

    meta = _retry_token_meta("p", "rp", "out1", "out2", captured, captured_retry)

    assert meta["estimated"] is False
    assert meta["input"] == 1300
    assert meta["output"] == 280
    assert meta["cache_read"] == 60
    assert meta["cost_usd"] == pytest.approx(0.014)


def test_retry_token_meta_uses_single_capture_when_only_one_present() -> None:
    """If only one invocation has a real capture (the other returned None), the
    single capture's values pass through unsummed (no phantom zero-padding bugs)."""
    captured = {"input": 1000, "output": 200, "estimated": False}

    meta = _retry_token_meta("p", "rp", "out1", "out2", captured, None)

    assert meta["estimated"] is False
    assert meta["input"] == 1000
    assert meta["output"] == 200
