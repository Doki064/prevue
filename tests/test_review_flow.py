"""End-to-end review orchestration — happy path and D-09 fail-closed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from prevue.config import NO_CONSUMER_CONFIG_SENTINEL, SkillsConfig, load_config
from prevue.engines.errors import EngineFailure
from prevue.engines.registry import UnknownEngineError
from prevue.fingerprint import fingerprint
from prevue.github.client import PrContext
from prevue.models import ChangedFile, DiffBundle, Finding, ReviewRequest, ReviewResult
from prevue.review import BASELINE_INSTRUCTIONS, ForkPrUnsupported, _open_set_findings, run_review

REPO_FULL = "owner/prevue"
PR_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"
STICKY_URL = "https://github.com/o/r/pull/1#issuecomment-99"


@pytest.fixture(autouse=True)
def _hermetic_review_config():
    """Framework defaults — ignore repo .github/prevue.yml in unit tests."""

    def _load_config(_path=None):
        return load_config(str(NO_CONSUMER_CONFIG_SENTINEL))

    with patch("prevue.review.load_config", side_effect=_load_config):
        yield


@pytest.fixture(autouse=True)
def _default_incremental_mocks(monkeypatch: pytest.MonkeyPatch):
    """Baseline incremental lifecycle mocks so legacy run_review tests stay hermetic."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    with (
        patch("prevue.review.decide_scope", return_value=("full", None, None)),
        # run_review calls _derive_prior_findings_with_threads; _finish_noop_review
        # still calls derive_prior_findings — mock both so all paths stay hermetic.
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.derive_prior_findings", return_value=[]),
        patch("prevue.review.resolve_outdated_prior_findings", return_value=set()),
        patch("prevue.review._read_sticky_body", return_value=None),
    ):
        yield


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
        patch("prevue.review.post_inline_review", return_value=set()) as mock_inline,
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


def test_run_review_with_findings_posts_sticky_then_inline_then_check() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    call_order: list[str] = []

    def track_inline(*_args, **_kwargs) -> set:
        call_order.append("inline")
        return set()

    def track_sticky(*_args, **_kwargs) -> MagicMock:
        call_order.append("sticky")
        return mock_sticky

    def track_check(*_args, **_kwargs) -> bool:
        call_order.append("check")
        return True

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
    assert call_order == ["sticky", "inline", "check"]


def test_run_review_inline_post_failure_downgrades_sticky_placements() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch(
            "prevue.review.post_inline_review",
            return_value={("src/example.py", 1, "RIGHT")},
        ) as mock_inline,
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=FindingsEngine())

    mock_inline.assert_called_once()
    assert mock_upsert.call_count == 2
    mock_check.assert_called_once()
    sticky_gate = mock_upsert.call_args.kwargs["gate"]
    assert sticky_gate.inline == []
    assert all(placed.placement != "inline" for placed in sticky_gate.placed)
    check_gate = mock_check.call_args[0][2]
    assert check_gate.inline == []
    assert all(placed.placement != "inline" for placed in check_gate.placed)


class TwoFindingsEngine:
    name = "two-findings"

    def review(self, req: ReviewRequest) -> ReviewResult:
        return ReviewResult(
            summary_markdown="Two issues.",
            findings=[
                Finding(
                    path="src/multi.py",
                    line=1,
                    side="RIGHT",
                    severity="warning",
                    title="First",
                    body="First issue.",
                ),
                Finding(
                    path="src/multi.py",
                    line=2,
                    side="RIGHT",
                    severity="warning",
                    title="Second",
                    body="Second issue.",
                ),
            ],
            engine_meta={"model": "fake", "duration_s": 0.1},
        )


def _two_line_diff() -> DiffBundle:
    return DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="src/multi.py",
                status="added",
                additions=2,
                deletions=0,
                patch="@@ -0,0 +1,2 @@\n+new1\n+new2",
            )
        ],
    )


