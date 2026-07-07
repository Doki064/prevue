"""Direct unit tests for review_with_retry token accounting (WR: no double-count)."""

from __future__ import annotations

import json
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


def test_retry_token_meta_both_required_flags_partial_capture_as_estimated() -> None:
    """For non-cumulative (per-invocation) real captures, a missing side means the
    retry's own real usage is unaccounted for — the merged total must be labeled
    estimated=True rather than silently under-reporting spend as a real total."""
    captured = {"input": 1000, "output": 200, "estimated": False}

    partial = _retry_token_meta("p", "rp", "out1", "out2", captured, None, both_required=True)
    assert partial["estimated"] is True
    assert partial["input"] == 1000  # values still pass through unpadded

    captured_retry = {"input": 300, "output": 80, "estimated": False}
    full = _retry_token_meta(
        "p", "rp", "out1", "out2", captured, captured_retry, both_required=True
    )
    assert full["estimated"] is False
    assert full["input"] == 1300


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


def test_merge_retry_tokens_otel_no_growth_falls_back_to_estimate_for_retry(tmp_path) -> None:
    """WR-02: a retry that crosses argv_prompt_max_bytes and falls back to stdin
    produces no new OTEL span. Trusting retry.captured as "first+retry combined"
    in that case silently reports ONLY the first invocation's usage, dropping the
    retry's real, billed tokens entirely — this must fall back to an estimate for
    the retry's own contribution instead, with estimated=True."""
    otel_dir = tmp_path / "copilot-otel"
    otel_dir.mkdir()
    spec = SimpleNamespace(name="copilot-cli", usage_capture="otel-jsonl", stdout_format="plain")

    span = {
        "type": "span",
        "attributes": {"gen_ai.usage.input_tokens": 1000, "gen_ai.usage.output_tokens": 200},
    }
    (otel_dir / "spans.jsonl").write_text(json.dumps(span) + "\n")

    req = make_sample_request()
    retry_stdout = stdout_with_fence(payload=[VALID_FINDING])
    calls: list[str] = []

    def invoke(p: str) -> str:
        calls.append(p)
        # Neither call writes a NEW span here — simulates the retry falling
        # back to stdin delivery (no -p, no OTEL emission) while the first
        # invocation's span is already on disk from before this call.
        return PROSE_REVIEW if len(calls) == 1 else retry_stdout

    result = review_with_retry(
        req,
        invoke=invoke,
        secret="tok",
        build_prompt=_build_prompt,
        max_prompt_bytes=10_000_000,
        model_label="default",
        spec=spec,
        otel_path=str(otel_dir),
    )

    assert len(calls) == 2
    tokens = result.engine_meta["tokens"]
    assert tokens["estimated"] is True
    # First invocation's real 1000/200 tokens are preserved, plus a bytes/4
    # estimate on top for the retry's own (real, billed) contribution — never
    # just the first invocation's numbers reported as if they were the total.
    assert tokens["input"] > 1000
    assert tokens["output"] > 200


def test_merge_retry_tokens_otel_growth_still_sums_normally(tmp_path) -> None:
    """Sanity check: when the retry's OTEL read actually grew (a real second span
    was written), the existing "trust retry.captured as the combined total"
    behavior is unchanged — estimated stays False and totals reflect both spans."""
    otel_dir = tmp_path / "copilot-otel"
    otel_dir.mkdir()
    spec = SimpleNamespace(name="copilot-cli", usage_capture="otel-jsonl", stdout_format="plain")
    spans_file = otel_dir / "spans.jsonl"

    span1 = {
        "type": "span",
        "attributes": {"gen_ai.usage.input_tokens": 1000, "gen_ai.usage.output_tokens": 200},
    }
    spans_file.write_text(json.dumps(span1) + "\n")

    req = make_sample_request()
    retry_stdout = stdout_with_fence(payload=[VALID_FINDING])
    calls: list[str] = []

    def invoke(p: str) -> str:
        calls.append(p)
        if len(calls) == 1:
            return PROSE_REVIEW
        # Retry invocation also reaches the OTEL-emitting path: a second span
        # is appended, so the directory read genuinely grows.
        span2 = {
            "type": "span",
            "attributes": {"gen_ai.usage.input_tokens": 300, "gen_ai.usage.output_tokens": 80},
        }
        spans_file.write_text(spans_file.read_text() + json.dumps(span2) + "\n")
        return retry_stdout

    result = review_with_retry(
        req,
        invoke=invoke,
        secret="tok",
        build_prompt=_build_prompt,
        max_prompt_bytes=10_000_000,
        model_label="default",
        spec=spec,
        otel_path=str(otel_dir),
    )

    tokens = result.engine_meta["tokens"]
    assert tokens["estimated"] is False
    assert tokens["input"] == 1300
    assert tokens["output"] == 280


def test_token_meta_no_cost_when_spec_or_model_missing() -> None:
    """No spec (e.g. classify-only path) or model_label="default" → no estimated
    cost attempted at all (can't price without knowing engine/model)."""
    meta_no_spec = _token_meta("p", "s", captured=None, spec=None, model_label="some-model")
    assert "cost_usd" not in meta_no_spec

    meta_default_model = _token_meta(
        "p", "s", captured=None, spec=SimpleNamespace(name="cursor-cli"), model_label="default"
    )
    assert "cost_usd" not in meta_default_model
