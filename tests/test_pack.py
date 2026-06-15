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

    packed, skipped = pack_files(files, weight=lambda f: f.path, budget_tokens=300)

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

    packed, skipped = pack_files([docs, security], weight=weight, budget_tokens=200)

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
    packed, skipped = pack_files([unmatched, custom], weight=weight, budget_tokens=200)

    assert [f.path for f in packed] == ["payments/charge.py"]
    assert [f.path for f in skipped] == ["misc/notes.txt"]


def test_readmit_then_trim_when_instructions_expand() -> None:
    """readmit_files + trim_packed_files sequence: second trim corrects for instruction growth."""
    from prevue.engines.prompt import estimate_file_prompt_tokens, estimate_prompt_overhead_tokens
    from prevue.pack import readmit_files, trim_packed_files

    small = ChangedFile(path="a.py", status="modified", additions=1, deletions=0, patch="+" * 200)
    medium = ChangedFile(path="b.py", status="modified", additions=1, deletions=0, patch="+" * 200)

    short_instr = "x"  # 1 token
    small_cost = estimate_file_prompt_tokens(small)
    medium_cost = estimate_file_prompt_tokens(medium)
    overhead_short = estimate_prompt_overhead_tokens(instructions=short_instr)

    # available_tokens fits exactly both files under short instructions
    available_tokens = overhead_short + small_cost + medium_cost

    new_packed, still_skipped = readmit_files(
        [small],
        [medium],
        instructions=short_instr,
        available_tokens=available_tokens,
        weight=lambda f: f.path,
    )
    assert medium in new_packed, "medium re-admitted when budget exactly fits both"
    assert not still_skipped

    # big_instr adds 1 more token (8 chars → 2 tokens vs 1 char → 1 token), shrinking
    # diff_budget by 1 so small_cost + medium_cost no longer fits.
    big_instr = "x" * 8  # 8//4=2 tokens vs 1//4→1 token: overhead grows by 1
    kept, dropped = trim_packed_files(
        new_packed,
        instructions=big_instr,
        budget_tokens=available_tokens,
        weight=lambda f: f.path,
    )
    assert medium in dropped, "medium dropped when instruction inflation shrinks diff budget by 1"
    assert small in kept