def test_run_review_partial_inline_failure_downgrades_only_failed_finding() -> None:
    """Only the finding whose inline post failed is downgraded; the rest stay inline."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_two_line_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch(
            "prevue.review.post_inline_review",
            return_value={("src/multi.py", 2, "RIGHT")},
        ),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check"),
    ):
        run_review(adapter=TwoFindingsEngine())

    gate = mock_upsert.call_args.kwargs["gate"]
    inline_lines = {f.line for f in gate.inline}
    assert inline_lines == {1}
    placements = {(p.finding.line, p.placement) for p in gate.placed}
    assert (1, "inline") in placements
    assert (2, "summary-only") in placements


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
    mock_inline.assert_called_once()
    assert mock_inline.call_args[0][0] is mock_pr
    assert mock_inline.call_args[0][1] is gate
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


def test_run_review_bot_skip_neutral_no_engine() -> None:
    """NOIS-01: bot PR skips before engine; posts neutral check + sticky reason."""
    mock_pr = MagicMock()
    mock_pr.user.type = "Bot"
    mock_pr.user.login = "dependabot[bot]"
    mock_pr.title = "chore: bump deps"
    mock_pr.labels = []
    mock_pr.head.sha = HEAD_SHA
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called on skipped PR")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.upsert_skip_note") as mock_skip,
        patch("prevue.review.conclude_skip_check") as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
        patch("prevue.review.llm_classify") as mock_llm,
    ):
        run_review(adapter=SpyEngine())

    mock_fetch.assert_not_called()
    mock_skip.assert_called_once()
    assert mock_skip.call_args.kwargs.get("reason") is not None
    assert "dependabot" in mock_skip.call_args.kwargs["reason"]
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="neutral",
        reason=mock_skip.call_args.kwargs["reason"],
    )
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()
    mock_llm.assert_not_called()


def test_run_review_bot_skip_before_empty_filter_path() -> None:
    """NOIS-01: bot PR with only filtered files gets neutral bot skip, not empty success."""
    mock_pr = MagicMock()
    mock_pr.user.type = "Bot"
    mock_pr.user.login = "dependabot[bot]"
    mock_pr.title = "chore: bump deps"
    mock_pr.labels = []
    mock_pr.head.sha = HEAD_SHA
    mock_repo = _mock_repo()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.upsert_skip_note") as mock_skip,
        patch("prevue.review.conclude_skip_check") as mock_skip_check,
    ):
        run_review()

    mock_fetch.assert_not_called()
    mock_skip.assert_called_once()
    assert "dependabot" in mock_skip.call_args.kwargs["reason"]
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="neutral",
        reason=mock_skip.call_args.kwargs["reason"],
    )


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


def test_no_fit_neutral_skip() -> None:
    """D-24: single file exceeding whole input budget -> neutral skip, no engine."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    huge_patch = "+" * 500_000
    oversized = DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="src/huge.py",
                status="modified",
                additions=1,
                deletions=0,
                patch=huge_patch,
            ),
        ],
    )
    tiny_budget = MagicMock()
    tiny_budget.ruleset = MagicMock()
    tiny_budget.ruleset.label_rules = {"backend": ["**/*.py"]}
    tiny_budget.ruleset.ignore_globs = []
    tiny_budget.ruleset.routing_map = {"backend": "backend"}
    tiny_budget.review = MagicMock(max_input_tokens=100, output_reserve_tokens=0)
    tiny_budget.fallback = MagicMock(enabled=False)
    tiny_budget.skip = MagicMock()
    tiny_budget.skills = SkillsConfig()
    tiny_budget.engine = "fake"

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called when no file fits budget")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=oversized),
        patch("prevue.review.load_config", return_value=tiny_budget),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.classify") as mock_classify,
        patch("prevue.review.upsert_skip_note") as mock_skip,
        patch("prevue.review.conclude_skip_check") as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        from prevue.classify.models import ClassificationResult

        mock_classify.return_value = ClassificationResult(
            labels={"backend": "**/*.py"},
            bundles=["backend"],
        )
        run_review(adapter=SpyEngine())

    mock_skip.assert_called_once_with(mock_pr, reason="PR too large to review within budget")
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="neutral",
        reason="PR too large to review within budget",
    )
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


def test_empty_consumer_tree_does_not_over_reserve_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With PREVUE_CONSUMER_ROOT set but zero consumer skills loaded, the pack budget
    must not reserve the consumer ceiling (~64k tokens) — a file that fits the real
    budget is reviewed, not dropped for headroom that never materializes."""
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    # ~40k-token file: fits under available (108k) but NOT under the old ceiling-reserved
    # budget (108k - 65k = ~43k once builtin overhead is subtracted it would be dropped).
    big = DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[
            ChangedFile(
                path="src/big.py",
                status="modified",
                additions=1,
                deletions=0,
                patch="+" * 160_000,  # ~40k tokens at bytes/4
            )
        ],
    )
    config = PrevueConfig(
        ruleset=RuleSet(ignore_globs=[], label_rules={"backend": ["**/*.py"]}, routing_map={}),
        review=ReviewConfig(),  # default 120k budget
        skip=SkipConfig(),
        fallback=FallbackConfig(enabled=False),
        skills=SkillsConfig(),
        engine="fake",
    )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=big),
        patch("prevue.review.load_config", return_value=config),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        # No consumer skills load (empty tree); builtins also empty for a clean budget.
        patch(
            "prevue.review.load_skills",
            side_effect=lambda *a, **kw: ([], []) if kw.get("return_skipped") else [],
        ),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=FindingsEngine())

    kwargs = mock_upsert.call_args.kwargs
    assert kwargs["reviewed_file_count"] == 1, "file dropped despite fitting the real budget"
    assert kwargs["not_reviewed_file_count"] == 0


def test_byte_limit_skip_runs_before_classify(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-24: a packed prompt exceeding MAX_PROMPT_BYTES (byte-estimate drift) yields a
    neutral skip BEFORE llm_classify runs — no engine call, no classify tokens spent."""
    monkeypatch.setattr("prevue.review.MAX_PROMPT_BYTES", 10)
    mock_pr = MagicMock()
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called when prompt exceeds byte limit")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.llm_classify") as mock_llm,
        patch("prevue.review.upsert_skip_note") as mock_skip,
        patch("prevue.review.conclude_skip_check", return_value=True) as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=SpyEngine())

    mock_skip.assert_called_once_with(mock_pr, reason="PR too large to review within budget")
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="neutral",
        reason="PR too large to review within budget",
    )
    mock_llm.assert_not_called()  # byte guard runs before classification fallback
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


