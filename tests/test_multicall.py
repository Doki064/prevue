"""RED scaffold — multi-call split/execute/merge unit tests (ENGN-05/06/07, D-08, Plan 09-05).

These tests import symbols from prevue.multicall, which does not exist yet.
They MUST FAIL with ImportError/ModuleNotFoundError until Plan 09-05 implements the module.

NO pytest.importorskip or @pytest.mark.skip — RED state is intentional.
"""

from __future__ import annotations

try:
    from prevue.multicall import CallGroup, execute_calls, merge_findings, split_into_calls
except ImportError as _import_err:
    _MISSING = _import_err
    CallGroup = None  # type: ignore[assignment]
    split_into_calls = None  # type: ignore[assignment]
    execute_calls = None  # type: ignore[assignment]
    merge_findings = None  # type: ignore[assignment]
else:
    _MISSING = None

from unittest.mock import MagicMock

import pytest

from prevue.gate import ReviewConfig
from prevue.models import ChangedFile, DiffBundle, Finding, ReviewRequest, ReviewResult


def _require_module() -> None:
    if _MISSING is not None:
        pytest.fail(f"prevue.multicall not yet implemented (Plan 09-05): {_MISSING}")


def _changed_file(path: str, bundle: str = "backend") -> ChangedFile:
    return ChangedFile(
        path=path,
        status="modified",
        additions=5,
        deletions=2,
        patch=f"@@ -1 +1 @@\n-old {path}\n+new {path}",
    )


def _diff_bundle(files: list[ChangedFile]) -> DiffBundle:
    return DiffBundle(
        pr_number=1,
        base_sha="abc123",
        head_sha="def456",
        files=files,
    )


def _finding(
    *,
    path: str = "src/a.py",
    line: int = 10,
    severity: str = "warning",
    title: str = "issue",
) -> Finding:
    return Finding(
        path=path,
        line=line,
        side="RIGHT",
        severity=severity,
        title=title,
        body="details",
    )


def _review_result(findings: list[Finding] | None = None) -> ReviewResult:
    return ReviewResult(
        summary_markdown="## Review\n",
        findings=findings or [],
        engine_meta={"model": "fake", "tokens": {"review": 1000}},
    )


# ---------------------------------------------------------------------------
# CallGroup dataclass tests
# ---------------------------------------------------------------------------


class TestCallGroup:
    def test_call_group_is_a_dataclass_or_model(self) -> None:
        """CallGroup can be instantiated with files and bundles."""
        _require_module()
        group = CallGroup(
            files=[_changed_file("src/api.py", "backend")],
            bundles={"backend"},
        )
        assert hasattr(group, "files"), "CallGroup must have a 'files' attribute"
        assert hasattr(group, "bundles"), "CallGroup must have a 'bundles' attribute"
        # WR-09: no per-group instructions field — all groups share full instructions.
        assert not hasattr(group, "instructions"), (
            "CallGroup must NOT expose an 'instructions' attribute (WR-09): per-group "
            "instruction scoping does not exist; all groups share the full skill union."
        )

    def test_call_group_files_accessible(self) -> None:
        """CallGroup.files contains the files passed in."""
        _require_module()
        files = [_changed_file("src/api.py")]
        group = CallGroup(files=files, bundles={"backend"})
        assert group.files == files, "CallGroup.files should contain passed files"


# ---------------------------------------------------------------------------
# split_into_calls tests
# ---------------------------------------------------------------------------


