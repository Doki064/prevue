"""RED contract tests for engine output parsing — fence extraction and salvage (ENGN-03)."""

from __future__ import annotations

import json

from prevue.engines.parsing import extract_json_fence, validate_findings

from prevue.models import Finding

VALID_FINDING = {
    "path": "src/main.py",
    "line": 12,
    "side": "RIGHT",
    "severity": "warning",
    "title": "Unused import",
    "body": "Remove the unused import.",
}


def _stdout_with_fence(*, prose_before: str = "## Review\n\nLooks good.", json_body: str) -> str:
    return f"{prose_before}\n\n```json\n{json_body}\n```"


class TestExtractJsonFence:
    def test_last_fence_wins_when_decoy_appears_earlier(self) -> None:
        stdout = (
            "Decoy fence:\n```json\n[{\"bad\": true}]\n```\n\n"
            + _stdout_with_fence(json_body=json.dumps([VALID_FINDING]))
        )
        prose, items, err = extract_json_fence(stdout)
        assert err is None
        assert items is not None
        assert len(items) == 1
        assert items[0]["path"] == "src/main.py"
        assert "Decoy fence" in prose
        assert "```json" not in prose

    def test_prose_has_extracted_fence_removed(self) -> None:
        stdout = _stdout_with_fence(
            prose_before="Summary paragraph.",
            json_body='[{"path":"a.py","line":1,"severity":"info","title":"t","body":"b"}]',
        )
        prose, items, err = extract_json_fence(stdout)
        assert err is None
        assert items is not None
        assert prose == "Summary paragraph."
        assert "path" not in prose or "a.py" not in prose

    def test_no_fence_returns_error(self) -> None:
        stdout = "## Review\n\nNo structured output here."
        prose, items, err = extract_json_fence(stdout)
        assert items is None
        assert err is not None
        assert "fence" in err.lower()
        assert prose == stdout

    def test_malformed_json_returns_prose_and_error(self) -> None:
        stdout = _stdout_with_fence(prose_before="Usable summary.", json_body="{not valid json")
        prose, items, err = extract_json_fence(stdout)
        assert items is None
        assert err is not None
        assert "Usable summary." in prose
        assert "```json" not in prose

    def test_top_level_object_not_array_returns_error(self) -> None:
        stdout = _stdout_with_fence(json_body='{"path":"a.py"}')
        prose, items, err = extract_json_fence(stdout)
        assert items is None
        assert err is not None
        assert "array" in err.lower()

    def test_accepts_uppercase_json_fence(self) -> None:
        stdout = (
            "## Review\n\nLooks good.\n\n"
            f"```JSON\n{json.dumps([VALID_FINDING])}\n```"
        )
        prose, items, err = extract_json_fence(stdout)
        assert err is None
        assert items is not None
        assert len(items) == 1
        assert items[0]["path"] == VALID_FINDING["path"]
        assert "```JSON" not in prose

    def test_accepts_crlf_fence_newlines(self) -> None:
        stdout = (
            "## Review\r\n\r\nLooks good.\r\n\r\n"
            f"```json\r\n{json.dumps([VALID_FINDING])}\r\n```"
        )
        prose, items, err = extract_json_fence(stdout)
        assert err is None
        assert items is not None
        assert len(items) == 1
        assert items[0]["path"] == VALID_FINDING["path"]
        assert "```json" not in prose


class TestValidateFindings:
    def test_mixed_list_keeps_valid_and_counts_dropped(self) -> None:
        items = [
            VALID_FINDING,
            {"path": "x.py", "line": 1, "severity": "nope", "title": "t", "body": "b"},
            {"path": "y.py", "line": 2, "severity": "error", "title": "ok", "body": "b"},
        ]
        valid, dropped = validate_findings(items)
        assert dropped == 1
        assert len(valid) == 2
        assert all(isinstance(f, Finding) for f in valid)
        assert {f.path for f in valid} == {"src/main.py", "y.py"}

    def test_wrong_case_severity_drops(self) -> None:
        items = [{**VALID_FINDING, "severity": "ERROR"}]
        valid, dropped = validate_findings(items)
        assert valid == []
        assert dropped == 1

    def test_unknown_severity_critical_drops(self) -> None:
        items = [{**VALID_FINDING, "severity": "critical"}]
        valid, dropped = validate_findings(items)
        assert valid == []
        assert dropped == 1

    def test_line_as_string_drops_under_strict_validation(self) -> None:
        items = [{**VALID_FINDING, "line": "12"}]
        valid, dropped = validate_findings(items)
        assert valid == []
        assert dropped == 1
