"""RED contract tests for GitHub check-run posting (OUTP-03, D-08/D-09/D-10)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from prevue.gate import GateResult, ReviewConfig
from prevue.github.checks import CHECK_NAME, conclude_review_check, conclude_skip_check


def _gate(*, conclusion: str = "success") -> GateResult:
    return GateResult(
        conclusion=conclusion,  # type: ignore[arg-type]
        severity_counts={"error": 0, "warning": 0, "info": 0},
        placed=[],
        inline=[],
        config=ReviewConfig(),
        degraded=False,
    )


class TestConcludeReviewCheck:
    def test_create_check_run_payload(self) -> None:
        repo = MagicMock()
        gate = _gate(conclusion="neutral")
        gate.severity_counts = {"error": 1, "warning": 0, "info": 0}
        head_sha = "abc123def456"

        conclude_review_check(repo, head_sha, gate)

        repo.create_check_run.assert_called_once()
        kwargs = repo.create_check_run.call_args.kwargs
        assert kwargs["name"] == CHECK_NAME == "prevue/review"
        assert kwargs["head_sha"] == head_sha
        assert kwargs["status"] == "completed"
        assert kwargs["conclusion"] == "neutral"
        output = kwargs["output"]
        assert "title" in output
        assert "summary" in output
        assert "Findings" in output["title"] or "⚠️" in output["title"]
        assert "Thresholds:" in output["summary"]

    @pytest.mark.parametrize("conclusion", ["success", "neutral", "failure"])
    def test_conclusion_passthrough(self, conclusion: str) -> None:
        repo = MagicMock()
        gate = _gate(conclusion=conclusion)
        conclude_review_check(repo, "sha123", gate)
        assert repo.create_check_run.call_args.kwargs["conclusion"] == conclusion

    def test_sticky_url_in_summary(self) -> None:
        repo = MagicMock()
        gate = _gate(conclusion="neutral")
        url = "https://github.com/o/r/pull/1#issuecomment-99"
        conclude_review_check(repo, "sha123", gate, sticky_url=url)
        summary = repo.create_check_run.call_args.kwargs["output"]["summary"]
        assert url in summary
        assert f"]({url})" in summary


class TestConcludeSkipCheck:
    def test_skip_posts_success_with_no_reviewable_files(self) -> None:
        repo = MagicMock()
        conclude_skip_check(repo, "sha456", dropped_count=3)
        kwargs = repo.create_check_run.call_args.kwargs
        assert kwargs["name"] == CHECK_NAME
        assert kwargs["conclusion"] == "success"
        assert kwargs["status"] == "completed"
        title = kwargs["output"]["title"].lower()
        assert "no reviewable files" in title