def test_run_review_empty_skip_raises_when_skip_check_not_published() -> None:
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

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=lockfile_only),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.upsert_skip_note"),
        patch("prevue.review.conclude_skip_check", return_value=False),
    ):
        with pytest.raises(RuntimeError, match="skip check run"):
            run_review(adapter=FindingsEngine())


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
            "prevue.review.load_config",
            side_effect=ValidationError.from_exception_data("ReviewConfig", []),
        ),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.get_adapter") as mock_get_adapter,
    ):
        with pytest.raises(ValidationError):
            run_review()

    mock_fetch.assert_not_called()
    mock_get_adapter.assert_not_called()


def test_run_review_load_config_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    # Hermetic: anchor the consumer root so the resolved path is deterministic
    # and does not depend on the ambient process CWD/env (CR-01).
    monkeypatch.delenv("PREVUE_CONFIG_PATH", raising=False)
    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.load_config") as mock_load_config,
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        from prevue.config import load_config as real_load_config

        mock_load_config.side_effect = real_load_config
        run_review(adapter=FindingsEngine())
        # CR-01: run_review now routes the default path through
        # resolve_consumer_config_path first, so load_config receives a
        # resolved absolute path anchored at PREVUE_CONSUMER_ROOT — not the
        # pre-fix unresolved relative ".github/prevue.yml".
        expected = str((tmp_path / ".github" / "prevue.yml").resolve())
        mock_load_config.assert_called_once_with(expected)


def test_run_review_fallback_skipped_when_all_matched() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    class SpyEngine(FindingsEngine):
        def classify(self, paths, allowed_labels, *, model=None):
            raise AssertionError("classify must not run when all files matched")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
        patch("prevue.review.llm_classify") as mock_llm,
    ):
        run_review(adapter=SpyEngine())
        mock_llm.assert_not_called()


def test_fallback_only_on_packed() -> None:
    """D-19/D-22: budget-skipped unmatched paths must not trigger llm_classify."""
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    budget_diff = DiffBundle(
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
                path="data/mystery_a.bin",
                status="added",
                additions=1,
                deletions=0,
                patch="+" * 400,
            ),
            ChangedFile(
                path="data/mystery_b.bin",
                status="added",
                additions=1,
                deletions=0,
                patch="+" * 200_000,
            ),
        ],
    )
    tight_config = PrevueConfig(
        ruleset=RuleSet(
            ignore_globs=[],
            label_rules={"frontend": ["**/*.tsx"]},
            routing_map={},
        ),
        # Tight budget: mystery_b.bin (~50k tokens) must not fit; mystery_a.bin (~100) must.
        review=ReviewConfig(max_input_tokens=5000, output_reserve_tokens=100),
        skip=SkipConfig(),
        fallback=FallbackConfig(enabled=True),
        skills=SkillsConfig(),
        engine="fake",
    )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=budget_diff),
        patch("prevue.review.load_config", return_value=tight_config),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch(
            "prevue.review.load_skills",
            side_effect=lambda *a, **kw: ([], []) if kw.get("return_skipped") else [],
        ),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
        patch(
            "prevue.review.llm_classify",
            return_value=({"data/mystery_a.bin": "backend"}, None),
        ) as mock_llm,
    ):
        run_review(adapter=FindingsEngine())

    mock_llm.assert_called_once()
    classified_paths = mock_llm.call_args[0][0]
    assert "data/mystery_b.bin" not in classified_paths
    assert "data/mystery_a.bin" in classified_paths
    assert mock_upsert.call_args.kwargs["not_reviewed_file_count"] == 1


def test_run_review_fallback_fires_on_unmatched_paths() -> None:
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
                path="mystery.bin",
                status="added",
                additions=1,
                deletions=0,
                patch="@@",
            ),
        ],
    )

    class ClassifyEngine(FindingsEngine):
        def classify(self, paths, allowed_labels, *, model=None):
            return {path: "backend" for path in paths}

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=mixed_diff),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=ClassifyEngine())

    classification = mock_upsert.call_args.kwargs["classification"]
    assert "backend" in classification.labels
    assert classification.labels["backend"] == "mystery.bin"
    assert "general" not in classification.labels


def _mixed_diff() -> DiffBundle:
    """A diff with one rule-matched file and one unmatched file (triggers fallback)."""
    return DiffBundle(
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
                path="mystery.bin",
                status="added",
                additions=1,
                deletions=0,
                patch="@@",
            ),
        ],
    )


def test_run_review_classify_tokens_zero_on_full_degrade() -> None:
    """WR-02: a fully degraded fallback must not bill any classify tokens."""
    from prevue.classify.llm_fallback import FALLBACK_DISCLOSURE, FALLBACK_FAILED_GLOB
    from prevue.classify.models import GENERAL_LABEL

    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_mixed_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
        patch(
            "prevue.review.llm_classify",
            return_value=({GENERAL_LABEL: FALLBACK_FAILED_GLOB}, FALLBACK_DISCLOSURE),
        ) as mock_llm,
    ):
        run_review(adapter=FindingsEngine())

    mock_llm.assert_called_once()
    token_meta = mock_upsert.call_args.kwargs["token_meta"]
    assert token_meta["classify"] == 0


