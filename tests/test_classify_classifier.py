"""Tests for classify — single-pass label assignment with matched-glob provenance."""

from __future__ import annotations

import pytest

from prevue.classify.classifier import classify
from prevue.models import ChangedFile

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


def test_classify_unmatched_returns_empty_labels() -> None:
    result = classify([_file("README.txt")], ALL_RULES)
    assert result.labels == {}


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
