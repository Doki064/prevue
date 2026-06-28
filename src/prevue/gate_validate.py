"""Gate revalidation for repository_dispatch command runs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from github import Auth, Github
from pydantic import BaseModel

from prevue.commands import authorize_commenter, needs_engine_for_body, parse_command
from prevue.github.client import read_comment_body

TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
DEFAULT_FRAMEWORK_REPO = "Doki064/prevue"


class GateValidationError(Exception):
    pass


class DispatchPayload(BaseModel):
    issue_number: str
    head_sha: str
    base_sha: str
    framework_sha: str
    comment_body: str
    comment_author: str
    comment_author_association: str
    comment_id: str
    needs_engine: bool
    engine: str


def load_dispatch_payload() -> DispatchPayload:
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    return DispatchPayload.model_validate(event["client_payload"])


def resolve_framework_sha(prevue_ref: str, *, framework_repo: str = DEFAULT_FRAMEWORK_REPO) -> str:
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    return gh.get_repo(framework_repo).get_commit(prevue_ref).sha


def validate_command_dispatch(
    *,
    payload: DispatchPayload,
    pull,
    comment,
    expected_engine: str,
    framework_sha: str,
    repository: str,
) -> None:
    if pull.head.sha != payload.head_sha:
        raise GateValidationError("Pinned head SHA does not match PR head; refusing.")
    if pull.base.sha != payload.base_sha:
        raise GateValidationError("Pinned base SHA does not match PR base; refusing.")
    if pull.head.repo.full_name != repository:
        raise GateValidationError("Fork PR; refusing.")
    if framework_sha != payload.framework_sha:
        raise GateValidationError("Framework SHA does not match resolved PREVUE_REF; refusing.")

    repo = pull.base.repo
    if not authorize_commenter(repo, payload.comment_author):
        raise GateValidationError("Comment author lacks write access; refusing.")

    issue_url = comment.issue_url or ""
    url_issue_number = issue_url.rsplit("/", 1)[-1] if issue_url else ""
    if url_issue_number != str(payload.issue_number):
        raise GateValidationError("Comment is not on the expected PR issue; refusing.")

    live_association = comment.author_association or ""
    if live_association not in TRUSTED_ASSOCIATIONS:
        raise GateValidationError("Comment author association is not trusted; refusing.")
    if live_association != payload.comment_author_association:
        raise GateValidationError(
            "Comment author association does not match gate payload; refusing."
        )

    live_body = (comment.body or "").rstrip("\r\n")
    if live_body != payload.comment_body.rstrip("\r\n"):
        raise GateValidationError("Comment body does not match gate payload; refusing.")

    live_author = comment.user.login
    if live_author != payload.comment_author:
        raise GateValidationError("Comment author does not match gate payload; refusing.")

    if parse_command(live_body) is None:
        raise GateValidationError("Comment is not a /prevue command; refusing.")

    expected_needs_engine = needs_engine_for_body(live_body)
    if payload.needs_engine != expected_needs_engine:
        raise GateValidationError("needs_engine does not match comment verb; refusing.")
    if payload.engine != expected_engine:
        raise GateValidationError("Engine does not match repo PREVUE_ENGINE; refusing.")


def run_gate_revalidate() -> int:
    payload = load_dispatch_payload()
    repository = os.environ["GITHUB_REPOSITORY"]
    issue_number = int(payload.issue_number)
    comment_id = int(payload.comment_id)
    expected_engine = os.environ.get("PREVUE_ENGINE", "copilot-cli")
    prevue_ref = os.environ.get("PREVUE_REF", "main")
    framework_repo = os.environ.get("PREVUE_FRAMEWORK_REPO", DEFAULT_FRAMEWORK_REPO)

    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    repo = gh.get_repo(repository)
    pull = repo.get_pull(issue_number)
    comment = repo.get_issue(issue_number).get_comment(comment_id)
    framework_sha = resolve_framework_sha(prevue_ref, framework_repo=framework_repo)

    try:
        validate_command_dispatch(
            payload=payload,
            pull=pull,
            comment=comment,
            expected_engine=expected_engine,
            framework_sha=framework_sha,
            repository=repository,
        )
    except GateValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def materialize_comment_event(
    *,
    issue_number: int,
    comment_body: str,
    comment_author: str,
    comment_author_association: str,
    output_path: Path,
) -> Path:
    payload = {
        "issue": {"number": issue_number, "pull_request": {}},
        "comment": {
            "body": comment_body,
            "user": {"login": comment_author},
            "author_association": comment_author_association,
        },
    }
    output_path.write_text(json.dumps(payload), encoding="utf-8")
    return output_path


def run_materialize_comment_event() -> int:
    issue_number = int(os.environ["PREVUE_ISSUE_NUMBER"])
    output_path = Path(os.environ["RUNNER_TEMP"]) / "issue_comment.json"
    materialize_comment_event(
        issue_number=issue_number,
        comment_body=read_comment_body(),
        comment_author=os.environ["PREVUE_COMMENT_AUTHOR"],
        comment_author_association=os.environ["PREVUE_COMMENT_AUTHOR_ASSOCIATION"],
        output_path=output_path,
    )
    # GITHUB_EVENT_PATH is a runner system var that GITHUB_ENV cannot override.
    # Use PREVUE_COMMENT_EVENT_PATH so load_comment_context() reads the right file.
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as env_file:
            env_file.write(f"PREVUE_COMMENT_EVENT_PATH={output_path}\n")
    return 0
