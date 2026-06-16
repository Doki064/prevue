"""Pure /prevue command parser, authorization, and dispatcher (D-16)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from github import Auth, Github
from github.Repository import Repository

from prevue.config import load_config, resolve_consumer_config_path
from prevue.dismiss import create_dismiss_entry
from prevue.engines.base import EngineAdapter
from prevue.gate import ReviewConfig
from prevue.github.client import CommentContext, PrContext, load_comment_context
from prevue.github.comments import PriorFinding, derive_prior_findings
from prevue.github.graphql import resolve_review_thread
from prevue.review import FORK_UNSUPPORTED_MSG, run_review

FINGERPRINT_RE = re.compile(r"^[0-9a-f]{16}$")
THREAD_ID_RE = re.compile(r"^[A-Za-z0-9_=-]{8,}$")
MAX_REASON_LEN = 500
_VALID_VERBS = frozenset({"review", "dismiss", "resolve"})

WRITE_ACCESS_REPLY = "🔒 /prevue requires write access"
USAGE_REPLY = (
    "Unrecognized /prevue command. Usage: "
    "`/prevue review` | `/prevue dismiss <id> [reason: text]` | `/prevue resolve <id>`"
)


@dataclass(frozen=True)
class Command:
    verb: Literal["review", "dismiss", "resolve"]
    id: str | None = None
    reason: str | None = None


def _valid_id(token: str) -> bool:
    return bool(FINGERPRINT_RE.match(token) or THREAD_ID_RE.match(token))


def _find_command_line(body: str) -> str | None:
    """Return the first /prevue line outside fenced code blocks."""
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("/prevue"):
            return stripped
    return None


def _parse_dismiss_reason(parts: list[str], line: str, id_token: str) -> str | None:
    """Extract optional reason text after a dismiss id token."""
    prefix = f"/prevue dismiss {id_token}"
    if not line.startswith(prefix):
        return None
    tail = line[len(prefix) :].strip()
    if not tail.startswith("reason:"):
        return None
    reason_text = tail[len("reason:") :].strip()
    if not reason_text:
        return None
    return reason_text[:MAX_REASON_LEN]


def parse_command(body: str) -> Command | None:
    """Parse the first /prevue command line; return None on unknown or malformed input."""
    line = _find_command_line(body)
    if line is None:
        return None

    parts = line.split()
    if len(parts) < 2 or parts[0] != "/prevue":
        return None

    verb = parts[1]
    if verb not in _VALID_VERBS:
        return None

    if verb == "review":
        return Command(verb="review")

    if len(parts) < 3:
        return None

    id_token = parts[2]
    if not _valid_id(id_token):
        return None

    reason = _parse_dismiss_reason(parts, line, id_token) if verb == "dismiss" else None
    return Command(verb=verb, id=id_token, reason=reason)


def authorize_commenter(repo: Repository, login: str) -> bool:
    """Return True when the commenter has write, maintain, or admin permission."""
    permission = repo.get_collaborator_permission(login)
    return permission in {"maintain", "write", "admin"}


def _get_repo_and_pull(ctx: CommentContext) -> tuple[Repository, object]:
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    repo = gh.get_repo(ctx.repo_full)
    pr = repo.get_pull(ctx.issue_number)
    return repo, pr


def _comment_to_pr_ctx(ctx: CommentContext) -> PrContext:
    return PrContext(
        repo_full=ctx.repo_full,
        pr_number=ctx.issue_number,
        head_repo_full=ctx.head_repo_full,
        base_repo_full=ctx.base_repo_full,
    )


def _load_review_cfg() -> ReviewConfig:
    consumer_path = resolve_consumer_config_path(
        os.environ.get("PREVUE_CONFIG_PATH"),
        consumer_root=os.environ.get("PREVUE_CONSUMER_ROOT"),
    )
    return load_config(str(consumer_path)).review


def _find_prior_by_ident(priors: list[PriorFinding], ident: str) -> PriorFinding | None:
    for prior in priors:
        if prior.fingerprint == ident or prior.thread_id == ident:
            return prior
    return None


def _handle_dismiss(
    pr,
    cmd: Command,
    ctx: CommentContext,
    *,
    review_cfg: ReviewConfig,
) -> str:
    owner, repo_name = ctx.repo_full.split("/", 1)
    result = create_dismiss_entry(
        pr,
        ident=cmd.id or "",
        reason=cmd.reason,
        actor=ctx.comment_author,
        owner=owner,
        repo=repo_name,
        review_cfg=review_cfg,
    )
    if isinstance(result, str):
        return result
    return (
        f"Dismissed finding `{result.fingerprint}` "
        f"(recorded in sticky suppress-list by {result.actor})."
    )


def _handle_resolve(pr, cmd: Command, ctx: CommentContext) -> str:
    owner, repo_name = ctx.repo_full.split("/", 1)
    priors = derive_prior_findings(pr, owner=owner, repo=repo_name)
    target = _find_prior_by_ident(priors, cmd.id or "")
    if target is None:
        return f"no open finding matches `{cmd.id}`"
    thread_id = target.thread_id
    if not thread_id:
        return f"no review thread found for `{cmd.id}`"
    if resolve_review_thread(thread_id):
        return f"Resolved review thread for `{cmd.id}`."
    return f"Could not resolve review thread for `{cmd.id}` (best-effort)."


def run_command(*, adapter: EngineAdapter | None = None) -> int:
    """Authorize-first /prevue dispatcher: review / dismiss / resolve."""
    ctx = load_comment_context()
    repo, pr = _get_repo_and_pull(ctx)

    if not authorize_commenter(repo, ctx.comment_author):
        pr.create_issue_comment(WRITE_ACCESS_REPLY)
        return 0

    if ctx.head_repo_full != ctx.base_repo_full:
        pr.create_issue_comment(FORK_UNSUPPORTED_MSG)
        return 0

    cmd = parse_command(ctx.comment_body)
    if cmd is None:
        pr.create_issue_comment(USAGE_REPLY)
        return 0

    if cmd.verb == "review":
        run_review(force_full=True, adapter=adapter, pr_ctx=_comment_to_pr_ctx(ctx))
        return 0

    review_cfg = _load_review_cfg()
    if cmd.verb == "dismiss":
        pr.create_issue_comment(_handle_dismiss(pr, cmd, ctx, review_cfg=review_cfg))
        return 0

    if cmd.verb == "resolve":
        pr.create_issue_comment(_handle_resolve(pr, cmd, ctx))
        return 0

    return 0
