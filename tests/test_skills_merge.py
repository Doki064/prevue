"""RED scaffold — consumer skill merge tests (SKIL-03). Target implemented in Plan 07-04."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prevue.classify.models import canonical_index
from prevue.config import SkillsConfig
from prevue.skills.loader import load_skills, select_skills


def _consumer_root() -> Path:
    return Path(__file__).parent / "fixtures" / "skills" / "consumer"


def test_override_replaces_builtin(skills_fixture_root: Path) -> None:
    skills = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
    )
    override = next(
        s for s in skills if s.filename == "committed-secrets.md" and s.bundle == "security"
    )
    assert "CONSUMER OVERRIDE" in override.body
    assert override.source == "consumer"


def test_custom_adds_alongside(skills_fixture_root: Path) -> None:
    skills = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
    )
    filenames = {s.filename for s in skills if s.bundle == "security"}
    assert "consumer-only-rule.md" in filenames
    assert "committed-secrets.md" in filenames
    consumer_only = next(s for s in skills if s.filename == "consumer-only-rule.md")
    assert consumer_only.source == "consumer"
    assert any(
        s.source == "builtin" for s in skills if s.bundle == "security" and s != consumer_only
    )


def test_noncanonical_bundle_sorts_last(skills_fixture_root: Path) -> None:
    skills = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
    )
    matched = select_skills(skills, ["src/payments/charge.py"])
    bundles = [s.bundle for s in matched]
    if "payments" in bundles:
        payments_idx = bundles.index("payments")
        for canonical in ("security", "frontend", "backend", "data", "infra"):
            if canonical in bundles:
                assert canonical_index(canonical) <= canonical_index("payments")
                assert bundles.index(canonical) < payments_idx


def test_malformed_consumer_fails(skills_fixture_root: Path) -> None:
    malformed_root = Path(__file__).parent / "fixtures" / "skills" / "consumer-malformed"
    with pytest.raises(ValidationError):
        load_skills(
            consumer_skills_root=malformed_root,
            builtin_skills_root=skills_fixture_root,
        )


def test_exclude_removes_builtin(skills_fixture_root: Path) -> None:
    cfg = SkillsConfig(exclude=["security/committed-secrets.md"])
    skills = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
        skills_config=cfg,
    )
    keys = {f"{s.bundle}/{s.filename}" for s in skills}
    assert "security/committed-secrets.md" not in keys


def test_over_cap_skips_and_discloses(skills_fixture_root: Path) -> None:
    cfg = SkillsConfig(max_skill_bytes=65536)
    skills, skipped = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
        skills_config=cfg,
        return_skipped=True,
    )
    keys = {f"{s.bundle}/{s.filename}" for s in skills}
    assert "security/oversized.md" not in keys
    assert any("security/oversized.md" in entry for entry in skipped)
