"""RED scaffold — file packing tests (DIFF-03). Target implemented in Plan 07-02."""

from __future__ import annotations

from prevue.models import ChangedFile


def test_packs_whole_files_to_budget() -> None:
    from prevue.pack import pack_files

    files = [
        ChangedFile(
            path="a.py",
            status="modified",
            additions=1,
            deletions=0,
            patch="+" * 400,  # 100 tokens at bytes/4
        ),
        ChangedFile(
            path="b.py",
            status="modified",
            additions=1,
            deletions=0,
            patch="+" * 400,
        ),
        ChangedFile(
            path="c.py",
            status="modified",
            additions=1,
            deletions=0,
            patch="+" * 400,
        ),
    ]

    packed, skipped = pack_files(files, weight=lambda f: f.path, budget_tokens=250)

    assert len(packed) == 2
    assert len(skipped) == 1
    assert {f.path for f in packed} == {"a.py", "b.py"}
    assert skipped[0].path == "c.py"


def test_priority_security_first() -> None:
    from prevue.pack import pack_files

    security = ChangedFile(
        path="src/auth/login.py",
        status="modified",
        additions=5,
        deletions=0,
        patch="+" * 400,
    )
    docs = ChangedFile(
        path="docs/readme.md",
        status="modified",
        additions=5,
        deletions=0,
        patch="+" * 400,
    )

    def weight(f: ChangedFile) -> tuple[int, str]:
        if "auth" in f.path or f.path.endswith(".py"):
            return (0, f.path)
        return (1, f.path)

    packed, skipped = pack_files([docs, security], weight=weight, budget_tokens=150)

    assert len(packed) == 1
    assert packed[0].path == "src/auth/login.py"
    assert len(skipped) == 1
    assert skipped[0].path == "docs/readme.md"


def test_custom_label_outranks_unmatched() -> None:
    """WR-04: a file matching a custom (non-canonical) label packs ahead of an unmatched file."""
    from prevue.pack import make_file_weight, pack_files

    custom = ChangedFile(
        path="payments/charge.py",
        status="modified",
        additions=5,
        deletions=0,
        patch="+" * 400,
    )
    unmatched = ChangedFile(
        path="misc/notes.txt",
        status="modified",
        additions=5,
        deletions=0,
        patch="+" * 400,
    )

    weight = make_file_weight({"payments": ["payments/**"]})
    # Budget fits exactly one of the two equally sized files.
    packed, skipped = pack_files([unmatched, custom], weight=weight, budget_tokens=150)

    assert [f.path for f in packed] == ["payments/charge.py"]
    assert [f.path for f in skipped] == ["misc/notes.txt"]
