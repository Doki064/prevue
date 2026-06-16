"""Diff hunk position validity for inline review comments (OUTP-02, D-17)."""

from __future__ import annotations

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

from prevue.models import ChangedFile, Finding


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


def is_placeable(
    finding: Finding,
    valid_lines: dict[str, dict[str, set[int]]],
) -> bool:
    """True when (path, line, side) maps to a commentable diff line."""
    side_lines = valid_lines.get(finding.path, {}).get(finding.side)
    return side_lines is not None and finding.line in side_lines


def annotate_patch(path: str, patch: str | None) -> str:
    """Prefix diff lines with file line numbers for engine prompts (OUTP-02)."""
    if not patch:
        return ""
    try:
        ps = PatchSet(f"--- a/{path}\n+++ b/{path}\n{patch}")
    except UnidiffParseError:
        return patch
    lines: list[str] = []
    for pf in ps:
        for hunk in pf:
            lines.append(
                f"@@ -{hunk.source_start},{hunk.source_length} "
                f"+{hunk.target_start},{hunk.target_length} @@"
            )
            for line in hunk:
                if line.line_type == "\\":
                    continue
                if line.is_removed:
                    lines.append(f"{line.source_line_no:5d} | -{line.value.rstrip(chr(10))}")
                elif line.is_added:
                    lines.append(f"{line.target_line_no:5d} | +{line.value.rstrip(chr(10))}")
                elif line.is_context:
                    lines.append(f"{line.target_line_no:5d} |  {line.value.rstrip(chr(10))}")
    if not lines:
        return patch
    return "\n".join(lines)


def reconcile_finding_locations(
    findings: list[Finding],
    valid_lines: dict[str, dict[str, set[int]]],
) -> list[Finding]:
    """Fix path/side when line uniquely matches one commentable diff location."""
    reconciled: list[Finding] = []
    for finding in findings:
        if is_placeable(finding, valid_lines):
            reconciled.append(finding)
            continue
        matches: list[tuple[str, str]] = []
        for path, sides in valid_lines.items():
            for side in ("RIGHT", "LEFT"):
                if finding.line in sides.get(side, set()):
                    matches.append((path, side))
        if len(matches) == 1:
            path, side = matches[0]
            reconciled.append(finding.model_copy(update={"path": path, "side": side}))
        else:
            reconciled.append(finding)
    return reconciled


def regions_changed(path: str, incremental_patch: str | None) -> list[tuple[int, int]]:
    """RIGHT-side (start, end) line ranges touched in an incremental patch (D-09)."""
    if not incremental_patch:
        return []
    try:
        ps = PatchSet(f"--- a/{path}\n+++ b/{path}\n{incremental_patch}")
    except UnidiffParseError:
        return []
    regions: list[tuple[int, int]] = []
    for pf in ps:
        for hunk in pf:
            target_lines: list[int] = []
            for line in hunk:
                if (line.is_added or line.is_context) and line.target_line_no is not None:
                    target_lines.append(line.target_line_no)
            if target_lines:
                regions.append((min(target_lines), max(target_lines)))
    return regions


def finding_region_changed(
    finding: Finding,
    regions: list[tuple[int, int]],
    context: int = 3,
) -> bool:
    """True when finding line overlaps a touched hunk or is within C lines of it."""
    return any(
        start <= finding.line + context and finding.line - context <= end for start, end in regions
    )
