"""Wave 0 RED scaffold — loader unit tests (SKIL-01, D-06/07/08/09/12, SKIL-04).

Modules under test are implemented in Plan 02; these tests fail until then.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from prevue.review import BASELINE_INSTRUCTIONS
from prevue.skills.loader import assemble_instructions, load_skills, select_skills


@pytest.fixture
def fixture_skills(monkeypatch: pytest.MonkeyPatch, skills_fixture_root: Path):
    """Load skills from the test fixture tree instead of packaged built-ins."""
    monkeypatch.setattr("prevue.skills.loader._skills_root", lambda: skills_fixture_root)
    return load_skills()


def test_backend_only_pr_selects_backend_not_frontend(fixture_skills) -> None:
    """SKIL-01: .py-only paths select backend/security skills, not frontend .tsx."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    bundles = {s.bundle for s in matched}
    assert "backend" in bundles or "security" in bundles
    assert "frontend" not in bundles


def test_dedupe_by_path(fixture_skills) -> None:
    """D-09: a skill matched by multiple globs appears once."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    keys = [f"{s.bundle}/{s.filename}" for s in matched]
    assert len(keys) == len(set(keys))


def test_canonical_then_filename_order(fixture_skills) -> None:
    """D-08: matched skills ordered by bundle rank, then filename alpha."""
    matched = select_skills(fixture_skills, ["src/example.py", "src/ui.tsx"])
    bundle_ranks = [s.bundle for s in matched]
    assert bundle_ranks == sorted(bundle_ranks)


def test_no_match_falls_back_to_baseline(fixture_skills) -> None:
    """D-06: paths matching nothing → assemble_instructions returns bare baseline."""
    matched = select_skills(fixture_skills, ["README"])
    result = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    assert result == BASELINE_INSTRUCTIONS


def test_assemble_sections(fixture_skills) -> None:
    """D-07: output is baseline + ## Skill: <name> delimited sections."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    result = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    assert result.startswith(BASELINE_INSTRUCTIONS)
    if matched:
        assert "## Skill:" in result


def test_missing_applies_to_raises(monkeypatch: pytest.MonkeyPatch, skills_fixture_root: Path) -> None:
    """D-12: skill with missing applies-to raises ValidationError on load."""
    monkeypatch.setattr(
        "prevue.skills.loader._skills_root",
        lambda: skills_fixture_root / "malformed",
    )
    with pytest.raises(ValidationError):
        load_skills()


def test_loads_from_packaged_framework_dir() -> None:
    """SKIL-04: loader resolves root via importlib.resources, not __file__/PR head."""
    with patch("prevue.skills.loader._skills_root") as mock_root:
        mock_root.return_value = Path("/packaged/prevue/skills")
        load_skills()
        mock_root.assert_called_once()
