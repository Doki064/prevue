"""End-to-end review orchestration — happy path and D-09 fail-closed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from prevue.engines.copilot_cli import EngineFailure
from prevue.github.client import PrContext
from prevue.models import ChangedFile, DiffBundle, Finding, ReviewRequest, ReviewResult
from prevue.review import BASELINE_INSTRUCTIONS, ForkPrUnsupported, run_review

REPO_FULL = "owner/prevue"
PR_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"
STICKY_URL = "https://github.com/o/r/pull/1#issuecomment-99"


def _sample_ctx() -> PrContext:
    return PrContext(
        repo_full=REPO_FULL,
        pr_number=PR_NUMBER,
        head_repo_full=REPO_FULL,
        base_repo_full=REPO_FULL,
    )


def _fork_ctx() -> PrContext:
    return PrContext(
        repo_full=REPO_FULL,
        pr_number=PR_NUMBER,
        head_repo_full="forker/prevue",
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


def _mock_repo() -> MagicMock:
    return MagicMock()


def _mock_sticky(*, html_url: str = STICKY_URL) -> MagicMock:
    sticky = MagicMock()
    sticky.html_url = html_url
    return sticky


class FailingEngine:
    name = "failing"

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise EngineFailure("engine exploded")


class FindingsEngine:
    name = "findings"

    def review(self, req: ReviewRequest) -> ReviewResult:
        return ReviewResult(
            summary_markdown="Found issues.",
            findings=[
                Finding(
                    path="src/example.py",
                    line=1,
                    side="RIGHT",
                    severity="warning",
                    title="Unused import",
                    body="Remove the unused import.",
                )
            ],
            engine_meta={"model": "fake", "duration_s": 0.1},
        )


class DegradedEngine:
    name = "degraded"

    def review(self, req: ReviewRequest) -> ReviewResult:
        return ReviewResult(
            summary_markdown="Could not parse structured output.",
            findings=[],
            degraded=True,
            engine_meta={"model": "fake", "duration_s": 0.1},
        )


def test_run_review_happy_path_calls_upsert_once(fake_engine) -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
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
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review") as mock_inline,
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=fake_engine)

    mock_fetch.assert_called_once()
    mock_get_pr.assert_called_once_with(_sample_ctx())
    mock_inline.assert_called_once()
    mock_upsert.assert_called_once()
    mock_check.assert_called_once()
    assert mock_upsert.call_args[0][0] is mock_pr
    result = mock_upsert.call_args[0][1]
    assert result.summary_markdown == "## Canned review\n\nNo issues found."

    gate = mock_upsert.call_args.kwargs["gate"]
    assert gate is not None
    assert gate.conclusion == "success"
    check_gate = mock_check.call_args[0][2]
    assert check_gate is gate
    assert mock_check.call_args.kwargs["sticky_url"] == STICKY_URL
    assert mock_check.call_args[0][1] == HEAD_SHA

    classification = mock_upsert.call_args.kwargs.get("classification")
    assert classification is not None
    assert classification.labels == {"backend": "**/*.py"}

    req = captured["req"]
    assert [f.path for f in req.diff.files] == [f.path for f in sample_diff.files]
    assert req.instructions.startswith(BASELINE_INSTRUCTIONS)
    assert "## Skill:" in req.instructions
    assert req.budget_seconds == 300

    loaded = mock_upsert.call_args.kwargs.get("loaded_skills")
    assert loaded
    assert any("(security)" in entry or "(backend)" in entry for entry in loaded)


def test_run_review_with_findings_posts_inline_then_sticky_then_check() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    call_order: list[str] = []

    def track_inline(*_args, **_kwargs) -> bool:
        call_order.append("inline")
        return True

    def track_sticky(*_args, **_kwargs) -> MagicMock:
        call_order.append("sticky")
        return mock_sticky

    def track_check(*_args, **_kwargs) -> None:
        call_order.append("check")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", side_effect=track_inline) as mock_inline,
        patch("prevue.review.upsert_sticky", side_effect=track_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", side_effect=track_check) as mock_check,
    ):
        run_review(adapter=FindingsEngine())

    mock_inline.assert_called_once()
    mock_upsert.assert_called_once()
    mock_check.assert_called_once()
    gate = mock_upsert.call_args.kwargs["gate"]
    assert gate.conclusion == "neutral"
    assert len(gate.inline) == 1
    assert mock_check.call_args[0][2] is gate
    assert call_order == ["inline", "sticky", "check"]


def test_run_review_degraded_neutral_check_no_inline() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review") as mock_inline,
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=DegradedEngine())

    gate = mock_upsert.call_args.kwargs["gate"]
    assert gate.degraded is True
    assert gate.conclusion == "neutral"
    assert gate.inline == []
    mock_inline.assert_called_once_with(mock_pr, gate)
    assert mock_check.call_args[0][2].conclusion == "neutral"


def test_run_review_filtered_diff_and_classification_metadata() -> None:
    """D-08: lockfile filtered from engine diff and never classified."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
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
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review"),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check"),
    ):
        run_review(adapter=CaptureEngine())

    req = captured["req"]
    assert [f.path for f in req.diff.files] == ["src/App.tsx"]
    classification = mock_upsert.call_args.kwargs["classification"]
    assert classification.labels == {"frontend": "**/*.tsx"}
    assert "uv.lock" not in str(classification.labels)
    assert "lock" not in classification.labels
    assert classification.dropped_count == 1


def test_run_review_empty_skip_no_engine_call() -> None:
    """D-10: all-filtered PR skips engine; posts skip note and success check."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    lockfile_only = DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="pkg/uv.lock",
                status="modified",
                additions=10,
                deletions=0,
                patch="@@",
            ),
        ],
    )

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called on all-filtered PR")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=lockfile_only),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.upsert_skip_note") as mock_skip,
        patch("prevue.review.conclude_skip_check") as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=SpyEngine())

    mock_skip.assert_called_once_with(mock_pr, dropped_count=1)
    mock_skip_check.assert_called_once_with(mock_repo, HEAD_SHA, dropped_count=1)
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


def test_fork_pr_creates_no_check() -> None:
    with (
        patch("prevue.review.load_pr_context", return_value=_fork_ctx()),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.conclude_review_check") as mock_check,
        patch("prevue.review.conclude_skip_check") as mock_skip_check,
    ):
        with pytest.raises(ForkPrUnsupported):
            run_review()

    mock_fetch.assert_not_called()
    mock_check.assert_not_called()
    mock_skip_check.assert_not_called()


def test_invalid_review_config_raises_before_fetch() -> None:
    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch(
            "prevue.review.load_review_config",
            side_effect=ValidationError.from_exception_data("ReviewConfig", []),
        ),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.CopilotCliAdapter") as mock_adapter_cls,
    ):
        with pytest.raises(ValidationError):
            run_review()

    mock_fetch.assert_not_called()
    mock_adapter_cls.assert_not_called()


def test_engine_failure_propagates_without_upsert() -> None:
    mock_pr = MagicMock()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.post_inline_review") as mock_inline,
        patch("prevue.review.upsert_sticky") as mock_upsert,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        with pytest.raises(EngineFailure, match="engine exploded"):
            run_review(adapter=FailingEngine())

    mock_inline.assert_not_called()
    mock_upsert.assert_not_called()
    mock_check.assert_not_called()
