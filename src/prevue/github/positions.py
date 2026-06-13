"""Diff hunk position validity for inline review comments (OUTP-02, D-17)."""

from __future__ import annotations

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

from prevue.models import ChangedFile


def commentable_lines(path: str, patch: str | None) -> dict[str, set[int]]:
    """Valid (side -> line numbers) for one file's GitHub patch fragment."""
    if not patch:
        return {"RIGHT": set(), "LEFT": set()}
    try:
        # GitHub's files[].patch has no ---/+++ headers; synthesize them.
        ps = PatchSet(f"--- a/{path}\n+++ b/{path}\n{patch}")
    except UnidiffParseError:
        return {"RIGHT": set(), "LEFT": set()}
    right: set[int] = set()
    left: set[int] = set()
    for pf in ps:
        for hunk in pf:
            for line in hunk:
                if line.is_added or line.is_context:
                    right.add(line.target_line_no)
                if line.is_removed:
                    left.add(line.source_line_no)
    right.discard(None)
    left.discard(None)
    return {"RIGHT": right, "LEFT": left}


def build_valid_lines(
    files: list[ChangedFile],
) -> dict[str, dict[str, set[int]]]:
    """Map each changed file path to commentable line sets per side."""
    return {f.path: commentable_lines(f.path, f.patch) for f in files}
