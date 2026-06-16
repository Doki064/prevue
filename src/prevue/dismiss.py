"""PR-scoped dismiss suppress-list stored in the sticky comment (D-14/D-15)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from prevue.fingerprint import fingerprint
from prevue.gate import SEVERITY_RANK, ReviewConfig
from prevue.github.positions import finding_region_changed
from prevue.models import Finding

DISMISS_BLOCK_OPEN = "<!-- prevue:dismiss -->"
DISMISS_BLOCK_CLOSE = "<!-- /prevue:dismiss -->"

_DISMISS_BLOCK_RE = re.compile(
    re.escape(DISMISS_BLOCK_OPEN) + r"(.*?)" + re.escape(DISMISS_BLOCK_CLOSE),
    re.DOTALL,
)


class DismissEntry(BaseModel):
    """One maintainer-dismissed finding record (PR-scoped, base-ref sticky only)."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    path: str
    region: tuple[int, int]
    side: Literal["RIGHT", "LEFT"] = "RIGHT"
    severity: str
    actor: str
    timestamp: str
    reason: str


def parse_dismiss_block(body: str | None) -> list[DismissEntry]:
    """Parse the fenced JSON dismiss block from a sticky body; fail-safe to []."""
    if not body:
        return []
    match = _DISMISS_BLOCK_RE.search(body)
    if not match:
        return []
    raw = match.group(1).strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")].strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    entries: list[DismissEntry] = []
    try:
        for item in data:
            entries.append(DismissEntry.model_validate(item))
    except ValidationError:
        return []
    return entries


def render_dismiss_block(entries: list[DismissEntry]) -> str:
    """Render the human-visible audit section + machine-parseable fenced JSON."""
    payload = [entry.model_dump() for entry in entries]
    json_text = json.dumps(payload, indent=2)
    return (
        "### Dismissed findings\n"
        f"{DISMISS_BLOCK_OPEN}\n"
        f"```json\n{json_text}\n```\n"
        f"{DISMISS_BLOCK_CLOSE}\n"
    )


def active_suppressed_fingerprints(
    entries: list[DismissEntry],
    current_findings: list[Finding],
    regions_by_path: dict[str, list[tuple[int, int]]],
) -> set[str]:
    """Return fingerprints still validly suppressed this run (D-15 guards 2/3)."""
    if not entries:
        return set()

    max_rank = max(SEVERITY_RANK.values(), default=2)
    current_by_fp: dict[str, Finding] = {}
    for finding in current_findings:
        fp = fingerprint(finding.path, finding.title)
        existing = current_by_fp.get(fp)
        if existing is None or SEVERITY_RANK.get(finding.severity, max_rank) < SEVERITY_RANK.get(
            existing.severity, max_rank
        ):
            current_by_fp[fp] = finding

    active: set[str] = set()
    for entry in entries:
        stub = Finding(
            path=entry.path,
            line=entry.region[0],
            side=entry.side,
            severity=entry.severity if entry.severity in SEVERITY_RANK else "info",
            title="",
            body="",
        )
        if finding_region_changed(stub, regions_by_path.get(entry.path, [])):
            continue
        current = current_by_fp.get(entry.fingerprint)
        if current is not None:
            entry_rank = SEVERITY_RANK.get(entry.severity, max_rank + 1)
            current_rank = SEVERITY_RANK.get(current.severity, max_rank)
            if current_rank < entry_rank:
                continue
        active.add(entry.fingerprint)
    return active


def _find_prior_by_ident(priors, ident: str):

    for prior in priors:
        if prior.fingerprint == ident or prior.thread_id == ident:
            return prior
    return None


def _read_sticky_body(pr) -> str | None:
    from prevue.github.comments import _is_prevue_sticky

    newest: str | None = None
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            newest = comment.body or ""
    return newest


def _merge_dismiss_into_sticky_body(
    body: str | None,
    entries: list[DismissEntry],
    *,
    head_sha: str | None,
) -> str:
    from prevue.github.comments import MARKER, render_marker

    without = _DISMISS_BLOCK_RE.sub("", body or "").rstrip()
    new_block = render_dismiss_block(entries)
    if not without:
        marker = render_marker(head_sha) if head_sha else MARKER
        return f"{marker}\n## Prevue Review\n\n{new_block}"
    from prevue.github.comments import LEGACY_METADATA_HEADING, METADATA_SUMMARY

    for metadata_marker in (METADATA_SUMMARY, LEGACY_METADATA_HEADING):
        if metadata_marker in without:
            prefix, suffix = without.split(metadata_marker, 1)
            return f"{prefix.rstrip()}\n{new_block}{metadata_marker}{suffix}"
    return f"{without}\n{new_block}"


def create_dismiss_entry(
    pr,
    *,
    ident: str,
    reason: str | None,
    actor: str,
    owner: str,
    repo: str,
    review_cfg: ReviewConfig,
) -> DismissEntry | str:
    """Guard-1 dismiss creation: finding must exist; error severity needs reason."""
    from prevue.github.comments import _upsert_marker_comment, derive_prior_findings

    priors = derive_prior_findings(pr, owner=owner, repo=repo)
    target = _find_prior_by_ident(priors, ident)
    if target is None:
        return f"no open finding matches `{ident}`"

    severity = target.severity or "warning"
    if severity == "error" and not (reason and reason.strip()):
        return "dismissing an error requires a reason"

    side: Literal["RIGHT", "LEFT"] = "RIGHT" if target.side != "LEFT" else "LEFT"
    entry = DismissEntry(
        fingerprint=target.fingerprint,
        path=target.path,
        region=(target.line, target.line),
        side=side,
        severity=severity,
        actor=actor,
        timestamp=datetime.now(UTC).isoformat(),
        reason=reason or "",
    )

    sticky_body = _read_sticky_body(pr)
    existing = parse_dismiss_block(sticky_body)
    by_fp = {item.fingerprint: item for item in existing}
    by_fp[entry.fingerprint] = entry
    entries = list(by_fp.values())[: review_cfg.max_dismissals]

    head_sha = getattr(getattr(pr, "head", None), "sha", None)
    new_body = _merge_dismiss_into_sticky_body(sticky_body, entries, head_sha=head_sha)
    _upsert_marker_comment(pr, new_body)
    return entry