def test_run_review_classify_tokens_nonzero_on_real_labels() -> None:
    """WR-02 pair: a fallback that produces real labels must bill a non-zero estimate."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_mixed_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
        patch(
            "prevue.review.llm_classify",
            return_value=({"mystery.bin": "backend"}, None),
        ) as mock_llm,
    ):
        run_review(adapter=FindingsEngine())

    mock_llm.assert_called_once()
    token_meta = mock_upsert.call_args.kwargs["token_meta"]
    assert token_meta["classify"] > 0


def test_run_review_partial_degrade_bills_routes_and_retains_general() -> None:
    """WR-01: a partial-degrade fallback shape must bill tokens, route real labels,
    and retain the partial-disclosure GENERAL_LABEL (not pop it)."""
    from prevue.classify.llm_fallback import FALLBACK_PARTIAL_GLOB
    from prevue.classify.models import GENERAL_LABEL

    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    partial_disclosure = (
        "classification fallback partially degraded — some files reviewed as general"
    )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_mixed_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
        patch(
            "prevue.review.llm_classify",
            return_value=(
                {"mystery.bin": "backend", GENERAL_LABEL: FALLBACK_PARTIAL_GLOB},
                partial_disclosure,
            ),
        ) as mock_llm,
    ):
        run_review(adapter=FindingsEngine())

    mock_llm.assert_called_once()
    kwargs = mock_upsert.call_args.kwargs
    # (a) non-zero classify estimate because real labels were produced
    assert kwargs["token_meta"]["classify"] > 0
    # (b) the real path → label entry was routed via the inversion
    classification = kwargs["classification"]
    assert classification.labels["backend"] == "mystery.bin"
    # (c) the partial-disclosure general label is retained, not popped by the dedup
    assert classification.labels[GENERAL_LABEL] == FALLBACK_PARTIAL_GLOB
    # disclosure is forwarded verbatim to the sticky comment
    assert kwargs["classification_disclosure"] == partial_disclosure


def test_engine_selection_via_prevue_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    monkeypatch.delenv("PREVUE_ENGINE", raising=False)
    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
        patch("prevue.review.get_adapter") as mock_get_adapter,
    ):
        mock_get_adapter.return_value = FindingsEngine()
        run_review()
        mock_get_adapter.assert_called_once_with("copilot-cli")

    monkeypatch.setenv("PREVUE_ENGINE", "nope")
    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
    ):
        with pytest.raises(UnknownEngineError, match="nope"):
            run_review()


def test_engine_failure_propagates_without_upsert() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review") as mock_inline,
        patch("prevue.review.upsert_sticky") as mock_upsert,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        with pytest.raises(EngineFailure, match="engine exploded"):
            run_review(adapter=FailingEngine())

    mock_inline.assert_not_called()
    mock_upsert.assert_not_called()
    mock_check.assert_not_called()


def test_run_review_raises_when_review_check_not_published() -> None:
    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=False),
    ):
        with pytest.raises(RuntimeError, match="review check run"):
            run_review(adapter=FindingsEngine())


def test_consumer_skills_root_skips_workspace_fallback_in_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SKIL-04: inside Actions, GITHUB_WORKSPACE must not load consumer skills (may be PR head)."""
    from prevue.review import _consumer_skills_root

    skills_dir = tmp_path / ".github" / "prevue" / "skills"
    skills_dir.mkdir(parents=True)

    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)

    root, note = _consumer_skills_root()
    assert root is None, "GITHUB_WORKSPACE must not be used as skills root inside Actions"
    # The skip is disclosed (sticky cap_skipped) and logged to stderr.
    assert note is not None and "PREVUE_CONSUMER_ROOT not set" in note
    assert "PREVUE_CONSUMER_ROOT not set" in capsys.readouterr().err

    # Explicit PREVUE_CONSUMER_ROOT still loads, even in Actions.
    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))
    root2, _ = _consumer_skills_root()
    assert root2 == skills_dir.resolve()


def test_run_review_malformed_consumer_skill_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed consumer skill: fail-closed check run, engine never invoked."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called on skill validation failure")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch(
            "prevue.review.load_skills",
            side_effect=ValidationError.from_exception_data("Skill", []),
        ),
        patch("prevue.review.upsert_skip_note") as mock_skip_note,
        patch("prevue.review.conclude_skip_check", return_value=True) as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=SpyEngine())

    mock_skip_note.assert_called_once()
    reason = mock_skip_note.call_args.kwargs.get("reason", "")
    assert "consumer skill" in reason
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="failure",
        reason=reason,
        title="review failed",
    )
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


def test_run_review_unreadable_consumer_skill_fail_closed() -> None:
    """OSError/UnicodeDecodeError from load_skills also fails closed (not just ValidationError)."""
    mock_pr = MagicMock()
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called on skill load failure")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch(
            "prevue.review.load_skills",
            side_effect=OSError("/secret/path/skill file unreadable"),
        ),
        patch("prevue.review.upsert_skip_note") as mock_skip_note,
        patch("prevue.review.conclude_skip_check", return_value=True) as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        run_review(adapter=SpyEngine())

    mock_skip_note.assert_called_once()
    reason = mock_skip_note.call_args.kwargs.get("reason", "")
    assert "consumer skill" in reason
    # The public message must not leak the raw exception text (paths / parser dumps).
    assert "/secret/path" not in reason
    assert "OSError" in reason
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="failure",
        reason=reason,
        title="review failed",
    )
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