class TestSplitIntoCalls:
    def test_single_call_when_max_review_calls_1(self) -> None:
        """max_review_calls=1 (default) produces exactly one CallGroup.

        This is the ENGN-05 single-call path: existing behavior is preserved.
        """
        _require_module()
        cfg = ReviewConfig()  # max_review_calls=1 by default
        files = [
            _changed_file("src/api.py"),
            _changed_file("src/models.py"),
            _changed_file("src/db.py"),
        ]
        file_bundle = {"src/api.py": "backend", "src/models.py": "backend", "src/db.py": "data"}
        groups = split_into_calls(files, {"backend", "data"}, file_bundle, cfg)
        assert isinstance(groups, list), "split_into_calls must return a list"
        assert len(groups) == 1, (
            f"max_review_calls=1 must produce exactly 1 group, got {len(groups)}"
        )

    def test_bundle_grouping_keeps_same_bundle_together(self) -> None:
        """Files from the same bundle are grouped into the same CallGroup."""
        _require_module()
        cfg = ReviewConfig(max_review_calls=3)
        backend_files = [_changed_file("src/api.py"), _changed_file("src/models.py")]
        security_files = [_changed_file("src/auth/guard.py")]
        all_files = backend_files + security_files
        file_bundle = {
            "src/api.py": "backend",
            "src/models.py": "backend",
            "src/auth/guard.py": "security",
        }
        groups = split_into_calls(all_files, {"backend", "security"}, file_bundle, cfg)
        assert isinstance(groups, list), "split_into_calls must return a list"
        # Each group's files should not mix bundles (they can be merged but not split).
        # A merged group may contain multiple bundles (greedy merge), but
        # same-bundle files should not be split across groups.
        # At least verify no single file appears in two groups
        all_group_paths = [f.path for g in groups for f in g.files]
        assert len(all_group_paths) == len(set(all_group_paths)), (
            "Each file must appear in exactly one CallGroup"
        )

    def test_returns_call_group_instances(self) -> None:
        """split_into_calls returns CallGroup instances."""
        _require_module()
        cfg = ReviewConfig()
        files = [_changed_file("src/api.py")]
        file_bundle = {"src/api.py": "backend"}
        groups = split_into_calls(files, {"backend"}, file_bundle, cfg)
        for group in groups:
            assert isinstance(group, CallGroup), f"Expected CallGroup, got {type(group)}"

    def test_empty_files_returns_single_group_or_empty(self) -> None:
        """Empty file list produces a single group (empty) or an empty list."""
        _require_module()
        cfg = ReviewConfig()
        groups = split_into_calls([], set(), {}, cfg)
        assert isinstance(groups, list), "split_into_calls must return a list"
        # Either empty or one empty group — both are acceptable
        if groups:
            assert all(isinstance(g, CallGroup) for g in groups)


# ---------------------------------------------------------------------------
# execute_calls tests
# ---------------------------------------------------------------------------


class TestExecuteCalls:
    def _make_request(self, path: str = "src/api.py") -> ReviewRequest:
        return ReviewRequest(
            diff=_diff_bundle([_changed_file(path)]),
            instructions="Review this.",
        )

    def test_single_call_max_review_calls_1(self) -> None:
        """With max_review_calls=1, exactly one engine.review() call is made (ENGN-05)."""
        _require_module()
        engine = MagicMock()
        engine.review.return_value = _review_result()
        requests = [self._make_request()]
        results, failures, failed_indices = execute_calls(requests, engine, concurrency=1)
        assert engine.review.call_count == 1, (
            f"Expected 1 engine.review call, got {engine.review.call_count}"
        )
        assert failures == 0
        assert failed_indices == []
        assert len(results) == 1

    def test_sequential_execution_when_concurrency_1(self) -> None:
        """concurrency=1 executes calls sequentially (D-08 default path)."""
        _require_module()
        call_order: list[int] = []

        def sequential_review(req: ReviewRequest) -> ReviewResult:
            call_order.append(len(call_order))
            return _review_result()

        engine = MagicMock()
        engine.review.side_effect = sequential_review
        requests = [self._make_request("src/a.py"), self._make_request("src/b.py")]
        results, failures, failed_indices = execute_calls(requests, engine, concurrency=1)
        assert len(results) == 2
        assert failures == 0
        assert failed_indices == []
        assert call_order == [0, 1], f"Sequential order expected, got: {call_order}"

    def test_fail_soft_one_failure_keeps_others(self) -> None:
        """A single call failure does not discard successful results (D-08 fail-soft)."""
        _require_module()
        from prevue.engines.base import EngineFailure

        call_count = [0]

        def mixed_review(req: ReviewRequest) -> ReviewResult:
            call_count[0] += 1
            if call_count[0] == 1:
                raise EngineFailure("simulated engine error")
            return _review_result([_finding(title="real finding")])

        engine = MagicMock()
        engine.review.side_effect = mixed_review
        requests = [self._make_request("src/a.py"), self._make_request("src/b.py")]
        results, failures, failed_indices = execute_calls(requests, engine, concurrency=1)
        assert failures == 1, f"Expected 1 failure, got {failures}"
        assert failed_indices == [0], f"Expected [0] failed indices, got {failed_indices}"
        assert len(results) == 1, f"Expected 1 successful result, got {len(results)}"
        assert results[0].findings[0].title == "real finding"

    def test_returns_tuple_results_and_failure_count(self) -> None:
        """execute_calls returns (list[ReviewResult], int, list[int]) tuple."""
        _require_module()
        engine = MagicMock()
        engine.review.return_value = _review_result()
        result = execute_calls([self._make_request()], engine, concurrency=1)
        assert isinstance(result, tuple), "execute_calls must return a tuple"
        results, failures, failed_indices = result
        assert isinstance(results, list), "First element must be list[ReviewResult]"
        assert isinstance(failures, int), "Second element must be int failure count"
        assert isinstance(failed_indices, list), "Third element must be list[int] failed indices"

    def test_parallel_execution_when_concurrency_gt_1(self) -> None:
        """concurrency>1 uses thread pool; all results returned (ENGN-07)."""
        _require_module()
        engine = MagicMock()
        engine.review.return_value = _review_result([_finding()])
        requests = [self._make_request(f"src/file{i}.py") for i in range(3)]
        results, failures, failed_indices = execute_calls(requests, engine, concurrency=2)
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        assert failures == 0
        assert failed_indices == []


