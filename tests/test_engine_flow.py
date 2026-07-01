"""Direct unit tests for review_with_retry token accounting (WR: no double-count)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from prevue.engines.flow import _retry_token_meta, _token_meta, review_with_retry
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


def test_token_meta_estimates_cost_when_no_real_capture() -> None:
    """T-07 (10-THERMOS): cursor-cli/antigravity-cli have usage_capture="none" so
    capture_usage always returns None — cost_usd was never computed for them,
    while tokens still showed (inconsistent UX: tokens but no $ in the comment).
    A ~est cost must now be fed through compute_cost using the bytes/4 split."""
    fake_spec = SimpleNamespace(name="cursor-cli")
    override = {"some-model": {"input_cost_per_token": 1e-5, "output_cost_per_token": 2e-5}}

    meta = _token_meta(
        "prompt text",
        "stdout text",
        captured=None,
        spec=fake_spec,
        model_label="some-model",
        pricing_override=override,
    )

    assert meta["estimated"] is True
    assert meta["cost_usd"] == pytest.approx(
        estimate_tokens("prompt text") * 1e-5 + estimate_tokens("stdout text") * 2e-5
    )


def test_token_meta_no_cost_when_model_unknown_to_pricing() -> None:
    """Unknown model → compute_cost returns None → no cost_usd key added (same
    "unknown model, no cost" contract as the real-capture path)."""
    fake_spec = SimpleNamespace(name="cursor-cli")

    meta = _token_meta(
        "prompt text",
        "stdout text",
        captured=None,
        spec=fake_spec,
        model_label="totally-unknown-model-xyz",
        pricing_override=None,
    )

    assert meta["estimated"] is True
    assert "cost_usd" not in meta


def test_token_meta_no_cost_when_spec_or_model_missing() -> None:
    """No spec (e.g. classify-only path) or model_label="default" → no estimated
    cost attempted at all (can't price without knowing engine/model)."""
    meta_no_spec = _token_meta("p", "s", captured=None, spec=None, model_label="some-model")
    assert "cost_usd" not in meta_no_spec

    meta_default_model = _token_meta(
        "p", "s", captured=None, spec=SimpleNamespace(name="cursor-cli"), model_label="default"
    )
    assert "cost_usd" not in meta_default_model
