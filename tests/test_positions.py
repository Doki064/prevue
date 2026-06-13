"""RED contract tests for diff position validity sets (OUTP-02, D-17)."""

from __future__ import annotations

from prevue.github.positions import build_valid_lines, commentable_lines

from prevue.models import ChangedFile

MODIFIED_PATCH = """\
@@ -10,3 +10,3 @@
 context line
-old line
+added line
 another context
"""

ADDED_PATCH = """\
@@ -0,0 +1,3 @@
+line one
+line two
+line three
"""

NO_NEWLINE_PATCH = """\
@@ -1,1 +1,2 @@
 unchanged
+changed
\\ No newline at end of file
"""


class TestCommentableLines:
    def test_added_lines_in_right_set(self) -> None:
        result = commentable_lines("src/foo.py", MODIFIED_PATCH)
        assert 11 in result["RIGHT"]  # added line target
        assert 10 in result["RIGHT"]  # context lines on RIGHT

    def test_context_lines_in_right_set(self) -> None:
        result = commentable_lines("src/foo.py", MODIFIED_PATCH)
        assert result["RIGHT"]  # non-empty RIGHT from context + added

    def test_removed_lines_in_left_not_right(self) -> None:
        result = commentable_lines("src/foo.py", MODIFIED_PATCH)
        assert 11 in result["LEFT"]  # removed source line
        assert 10 in result["RIGHT"] and 10 not in result["LEFT"]  # context: RIGHT only

    def test_patch_none_returns_empty_sets(self) -> None:
        result = commentable_lines("large.bin", None)
        assert result == {"RIGHT": set(), "LEFT": set()}

    def test_malformed_patch_returns_empty_no_exception(self) -> None:
        result = commentable_lines("src/foo.py", "@@ -1,1 +1,1 @@\n+broken")
        assert result == {"RIGHT": set(), "LEFT": set()}

    def test_new_file_hunk_parses_right_one_through_three(self) -> None:
        result = commentable_lines("README.md", ADDED_PATCH)
        assert result["RIGHT"] == {1, 2, 3}
        assert result["LEFT"] == set()

    def test_no_newline_marker_in_neither_set(self) -> None:
        result = commentable_lines("src/foo.py", NO_NEWLINE_PATCH)
        for side in ("RIGHT", "LEFT"):
            assert all(isinstance(n, int) for n in result[side])


class TestBuildValidLines:
    def test_maps_each_changed_file_path(self) -> None:
        files = [
            ChangedFile(
                path="src/a.py",
                status="modified",
                additions=1,
                deletions=1,
                patch=MODIFIED_PATCH,
            ),
            ChangedFile(
                path="README.md",
                status="added",
                additions=3,
                deletions=0,
                patch=ADDED_PATCH,
            ),
            ChangedFile(
                path="big.bin",
                status="modified",
                additions=0,
                deletions=0,
                patch=None,
            ),
        ]
        result = build_valid_lines(files)
        assert set(result.keys()) == {"src/a.py", "README.md", "big.bin"}
        assert result["README.md"]["RIGHT"] == {1, 2, 3}
        assert result["big.bin"] == {"RIGHT": set(), "LEFT": set()}
        assert result["src/a.py"] == commentable_lines("src/a.py", MODIFIED_PATCH)
