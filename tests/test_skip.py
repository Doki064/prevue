"""RED contract tests for skip evaluation and neutral surfacing (NOIS-01)."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import responses

from prevue.config import SkipConfig
from prevue.github.checks import CHECK_NAME, conclude_skip_check
from prevue.github.comments import upsert_skip_note
from prevue.skip import should_skip


def _label(name: str) -> MagicMock:
    label = MagicMock()
    label.name = name
    return label


def _bot_pr(*, login: str = "dependabot[bot]", labels: list[str] | None = None) -> MagicMock:
    pr = MagicMock()
    pr.user.type = "Bot"
    pr.user.login = login
    pr.title = "chore: bump deps"
    pr.labels = [_label(label) for label in (labels or [])]
    return pr


def _human_pr(
    *,
    title: str = "feat: add widget",
    labels: list[str] | None = None,
) -> MagicMock:
    pr = MagicMock()
    pr.user.type = "User"
    pr.user.login = "alice"
    pr.title = title
    pr.labels = [_label(label) for label in (labels or [])]
    return pr


def test_bot_skip_neutral() -> None:
    cfg = SkipConfig()
    reason = should_skip(_bot_pr(), cfg)
    assert reason is not None
    assert "dependabot[bot]" in reason

    repo = MagicMock()
    conclude_skip_check(repo, "sha123", conclusion="neutral", reason=reason)
    kwargs = repo.create_check_run.call_args.kwargs
    assert kwargs["name"] == CHECK_NAME
    assert kwargs["conclusion"] == "neutral"


def test_label_and_title() -> None:
    cfg = SkipConfig()
    label_reason = should_skip(_human_pr(labels=["skip-review"]), cfg)
    assert label_reason is not None
    assert "skip-review" in label_reason

    title_cfg = SkipConfig(skip_title_patterns=[r"^WIP:"])
    title_reason = should_skip(_human_pr(title="WIP: draft feature"), title_cfg)
    assert title_reason is not None
    assert re.search("WIP", title_reason)


def test_none_title_does_not_crash() -> None:
    """WR-05: a None PR title must not make re.search raise TypeError."""
    cfg = SkipConfig(skip_title_patterns=[r"^WIP:"])
    pr = _human_pr()
    pr.title = None
    # Title is None and no other skip condition applies → proceed (None), no raise.
    assert should_skip(pr, cfg) is None


def test_bot_with_none_login_skips_as_unknown() -> None:
    """WR-05: a Bot author with login=None is skipped as an unknown bot, not crashed."""
    cfg = SkipConfig()
    pr = _bot_pr(login=None)  # type: ignore[arg-type]
    reason = should_skip(pr, cfg)
    assert reason == "bot author unknown"


@responses.activate
def test_skip_surface(responses_activated: None) -> None:
    pr = MagicMock()
    pr.number = 7
    pr.create_issue_comment = MagicMock()
    pr.get_issue_comments = MagicMock(return_value=[])
    pr.base.repo.full_name = "owner/repo"

    reason = "skip label skip-review"
    upsert_skip_note(pr, reason=reason)
    pr.create_issue_comment.assert_called_once()
    call = pr.create_issue_comment.call_args
    body = call.kwargs.get("body") or call[0][0]
    assert reason in body

    repo = MagicMock()
    conclude_skip_check(repo, "sha789", conclusion="neutral", reason=reason)
    assert repo.create_check_run.call_args.kwargs["conclusion"] == "neutral"
