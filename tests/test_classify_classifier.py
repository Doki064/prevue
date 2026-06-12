"""Tests for classify — multi-label union, general fallback, canonical ordering."""

from __future__ import annotations

import pytest

from prevue.classify.classifier import classify
from prevue.models import ChangedFile

GENERAL_LABEL = "general"
CANONICAL_LABEL_ORDER = ("security", "frontend", "backend", "data", "infra", "general")

FRONTEND_RULES = {"frontend": ["**/*.tsx", "**/*.css"]}
BACKEND_RULES = {"backend": ["**/*.py"]}
ALL_RULES = {
    "frontend": ["**/*.tsx"],
    "backend": ["**/*.py"],
    "infra": ["**/*.tf"],
    "data": ["**/*.sql"],
    "security": ["**/.env*"],
}


def _file(path: str) -> ChangedFile:
    return ChangedFile(path=path, status="modified", additions=1, deletions=0, patch="@@")


def test_classify_frontend_tsx() -> None:
    result = classify([_file("src/App.tsx")], FRONTEND_RULES)
    assert result.labels == {"frontend": "**/*.tsx"}


def test_classify_backend_py() -> None:
    result = classify([_file("api/main.py")], BACKEND_RULES)
    assert result.labels == {"backend": "**/*.py"}


@pytest.mark.parametrize(
    ("path", "rules", "expected"),
    [
        ("src/App.tsx", FRONTEND_RULES, {"frontend": "**/*.tsx"}),
        ("styles/app.css", FRONTEND_RULES, {"frontend": "**/*.css"}),
    ],
)
def test_classify_matched_glob_provenance(
    path: str,
    rules: dict[str, list[str]],
    expected: dict[str, str],
) -> None:
    result = classify([_file(path)], rules)
    assert result.labels == expected


def test_classify_union_multi_domain() -> None:
    """D-01: PR spanning domains receives every matched label."""
    files = [_file("src/App.tsx"), _file("terraform/main.tf")]
    result = classify(files, ALL_RULES)
    assert set(result.labels.keys()) == {"frontend", "infra"}
    assert result.labels["frontend"] == "**/*.tsx"
    assert result.labels["infra"] == "**/*.tf"


def test_classify_general_all_unmatched() -> None:
    """D-02/D-03: whole PR matched nothing → general fallback."""
    files = [_file("README.txt"), _file("notes.org")]
    result = classify(files, ALL_RULES)
    assert result.labels == {GENERAL_LABEL: "(no rule matched)"}


def test_classify_general_not_alongside_real_labels() -> None:
    """D-03: mixed PR with one matched file stays specific — no general."""
    files = [_file("src/App.tsx"), _file("README.txt")]
    result = classify(files, ALL_RULES)
    assert set(result.labels.keys()) == {"frontend"}
    assert GENERAL_LABEL not in result.labels


def test_classify_canonical_label_order() -> None:
    """Pitfall 5: labels emitted in fixed canonical order regardless of file order."""
    files = [_file("terraform/main.tf"), _file("src/App.tsx")]
    result = classify(files, ALL_RULES)
    present = list(result.labels.keys())
    expected_order = [label for label in CANONICAL_LABEL_ORDER if label in result.labels]
    assert present == expected_order
    assert present.index("frontend") < present.index("infra")


def test_classify_overlap_records_both_labels() -> None:
    """D-01: file matching two labels records both (deliberate overlap)."""
    rules = {
        "security": ["**/.env*"],
        "frontend": ["**/.env.local.tsx"],
    }
    result = classify([_file("src/.env.local.tsx")], rules)
    assert set(result.labels.keys()) == {"security", "frontend"}
