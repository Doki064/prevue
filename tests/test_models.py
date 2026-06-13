"""Contract tests for the engine adapter pydantic models (ENGN-01)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prevue.models import (
    ChangedFile,
    DiffBundle,
    Finding,
    ReviewRequest,
    ReviewResult,
)


def test_review_result_defaults_findings_and_engine_meta() -> None:
    result = ReviewResult(summary_markdown="x")
    assert result.findings == []
    assert result.degraded is False
    assert result.dropped_findings == 0
    assert result.engine_meta == {}


def test_finding_rejects_non_canonical_severity() -> None:
    with pytest.raises(ValidationError):
        Finding(
            path="src/main.py",
            line=1,
            severity="critical",
            title="t",
            body="b",
        )


def test_finding_rejects_non_positive_line() -> None:
    with pytest.raises(ValidationError):
        Finding(
            path="src/main.py",
            line=0,
            severity="warning",
            title="t",
            body="b",
        )


def test_finding_rejects_invalid_side() -> None:
    with pytest.raises(ValidationError):
        Finding(
            path="src/main.py",
            line=1,
            side="MIDDLE",
            severity="warning",
            title="t",
            body="b",
        )


@pytest.mark.parametrize("severity", ["error", "warning", "info"])
def test_finding_accepts_canonical_severities(severity: str) -> None:
    finding = Finding(
        path="src/main.py",
        line=1,
        severity=severity,
        title="t",
        body="b",
    )
    assert finding.severity == severity


def test_review_request_requires_diff_and_instructions() -> None:
    bundle = DiffBundle(
        pr_number=1,
        base_sha="abc",
        head_sha="def",
        files=[],
    )
    req = ReviewRequest(diff=bundle, instructions="Review carefully.")
    assert req.budget_seconds == 300
    assert req.model is None


def test_review_request_rejects_missing_diff() -> None:
    with pytest.raises(ValidationError):
        ReviewRequest(instructions="Review carefully.")  # type: ignore[call-arg]


def test_changed_file_accepts_none_patch() -> None:
    cf = ChangedFile(
        path="large.bin",
        status="added",
        additions=0,
        deletions=0,
        patch=None,
    )
    assert cf.patch is None


def test_diff_bundle_carries_pr_metadata_and_files() -> None:
    files = [
        ChangedFile(
            path="src/main.py",
            status="modified",
            additions=3,
            deletions=1,
            patch="@@ -1 +1 @@",
        )
    ]
    bundle = DiffBundle(pr_number=42, base_sha="base", head_sha="head", files=files)
    assert bundle.pr_number == 42
    assert bundle.base_sha == "base"
    assert bundle.head_sha == "head"
    assert len(bundle.files) == 1


@pytest.mark.parametrize("model_cls", [DiffBundle, ReviewRequest])
def test_no_pr_title_or_body_fields(model_cls: type) -> None:
    forbidden = {"title", "body", "pr_title", "pr_body"}
    assert forbidden.isdisjoint(model_cls.model_fields)


def test_review_result_json_round_trip() -> None:
    finding = Finding(
        path="src/main.py",
        line=10,
        side="RIGHT",
        severity="warning",
        title="Unused import",
        body="Remove the unused import.",
        suggestion="Delete line 10.",
    )
    original = ReviewResult(
        summary_markdown="## Review\n\nOne warning.",
        findings=[finding],
        engine_meta={"model": "gpt-4", "duration_s": 1.5},
    )
    restored = ReviewResult.model_validate_json(original.model_dump_json())
    assert restored == original
