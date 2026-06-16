"""Direct unit tests for review_with_retry token accounting (WR: no double-count)."""

from __future__ import annotations

from prevue.engines.flow import review_with_retry
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
