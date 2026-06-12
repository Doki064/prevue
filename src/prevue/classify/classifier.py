"""Classify changed files into labels with matched-glob provenance (CLSF-01)."""

from __future__ import annotations

from pathspec import GitIgnoreSpec

from prevue.classify.models import ClassificationResult
from prevue.models import ChangedFile


def classify(
    files: list[ChangedFile],
    label_rules: dict[str, list[str]],
) -> ClassificationResult:
    """Single-pass classify: first matching glob per label wins."""
    # Plan 02: D-01 union, D-03 general, canonical sort
    labels: dict[str, str] = {}
    specs = {
        label: GitIgnoreSpec.from_lines(globs)
        for label, globs in label_rules.items()
    }
    for f in files:
        for label, spec in specs.items():
            res = spec.check_file(f.path)
            if res.include:
                labels[label] = label_rules[label][res.index]
                break
    return ClassificationResult(labels=labels)