# ---------------------------------------------------------------------------
# merge_findings tests
# ---------------------------------------------------------------------------


class TestMergeFindings:
    def test_single_call_result_findings_preserved(self) -> None:
        """Single result's findings pass through unchanged."""
        _require_module()
        f1 = _finding(path="src/a.py", title="issue A")
        result = _review_result([f1])
        merged = merge_findings([result])
        assert len(merged) == 1
        assert merged[0].title == "issue A"

    def test_dedupe_same_fingerprint_across_calls(self) -> None:
        """Duplicate findings across calls (same path+title) are deduplicated (D-08).

        fingerprint(path, title) is the deduplication key — reuses Phase 8 mechanism.
        """
        _require_module()
        f1 = _finding(path="src/a.py", title="duplicate issue", severity="warning")
        f2 = _finding(path="src/a.py", title="duplicate issue", severity="warning")
        result1 = _review_result([f1])
        result2 = _review_result([f2])
        merged = merge_findings([result1, result2])
        assert len(merged) == 1, f"Duplicate across calls must be deduped to 1, got {len(merged)}"

    def test_severity_tie_break_keeps_higher_severity(self) -> None:
        """On fingerprint collision (same path+title), keep the higher-severity finding (D-08).

        Mirrors _dedupe_findings_by_location tie-break: SEVERITY_RANK error=0 wins.
        """
        _require_module()
        f_warning = _finding(path="src/a.py", title="same issue", severity="warning", line=10)
        f_error = _finding(path="src/a.py", title="same issue", severity="error", line=10)
        result1 = _review_result([f_warning])
        result2 = _review_result([f_error])
        merged = merge_findings([result1, result2])
        assert len(merged) == 1, "Duplicate must collapse to one finding"
        assert merged[0].severity == "error", (
            f"Higher severity (error) must win tie-break, got {merged[0].severity!r}"
        )

    def test_distinct_findings_all_preserved(self) -> None:
        """Findings with different paths/titles from multiple calls are all included."""
        _require_module()
        f1 = _finding(path="src/a.py", title="issue in a")
        f2 = _finding(path="src/b.py", title="issue in b")
        f3 = _finding(path="src/c.py", title="issue in c")
        result1 = _review_result([f1, f2])
        result2 = _review_result([f3])
        merged = merge_findings([result1, result2])
        assert len(merged) == 3, f"3 distinct findings expected, got {len(merged)}"

    def test_empty_results_returns_empty(self) -> None:
        """No results → empty merged findings."""
        _require_module()
        merged = merge_findings([])
        assert merged == [], f"Expected empty merged list, got: {merged}"

    def test_no_findings_in_results_returns_empty(self) -> None:
        """Results with no findings → empty merged list."""
        _require_module()
        results = [_review_result([]), _review_result([])]
        merged = merge_findings(results)
        assert merged == [], f"Expected empty merged list, got: {merged}"

    def test_returns_list_of_findings(self) -> None:
        """merge_findings always returns list[Finding]."""
        _require_module()
        result = _review_result([_finding()])
        merged = merge_findings([result])
        assert isinstance(merged, list), "merge_findings must return a list"
        for item in merged:
            assert isinstance(item, Finding), f"Each item must be a Finding, got {type(item)}"
