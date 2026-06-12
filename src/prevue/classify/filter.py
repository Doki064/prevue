"""Filter diff files by ignore globs before classification (D-08)."""

from __future__ import annotations

from pathspec import GitIgnoreSpec

from prevue.models import ChangedFile, DiffBundle


def filter_diff(
    diff: DiffBundle,
    ignore_globs: list[str],
) -> tuple[DiffBundle, list[ChangedFile]]:
    """Return reduced diff and dropped files; original diff unchanged."""
    if not ignore_globs:
        return diff.model_copy(), []

    spec = GitIgnoreSpec.from_lines(ignore_globs)
    kept: list[ChangedFile] = []
    dropped: list[ChangedFile] = []
    for f in diff.files:
        if spec.match_file(f.path):
            dropped.append(f)
        else:
            kept.append(f)
    return diff.model_copy(update={"files": kept}), dropped
