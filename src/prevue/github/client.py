"""GitHub PR context from Actions event payload — no git checkout."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from github import Auth, Github
from github.PullRequest import PullRequest


@dataclass(frozen=True)
class PrContext:
    repo_full: str
    pr_number: int
    head_repo_full: str
    base_repo_full: str


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