def test_run_review_consumer_override_and_cap_disclosure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consumer skill override wins; oversized skill is disclosed in sticky cap_skipped."""
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    # Build consumer skills tree under tmp_path/.github/prevue/skills/security/
    skills_dir = tmp_path / ".github" / "prevue" / "skills" / "security"
    skills_dir.mkdir(parents=True)

    # Override skill — should win over built-in security bundle
    override = skills_dir / "committed-secrets.md"
    override.write_text(
        "---\n"
        "name: Committed Secrets (Consumer)\n"
        "description: consumer override\n"
        "applies-to:\n  - '**/*'\n"
        "---\n"
        "CONSUMER OVERRIDE sentinel\n"
    )
    # Oversized skill — exceeds max_skill_bytes cap, should appear in cap_skipped
    oversized = skills_dir / "oversized.md"
    oversized.write_text(
        "---\nname: Oversized\ndescription: too big\napplies-to:\n  - '**/*'\n---\n" + "x" * 70_000
    )

    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))

    mock_pr = MagicMock()
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    tight_skills = SkillsConfig(max_skill_bytes=50_000)

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.load_config") as mock_config,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        mock_config.return_value = PrevueConfig(
            ruleset=RuleSet(ignore_globs=[], label_rules={}, routing_map={}),
            review=ReviewConfig(),
            skip=SkipConfig(),
            fallback=FallbackConfig(enabled=False),
            skills=tight_skills,
            engine="fake",
        )
        run_review(adapter=FindingsEngine())

    call_kwargs = mock_upsert.call_args.kwargs
    cap_skipped = call_kwargs["cap_skipped"]
    assert any("oversized.md" in s for s in cap_skipped), (
        f"oversized not in cap_skipped: {cap_skipped}"
    )
    loaded = call_kwargs["loaded_skills"]
    assert any("Consumer" in s for s in loaded), f"consumer override not in loaded_skills: {loaded}"


def test_run_review_invalid_yaml_frontmatter_fail_closed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A consumer skill with syntactically invalid YAML frontmatter fails closed
    (yaml.YAMLError from frontmatter.loads) instead of crashing the job."""
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    skills_dir = tmp_path / ".github" / "prevue" / "skills" / "security"
    skills_dir.mkdir(parents=True)
    # Invalid YAML: unbalanced bracket / bad indentation in the frontmatter block.
    bad = skills_dir / "broken.md"
    bad.write_text("---\nname: [unclosed\n  bad: : :\napplies-to: ]\n---\nbody\n")

    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))

    mock_pr = MagicMock()
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not be called on invalid YAML frontmatter")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.load_config") as mock_config,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.upsert_skip_note") as mock_skip_note,
        patch("prevue.review.conclude_skip_check", return_value=True) as mock_skip_check,
        patch("prevue.review.upsert_sticky") as mock_sticky,
        patch("prevue.review.conclude_review_check") as mock_check,
    ):
        mock_config.return_value = PrevueConfig(
            ruleset=RuleSet(ignore_globs=[], label_rules={}, routing_map={}),
            review=ReviewConfig(),
            skip=SkipConfig(),
            fallback=FallbackConfig(enabled=False),
            skills=SkillsConfig(),
            engine="fake",
        )
        run_review(adapter=SpyEngine())

    mock_skip_note.assert_called_once()
    reason = mock_skip_note.call_args.kwargs.get("reason", "")
    assert "consumer skill" in reason
    mock_skip_check.assert_called_once_with(
        mock_repo,
        HEAD_SHA,
        conclusion="failure",
        reason=reason,
        title="review failed",
    )
    mock_sticky.assert_not_called()
    mock_check.assert_not_called()


# --- Phase 8 incremental lifecycle (08-06) ---

LAST_SHA = "deadbeef123456789012345678901234567890ab"


def _sticky_with_marker(*, sha: str | None = None) -> MagicMock:
    from prevue.github.comments import MARKER, render_marker

    comment = MagicMock()
    comment.user.login = "github-actions[bot]"
    comment.user.type = "Bot"
    if sha:
        comment.body = f"{render_marker(sha)}\n## Prevue Review\n\nPrior run."
    else:
        comment.body = f"{MARKER}\n## Prevue Review\n\nLegacy run."
    return comment


def _scoped_diff() -> DiffBundle:
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
            ),
        ],
    )


def test_full_first_run_writes_head_marker(fake_engine) -> None:
    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = []
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    captured_body: dict[str, str] = {}

    def capture_upsert(*_args, **kwargs) -> MagicMock:
        captured_body["head_sha"] = kwargs.get("head_sha")
        return mock_sticky

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("full", None, None)),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", side_effect=capture_upsert) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=fake_engine)

    mock_upsert.assert_called_once()
    assert captured_body["head_sha"] == HEAD_SHA


