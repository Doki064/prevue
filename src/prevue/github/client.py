"""GitHub PR context from Actions event payload — no git checkout."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from github import Auth, Github
from github.PullRequest import PullRequest
from github.Repository import Repository


@dataclass(frozen=True)
class PrContext:
    repo_full: str
    pr_number: int
    head_repo_full: str
    base_repo_full: str


@dataclass(frozen=True)
class CommentContext:
    repo_full: str
    issue_number: int
    comment_body: str
    comment_author: str
    author_association: str
    head_repo_full: str
    base_repo_full: str
    head_sha: str
    base_sha: str


def load_pr_context() -> PrContext:
    """Read PR context from GITHUB_EVENT_PATH + GITHUB_REPOSITORY in one parse."""
    repo_full = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    pr = event["pull_request"]
    return PrContext(
        repo_full=repo_full,
        pr_number=pr["number"],
        head_repo_full=pr["head"]["repo"]["full_name"],
        base_repo_full=pr["base"]["repo"]["full_name"],
    )


def get_authenticated_pull(ctx: PrContext) -> PullRequest:
    """Resolve the PR via PyGithub REST API (no checkout)."""
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    return gh.get_repo(ctx.repo_full).get_pull(ctx.pr_number)


def get_repo(ctx: PrContext) -> Repository:
    """Resolve the repository for repo-scoped APIs (e.g. Checks)."""
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    return gh.get_repo(ctx.repo_full)


def load_comment_context() -> CommentContext:
    """Read issue_comment event + env vars; resolve PR SHAs via get_pull (§L1)."""
    repo_full = os.environ["GITHUB_REPOSITORY"]
    issue_number = int(os.environ["PREVUE_ISSUE_NUMBER"])
    comment_body = os.environ["PREVUE_COMMENT_BODY"]
    comment_author = os.environ["PREVUE_COMMENT_AUTHOR"]

    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)

    event_issue_number = event["issue"]["number"]
    if event_issue_number != issue_number:
        msg = (
            f"PREVUE_ISSUE_NUMBER ({issue_number}) "
            f"does not match event issue number ({event_issue_number})"
        )
        raise ValueError(msg)

    author_association = event["comment"]["author_association"]

    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    pull = gh.get_repo(repo_full).get_pull(issue_number)

    return CommentContext(
        repo_full=repo_full,
        issue_number=issue_number,
        comment_body=comment_body,
        comment_author=comment_author,
        author_association=author_association,
        head_repo_full=pull.head.repo.full_name,
        base_repo_full=pull.base.repo.full_name,
        head_sha=pull.head.sha,
        base_sha=pull.base.sha,
    )
