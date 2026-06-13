"""RED contract tests for review gate policy (NOIS-02/03, OUTP-03)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prevue.gate import (
    GateResult,
    ReviewConfig,
    apply_gate,
    conclude,
    load_review_config,
    severity_counts_line,
    thresholds_line,
    verdict_title,
)
from prevue.models import Finding


def _finding(
    *,
    path: str = "src/a.py",
    line: int = 10,
    side: str = "RIGHT",
    severity: str = "warning",
    title: str = "issue",
) -> Finding:
    return Finding(
        path=path,
        line=line,
        side=side,
        severity=severity,
        title=title,
        body="details",
    )


def _valid_lines(*, path: str = "src/a.py", right: set[int] | None = None) -> dict:
    return {path: {"RIGHT": right or {10}, "LEFT": set()}}


class TestReviewConfig:
    def test_defaults(self) -> None:
        cfg = ReviewConfig()
        assert cfg.min_severity_to_comment == "warning"
        assert cfg.min_severity_to_fail is None
        assert cfg.max_inline_comments == 10

    def test_unknown_severity_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewConfig(min_severity_to_comment="blocker")  # type: ignore[arg-type]

    def test_unknown_extra_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewConfig.model_validate({"max_inline_comments": 5, "typo_key": 1})

    def test_negative_max_inline_comments_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewConfig(max_inline_comments=-1)

    def test_load_review_config_none_returns_defaults(self) -> None:
        cfg = load_review_config(None)
        assert cfg == ReviewConfig()

    def test_load_review_config_no_review_section_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "prevue.yml"
        path.write_text("ignore:\n  - '**/*.lock'\n")
        cfg = load_review_config(str(path))
        assert cfg == ReviewConfig()

    def test_load_review_config_consumer_overrides(self, tmp_path: Path) -> None:
        path = tmp_path / "prevue.yml"
        path.write_text("review:\n  min_severity_to_fail: error\n  max_inline_comments: 3\n")
        cfg = load_review_config(str(path))
        assert cfg.min_severity_to_fail == "error"
        assert cfg.max_inline_comments == 3
        assert cfg.min_severity_to_comment == "warning"

    def test_load_review_config_invalid_severity_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "prevue.yml"
        path.write_text("review:\n  min_severity_to_fail: blocker\n")
        with pytest.raises(ValidationError):
            load_review_config(str(path))


class TestConclude:
    def test_no_findings_not_degraded_success(self) -> None:
        assert conclude([], ReviewConfig(), degraded=False) == "success"

    def test_findings_default_neutral_when_fail_unset(self) -> None:
        assert conclude([_finding()], ReviewConfig(), degraded=False) == "neutral"

    def test_warning_meets_fail_threshold_failure(self) -> None:
        cfg = ReviewConfig(min_severity_to_fail="warning")
        assert conclude([_finding(severity="warning")], cfg, degraded=False) == "failure"

    def test_info_below_fail_threshold_neutral(self) -> None:
        cfg = ReviewConfig(min_severity_to_fail="warning")
        assert conclude([_finding(severity="info")], cfg, degraded=False) == "neutral"

    def test_degraded_always_neutral(self) -> None:
        cfg = ReviewConfig(min_severity_to_fail="warning")
        assert conclude([_finding(severity="error")], cfg, degraded=True) == "neutral"


class TestApplyGate:
    def test_severity_counts_all_three_keys_all_findings(self) -> None:
        findings = [
            _finding(severity="error", line=10),
            _finding(severity="info", line=11, path="src/b.py"),
        ]
        valid = {
            "src/a.py": {"RIGHT": {10, 11}, "LEFT": set()},
            "src/b.py": {"RIGHT": {11}, "LEFT": set()},
        }
        gate = apply_gate(findings, ReviewConfig(), valid)
        assert set(gate.severity_counts.keys()) == {"error", "warning", "info"}
        assert gate.severity_counts["error"] == 1
        assert gate.severity_counts["info"] == 1

    def test_info_summary_only_under_default_config(self) -> None:
        gate = apply_gate([_finding(severity="info")], ReviewConfig(), _valid_lines())
        assert gate.placed[0].placement == "summary-only"

    def test_invalid_position_gets_position_fallback(self) -> None:
        gate = apply_gate(
            [_finding(line=999)],
            ReviewConfig(),
            _valid_lines(right={10}),
        )
        assert gate.placed[0].placement == "position-fallback"
        assert gate.inline == []

    def test_hallucinated_path_gets_position_fallback(self) -> None:
        gate = apply_gate(
            [_finding(path="src/missing.py")],
            ReviewConfig(),
            _valid_lines(),
        )
        assert gate.placed[0].placement == "position-fallback"

    def test_budget_cap_only_first_n_placeable_inline(self) -> None:
        cfg = ReviewConfig(max_inline_comments=2)
        findings = [
            _finding(path="src/a.py", line=10, severity="error", title="e1"),
            _finding(path="src/a.py", line=11, severity="error", title="e2"),
            _finding(path="src/a.py", line=12, severity="error", title="e3"),
        ]
        valid = {"src/a.py": {"RIGHT": {10, 11, 12}, "LEFT": set()}}
        gate = apply_gate(findings, cfg, valid)
        assert len(gate.inline) == 2
        assert gate.inline[0].title == "e1"
        assert gate.inline[1].title == "e2"
        overflow = [p for p in gate.placed if p.finding.title == "e3"][0]
        assert overflow.placement == "summary-only"

    def test_unplaceable_error_does_not_consume_slot(self) -> None:
        cfg = ReviewConfig(max_inline_comments=1)
        findings = [
            _finding(path="src/a.py", line=999, severity="error", title="bad-pos"),
            _finding(path="src/a.py", line=10, severity="warning", title="good"),
        ]
        valid = {"src/a.py": {"RIGHT": {10}, "LEFT": set()}}
        gate = apply_gate(findings, cfg, valid)
        assert len(gate.inline) == 1
        assert gate.inline[0].title == "good"

    def test_inline_order_errors_before_warnings_emission_order(self) -> None:
        findings = [
            _finding(severity="warning", line=11, title="w1"),
            _finding(severity="error", line=10, title="e1"),
            _finding(severity="error", line=12, title="e2"),
        ]
        valid = {"src/a.py": {"RIGHT": {10, 11, 12}, "LEFT": set()}}
        gate = apply_gate(findings, ReviewConfig(), valid)
        titles = [f.title for f in gate.inline]
        assert titles == ["e1", "e2", "w1"]

    def test_placed_ordered_error_warning_info(self) -> None:
        findings = [
            _finding(severity="info", line=13, title="i1"),
            _finding(severity="error", line=10, title="e1"),
            _finding(severity="warning", line=11, title="w1"),
        ]
        valid = {"src/a.py": {"RIGHT": {10, 11, 13}, "LEFT": set()}}
        gate = apply_gate(findings, ReviewConfig(), valid)
        severities = [p.finding.severity for p in gate.placed]
        assert severities == ["error", "warning", "info"]

    def test_max_inline_zero_everything_summary_only(self) -> None:
        cfg = ReviewConfig(max_inline_comments=0)
        gate = apply_gate([_finding(severity="error")], cfg, _valid_lines())
        assert gate.inline == []
        assert all(p.placement == "summary-only" for p in gate.placed)

    def test_degraded_neutral_empty_inline(self) -> None:
        gate = apply_gate([], ReviewConfig(), {}, degraded=True)
        assert gate.conclusion == "neutral"
        assert gate.inline == []
        assert gate.degraded is True


class TestVerdictStrings:
    def _gate(
        self,
        *,
        conclusion: str = "success",
        counts: dict[str, int] | None = None,
        degraded: bool = False,
        fail: str | None = None,
    ) -> GateResult:
        cfg = ReviewConfig(min_severity_to_fail=fail)  # type: ignore[arg-type]
        return GateResult(
            conclusion=conclusion,  # type: ignore[arg-type]
            severity_counts=counts or {"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=cfg,
            degraded=degraded,
        )

    def test_verdict_title_success(self) -> None:
        assert verdict_title(self._gate()) == "✅ Pass — no findings"

    def test_verdict_title_neutral_with_findings(self) -> None:
        gate = self._gate(conclusion="neutral", counts={"error": 1, "warning": 0, "info": 0})
        assert verdict_title(gate) == "⚠️ Findings — not blocking"

    def test_verdict_title_degraded_neutral(self) -> None:
        gate = self._gate(conclusion="neutral", degraded=True)
        assert verdict_title(gate) == "⚠️ Structured findings unavailable — not blocking"

    def test_verdict_title_failure(self) -> None:
        gate = self._gate(conclusion="failure")
        assert verdict_title(gate) == "❌ Fail — findings at or above fail threshold"

    def test_severity_counts_line(self) -> None:
        gate = self._gate(
            counts={"error": 2, "warning": 3, "info": 1},
        )
        assert severity_counts_line(gate) == "2 error · 3 warning · 1 info"

    def test_thresholds_line_fail_off(self) -> None:
        gate = self._gate()
        assert thresholds_line(gate) == "Thresholds: comment ≥ warning · fail: off"

    def test_thresholds_line_fail_set(self) -> None:
        gate = self._gate(fail="error")
        assert thresholds_line(gate) == "Thresholds: comment ≥ warning · fail ≥ error"