def test_incremental_scope_reviews_only_in_scope_files() -> None:
    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    in_scope = {"src/example.py"}
    captured: dict[str, object] = {}

    class CaptureEngine:
        name = "capture"

        def review(self, req: ReviewRequest) -> ReviewResult:
            captured["paths"] = [f.path for f in req.diff.files]
            return ReviewResult(
                summary_markdown="ok",
                findings=[],
                engine_meta={"model": "fake", "duration_s": 0.1},
            )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("incremental", in_scope, None)),
        patch("prevue.review.fetch_diff_in_scope", return_value=_scoped_diff()) as mock_inc,
        patch("prevue.review.fetch_diff") as mock_full,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=CaptureEngine())

    mock_inc.assert_called_once_with(in_scope)
    mock_full.assert_not_called()
    assert captured["paths"] == ["src/example.py"]


def test_identical_rerun_noop_skips_engine() -> None:
    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=HEAD_SHA)]
    mock_repo = _mock_repo()

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not run on identical noop")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("noop", None, None)),
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.derive_prior_findings", return_value=[]),
        patch("prevue.review._upsert_marker_comment") as mock_upsert_marker,
        patch("prevue.review.conclude_review_check", return_value=True) as mock_check,
        patch("prevue.review.post_inline_review") as mock_inline,
        patch("prevue.review.resolve_outdated_prior_findings") as mock_resolve,
    ):
        # noop scope → _finish_noop_review, not the full priors path
        run_review(adapter=SpyEngine())

    mock_fetch.assert_not_called()
    mock_inline.assert_not_called()
    mock_resolve.assert_not_called()
    mock_upsert_marker.assert_called_once()
    body = mock_upsert_marker.call_args[0][1]
    from prevue.github.comments import parse_marker_sha

    assert parse_marker_sha(body) == HEAD_SHA
    mock_check.assert_called_once()


def test_incremental_empty_after_filter_refreshes_marker() -> None:
    """Incremental delta with no reviewable files still advances marker."""
    from prevue.models import DiffBundle

    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    empty_diff = DiffBundle(
        pr_number=1,
        base_sha="base",
        head_sha=HEAD_SHA,
        files=[],
    )

    class SpyEngine:
        name = "spy"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise AssertionError("engine must not run when incremental diff filters empty")

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch(
            "prevue.review.decide_scope",
            return_value=("incremental", {"vendor/ignored.py"}, MagicMock()),
        ),
        patch("prevue.review.fetch_diff_in_scope", return_value=empty_diff),
        patch("prevue.review.fetch_diff") as mock_full,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review.derive_prior_findings", return_value=[]),
        patch("prevue.review._upsert_marker_comment") as mock_upsert_marker,
        patch("prevue.review.conclude_review_check", return_value=True),
        patch("prevue.review.post_inline_review") as mock_inline,
    ):
        run_review(adapter=SpyEngine())

    mock_full.assert_not_called()
    mock_inline.assert_not_called()
    mock_upsert_marker.assert_called_once()
    from prevue.github.comments import parse_marker_sha

    assert parse_marker_sha(mock_upsert_marker.call_args[0][1]) == HEAD_SHA


def test_incremental_false_forces_full_despite_marker() -> None:
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    config = PrevueConfig(
        ruleset=RuleSet(ignore_globs=[], label_rules={"backend": ["**/*.py"]}, routing_map={}),
        review=ReviewConfig(incremental=False),
        skip=SkipConfig(),
        fallback=FallbackConfig(enabled=False),
        skills=SkillsConfig(),
        engine="fake",
    )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.load_config", return_value=config),
        patch("prevue.review.decide_scope", return_value=("full", None, None)) as mock_scope,
        patch("prevue.review.fetch_diff", return_value=_sample_diff()) as mock_full,
        patch("prevue.review.fetch_diff_in_scope") as mock_inc,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=FindingsEngine())

    mock_scope.assert_called_once()
    assert mock_scope.call_args[0][1] is None
    mock_full.assert_called_once()
    mock_inc.assert_not_called()


def test_open_set_false_green_blocks_success_on_carried_error() -> None:
    from prevue.github.comments import PriorFinding

    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    carried = PriorFinding(
        path="src/other.py",
        line=5,
        side="RIGHT",
        title="Prior security bug",
        fingerprint="abc123prior00001",
        severity="error",
        thread_id=None,
    )

    class CleanEngine:
        name = "clean"

        def review(self, req: ReviewRequest) -> ReviewResult:
            return ReviewResult(
                summary_markdown="Clean incremental push.",
                findings=[],
                engine_meta={"model": "fake", "duration_s": 0.1},
            )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("incremental", {"src/example.py"}, None)),
        patch("prevue.review.fetch_diff_in_scope", return_value=_scoped_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([carried], [])),
        patch("prevue.review.resolve_outdated_prior_findings", return_value=set()),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True) as mock_check,
    ):
        run_review(adapter=CleanEngine())

    gate = mock_upsert.call_args.kwargs["gate"]
    assert gate.conclusion != "success"
    assert gate.severity_counts["error"] == 1
    check_gate = mock_check.call_args[0][2]
    assert check_gate.conclusion != "success"


