"""Wave 0 RED scaffold — loader unit tests (SKIL-01, D-06/07/08/09/12, SKIL-04).

Modules under test are implemented in Plan 02; these tests fail until then.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import frontmatter
import pytest
from pydantic import ValidationError

from prevue.classify.models import canonical_index
from prevue.review import BASELINE_INSTRUCTIONS
from prevue.skills.loader import assemble_instructions, load_skills, select_skills
from prevue.skills.models import Skill


def _load_fixture_bundle(bundle_dir: Path, bundle: str) -> list[Skill]:
    """Load skills from one bundle directory."""
    skills: list[Skill] = []
    for entry in bundle_dir.iterdir():
        if not entry.name.endswith(".md"):
            continue
        post = frontmatter.loads(entry.read_text(encoding="utf-8"))
        skill = Skill.model_validate(post.metadata)
        skill.bundle = bundle
        skill.filename = entry.name
        skill.body = post.content
        skills.append(skill)
    return skills


@pytest.fixture
def fixture_skills(skills_fixture_root: Path) -> list[Skill]:
    """Load valid fixture skills (excludes malformed/ used by D-12 test)."""
    skills: list[Skill] = []
    for bundle in ("security", "frontend", "backend"):
        skills.extend(_load_fixture_bundle(skills_fixture_root / bundle, bundle))
    return skills


def test_backend_only_pr_selects_backend_not_frontend(fixture_skills) -> None:
    """SKIL-01: .py-only paths select backend/security skills, not frontend .tsx."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    bundles = {s.bundle for s in matched}
    assert "backend" in bundles
    assert "security" in bundles
    assert "frontend" not in bundles


def test_dedupe_by_path(fixture_skills) -> None:
    """D-09: a skill matched by multiple globs appears once."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    keys = [f"{s.bundle}/{s.filename}" for s in matched]
    assert len(keys) == len(set(keys))


def test_canonical_then_filename_order(fixture_skills) -> None:
    """D-08: matched skills ordered by bundle rank, then filename alpha."""
    matched = select_skills(fixture_skills, ["src/example.py", "src/ui.tsx"])
    ordering = [(canonical_index(s.bundle), s.filename) for s in matched]
    assert ordering == sorted(ordering)


def test_no_match_falls_back_to_baseline(fixture_skills) -> None:
    """D-06: paths matching nothing → assemble_instructions returns bare baseline."""
    matched = select_skills(fixture_skills, [])
    result = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    assert result == BASELINE_INSTRUCTIONS


def test_assemble_sections(fixture_skills) -> None:
    """D-07: output is baseline + ## Skill: <name> delimited sections."""
    matched = select_skills(fixture_skills, ["src/example.py"])
    result = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    assert result.startswith(BASELINE_INSTRUCTIONS)
    if matched:
        assert "## Skill:" in result


def test_missing_applies_to_raises(skills_fixture_root: Path) -> None:
    """D-12: skill with missing applies-to raises ValidationError on load."""
    with pytest.raises(ValidationError):
        _load_fixture_bundle(skills_fixture_root / "malformed", "malformed")


def test_loads_from_packaged_framework_dir() -> None:
    """SKIL-04: loader resolves root via importlib.resources, not __file__/PR head."""
    mock_root = MagicMock()
    mock_root.iterdir.return_value = []
    with patch("prevue.skills.loader._skills_root", return_value=mock_root) as mock_fn:
        assert load_skills() == []
        mock_fn.assert_called_once()
