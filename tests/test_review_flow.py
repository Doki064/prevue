"""End-to-end review orchestration — happy path and D-09 fail-closed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prevue.engines.copilot_cli import EngineFailure
from prevue.github.client import PrContext
from prevue.models import ChangedFile, DiffBundle, ReviewRequest, ReviewResult
from prevue.review import BASELINE_INSTRUCTIONS, run_review

REPO_FULL = "owner/prevue"
PR_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"


def _sample_ctx() -> PrContext:
    return PrContext(
        repo_full=REPO_FULL,
        pr_number=PR_NUMBER,
        head_repo_full=REPO_FULL,
        base_repo_full=REPO_FULL,
    )


def _sample_diff() -> DiffBundle:
    return DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="src/example.py",
                status="modified",
                additions=3,
                deletions=1,
                patch="@@ -1 +1 @@\n-old\n+new",
            )
        ],
    )


class FailingEngine:
    name = "failing"

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise EngineFailure("engine exploded")


def test_run_review_happy_path_calls_upsert_once(fake_engine) -> None:
    mock_pr = MagicMock()
    sample_diff = _sample_diff()
    captured: dict[str, ReviewRequest] = {}

    original_review = fake_engine.review

    def capture_review(req: ReviewRequest) -> ReviewResult:
        captured["req"] = req
        return original_review(req)

    fake_engine.review = capture_review  # type: ignore[method-assign]

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=sample_diff) as mock_fetch,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr) as mock_get_pr,
        patch("prevue.review.upsert_sticky") as mock_upsert,
    ):
        run_review(adapter=fake_engine)

    mock_fetch.assert_called_once()
    mock_get_pr.assert_called_once_with(_sample_ctx())
    mock_upsert.assert_called_once()
    assert mock_upsert.call_args[0][0] is mock_pr
    result = mock_upsert.call_args[0][1]
    assert result.summary_markdown == "## Canned review\n\nNo issues found."

    classification = mock_upsert.call_args.kwargs.get("classification")
    assert classification is not None
    assert classification.labels == {"backend": "**/*.py"}

    req = captured["req"]
    assert [f.path for f in req.diff.files] == [f.path for f in sample_diff.files]
    assert req.instructions == BASELINE_INSTRUCTIONS
    assert req.budget_seconds == 300


def test_run_review_filtered_diff_and_classification_metadata() -> None:
    """D-08: lockfile filtered from engine diff and never classified."""
    mock_pr = MagicMock()
    mixed_diff = DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="src/App.tsx",
                status="modified",
                additions=1,
                deletions=0,
                patch="@@",
            ),
            ChangedFile(
                path="pkg/uv.lock",
                status="modified",
                additions=10,
                deletions=0,
                patch="@@",
            ),
        ],
    )
    captured: dict[str, ReviewRequest] = {}

    class CaptureEngine:
        name = "capture"

        def review(self, req: ReviewRequest) -> ReviewResult:
            captured["req"] = req
            return ReviewResult(
                summary_markdown="ok",
                findings=[],
                engine_meta={"model": "fake", "duration_s": 0.1},
            )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=mixed_diff),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.upsert_sticky") as mock_upsert,
    ):
        run_review(adapter=CaptureEngine())

    req = captured["req"]
    assert [f.path for f in req.diff.files] == ["src/App.tsx"]
    classification = mock_upsert.call_args.kwargs["classification"]
    assert classification.labels == {"frontend": "**/*.tsx"}
    assert "uv.lock" not in str(classification.labels)
    assert "lock" not in classification.labels


def test_engine_failure_propagates_without_upsert() -> None:
    mock_pr = MagicMock()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.upsert_sticky") as mock_upsert,
    ):
        with pytest.raises(EngineFailure, match="engine exploded"):
            run_review(adapter=FailingEngine())

    mock_upsert.assert_not_called()