def test_fingerprints_outdated_by_region_excludes_from_known_items() -> None:
    from prevue.github.comments import PriorFinding
    from prevue.review import _build_known_issues_items, _fingerprints_outdated_by_region

    priors = [
        PriorFinding(
            path="src/a.py",
            line=10,
            side="RIGHT",
            title="Stale issue",
            fingerprint=fingerprint("src/a.py", "Stale issue"),
            severity="warning",
            thread_id=None,
        ),
        PriorFinding(
            path="src/b.py",
            line=5,
            side="RIGHT",
            title="Still valid",
            fingerprint=fingerprint("src/b.py", "Still valid"),
            severity="warning",
            thread_id=None,
        ),
    ]
    regions = {"src/a.py": [(8, 12)]}
    in_scope = {"src/a.py", "src/b.py"}
    outdated = _fingerprints_outdated_by_region(priors, in_scope, regions)
    assert outdated == {priors[0].fingerprint}
    items = _build_known_issues_items(priors, in_scope, 10, exclude_fingerprints=outdated)
    assert items == [("src/b.py", 5, "Still valid")]


def test_open_set_dedupes_carried_prior_at_same_line_as_current() -> None:
    """Rephrase-at-same-line: when current has a DIFFERENT fingerprint at the same
    (path,line,side), the open-set must keep the CARRIED prior title (which matches
    the live inline thread that D-06 left unchanged) — not the new engine title."""
    from prevue.github.comments import PriorFinding

    current = [
        Finding(
            path="src/test1.js",
            line=4,
            severity="error",
            title="Console.log uses wrong identifier casing",
            body="",
        )
    ]
    carried = PriorFinding(
        path="src/test1.js",
        line=4,
        side="RIGHT",
        title="Invalid Console.log — use console.log",
        fingerprint=fingerprint("src/test1.js", "Invalid Console.log — use console.log"),
        severity="error",
        thread_id=None,
    )

    open_findings = _open_set_findings(current, [carried], set())

    assert len(open_findings) == 1
    assert open_findings[0].title == "Invalid Console.log — use console.log"


def test_open_set_keeps_current_on_severity_escalation_at_same_line() -> None:
    """Rephrase + escalation: current error wins over carried warning at same loc."""
    from prevue.github.comments import PriorFinding

    current = [
        Finding(
            path="src/test1.js",
            line=4,
            severity="error",
            title="Console.log uses wrong identifier casing",
            body="",
        )
    ]
    carried = PriorFinding(
        path="src/test1.js",
        line=4,
        side="RIGHT",
        title="Invalid Console.log — use console.log",
        fingerprint=fingerprint("src/test1.js", "Invalid Console.log — use console.log"),
        severity="warning",
        thread_id=None,
    )

    open_findings = _open_set_findings(current, [carried], set())

    assert len(open_findings) == 1
    assert open_findings[0].severity == "error"
    assert open_findings[0].title == "Console.log uses wrong identifier casing"


def test_open_set_drops_true_duplicate_at_same_line() -> None:
    """True duplicate (current fingerprint == carried fingerprint): one entry, current chosen."""
    from prevue.github.comments import PriorFinding

    # Both titles normalize to the same fingerprint — genuine duplicate, current wins.
    carried_title = "Console.log uses wrong identifier casing"
    current = [
        Finding(
            path="src/test1.js",
            line=4,
            severity="error",
            title=carried_title,
            body="Fixed body",
        )
    ]
    carried = PriorFinding(
        path="src/test1.js",
        line=4,
        side="RIGHT",
        title=carried_title,
        fingerprint=fingerprint("src/test1.js", carried_title),
        severity="error",
        thread_id=None,
    )

    open_findings = _open_set_findings(current, [carried], set())

    assert len(open_findings) == 1
    assert open_findings[0].title == carried_title


def test_open_set_dedupes_multiple_current_at_same_line() -> None:
    current = [
        Finding(
            path="src/test1.js",
            line=8,
            severity="info",
            title="Undeclared identifier World",
            body="",
        ),
        Finding(
            path="src/test1.js",
            line=8,
            severity="error",
            title="Undefined variable World",
            body="",
        ),
    ]

    open_findings = _open_set_findings(current, [], set())

    assert len(open_findings) == 1
    assert open_findings[0].title == "Undefined variable World"


def test_open_set_keeps_carried_prior_at_different_line() -> None:
    from prevue.github.comments import PriorFinding

    current = [
        Finding(
            path="src/test2.js",
            line=1,
            severity="error",
            title="Undefined identifier console2",
            body="",
        )
    ]
    carried = PriorFinding(
        path="src/test1.js",
        line=4,
        side="RIGHT",
        title="Invalid Console.log — use console.log",
        fingerprint=fingerprint("src/test1.js", "Invalid Console.log — use console.log"),
        severity="error",
        thread_id=None,
    )

    open_findings = _open_set_findings(current, [carried], set())

    assert len(open_findings) == 2
    assert {(f.path, f.line) for f in open_findings} == {("src/test2.js", 1), ("src/test1.js", 4)}


