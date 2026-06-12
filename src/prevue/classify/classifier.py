"""Classify changed files into labels with matched-glob provenance (CLSF-01)."""

from __future__ import annotations

from pathspec import GitIgnoreSpec

from prevue.classify.models import (
    CANONICAL_LABEL_ORDER,
    GENERAL_LABEL,
    ClassificationResult,
)
from prevue.models import ChangedFile

NO_RULE_MATCHED = "(no rule matched)"


def _order_labels(labels: dict[str, str]) -> dict[str, str]:
    """Emit labels in fixed canonical order (Pitfall 5 determinism)."""
    ordered = {
        label: labels[label]
        for label in CANONICAL_LABEL_ORDER
        if label in labels
    }
    for label, glob in labels.items():
        if label not in ordered:
            ordered[label] = glob
    return ordered


def classify(
    files: list[ChangedFile],
    label_rules: dict[str, list[str]],
) -> ClassificationResult:
    """Multi-label union classify with PR-level general fallback (D-01, D-03)."""
    labels: dict[str, str] = {}
    specs = {
        label: GitIgnoreSpec.from_lines(globs)
        for label, globs in label_rules.items()
    }
    for f in files:
        for label, spec in specs.items():
            if label in labels:
                continue
            res = spec.check_file(f.path)
            if res.include:
                labels[label] = label_rules[label][res.index]
    if not labels:
        labels = {GENERAL_LABEL: NO_RULE_MATCHED}
    return ClassificationResult(labels=_order_labels(labels))