def test_known_issues_in_prompt_capped_on_incremental() -> None:
    from prevue.github.comments import PriorFinding

    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    priors = [
        PriorFinding(
            path="src/example.py",
            line=i,
            side="RIGHT",
            title=f"Issue {i}",
            fingerprint=f"fp{i:02d}",
            severity="warning",
            thread_id=None,
        )
        for i in range(1, 6)
    ]
    captured_prompts: list[str] = []

    class PromptCaptureEngine:
        name = "capture"

        def review(self, req: ReviewRequest) -> ReviewResult:
            from prevue.engines.prompt import build_prompt

            # Capture the prompt as flow.review_with_retry builds it — with
            # known_issues/max_known_issues from req (WR-05: no monkey-patching).
            captured_prompts.append(
                build_prompt(
                    req, known_issues=req.known_issues, max_known_issues=req.max_known_issues
                )
            )
            return ReviewResult(
                summary_markdown="ok",
                findings=[],
                engine_meta={"model": "fake", "duration_s": 0.1},
            )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("incremental", {"src/example.py"}, None)),
        patch("prevue.review.fetch_diff_in_scope", return_value=_scoped_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=(priors, [])),
        patch("prevue.review.resolve_outdated_prior_findings", return_value=set()),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        from prevue.classify.models import RuleSet
        from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
        from prevue.gate import ReviewConfig

        tight = PrevueConfig(
            ruleset=RuleSet(ignore_globs=[], label_rules={"backend": ["**/*.py"]}, routing_map={}),
            review=ReviewConfig(max_known_issues=3),
            skip=SkipConfig(),
            fallback=FallbackConfig(enabled=False),
            skills=SkillsConfig(),
            engine="fake",
        )
        with patch("prevue.review.load_config", return_value=tight):
            run_review(adapter=PromptCaptureEngine())

    assert captured_prompts
    prompt = captured_prompts[-1]
    assert "Already reported" in prompt
    assert prompt.count("title=") == 3


def test_resolve_opt_out_never_calls_graphql_resolve() -> None:
    from prevue.classify.models import RuleSet
    from prevue.config import FallbackConfig, PrevueConfig, SkillsConfig, SkipConfig
    from prevue.gate import ReviewConfig

    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = []
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()
    config = PrevueConfig(
        ruleset=RuleSet(ignore_globs=[], label_rules={"backend": ["**/*.py"]}, routing_map={}),
        review=ReviewConfig(resolve_outdated=False),
        skip=SkipConfig(),
        fallback=FallbackConfig(enabled=False),
        skills=SkillsConfig(),
        engine="fake",
    )

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.load_config", return_value=config),
        patch("prevue.review.decide_scope", return_value=("full", None, None)),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.resolve_outdated_prior_findings") as mock_resolve,
        patch("prevue.review.post_inline_review", return_value=set()) as mock_inline,
        patch("prevue.review.upsert_sticky", return_value=mock_sticky),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=FindingsEngine())

    mock_resolve.assert_not_called()
    mock_inline.assert_called_once()
    assert mock_inline.call_args.kwargs.get("resolve_outdated") is False


def test_marker_write_after_run_parseable(fake_engine) -> None:
    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = []
    mock_repo = _mock_repo()
    rendered: dict[str, str] = {}

    def fake_upsert(pr, result, **kwargs):
        from prevue.github.comments import render_body

        rendered["body"] = render_body(
            result,
            gate=kwargs.get("gate"),
            head_sha=kwargs.get("head_sha"),
        )
        sticky = MagicMock()
        sticky.html_url = STICKY_URL
        return sticky

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("full", None, None)),
        patch("prevue.review.fetch_diff", return_value=_sample_diff()),
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", side_effect=fake_upsert),
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=fake_engine)

    from prevue.github.comments import parse_marker_sha

    assert parse_marker_sha(rendered["body"]) == HEAD_SHA


def _incremental_two_file_diff() -> DiffBundle:
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
            ),
            ChangedFile(
                path="src/untouched.py",
                status="modified",
                additions=1,
                deletions=0,
                patch="@@ -1 +1 @@\n+noop",
            ),
        ],
    )


def test_force_push_resets_to_full_review() -> None:
    mock_pr = MagicMock()
    mock_pr.head.sha = HEAD_SHA
    mock_pr.get_issue_comments.return_value = [_sticky_with_marker(sha=LAST_SHA)]
    mock_repo = _mock_repo()
    mock_sticky = _mock_sticky()

    with (
        patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
        patch("prevue.review.decide_scope", return_value=("full", None, None)) as mock_scope,
        patch("prevue.review.fetch_diff", return_value=_incremental_two_file_diff()) as mock_full,
        patch("prevue.review.fetch_diff_in_scope") as mock_inc,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.get_repo", return_value=mock_repo),
        patch("prevue.review._derive_prior_findings_with_threads", return_value=([], [])),
        patch("prevue.review.post_inline_review", return_value=set()),
        patch("prevue.review.upsert_sticky", return_value=mock_sticky) as mock_upsert,
        patch("prevue.review.conclude_review_check", return_value=True),
    ):
        run_review(adapter=FindingsEngine())

    mock_scope.assert_called_once()
    mock_full.assert_called_once()
    mock_inc.assert_not_called()
    assert mock_upsert.call_args.kwargs.get("head_sha") == HEAD_SHA
