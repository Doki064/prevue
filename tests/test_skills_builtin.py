"""Wave 0 RED scaffold — built-in skill bundle tests (SKIL-02, packaging guard).

Runs against the REAL packaged prevue.skills tree; fails until Plan 02/03 content ships.
"""

from __future__ import annotations

import importlib.resources as resources

from prevue.skills.loader import load_skills


def test_all_builtin_skills_valid() -> None:
    """SKIL-02: every built-in skill parses and validates; all five bundles present."""
    skills = load_skills()
    bundles = {s.bundle for s in skills}
    assert bundles >= {"security", "frontend", "backend", "data", "infra"}
    for skill in skills:
        assert skill.name
        assert skill.applies_to


def test_security_secrets_skill_present() -> None:
    """SKIL-02/D-11: committed-secrets skill exists with always-on **/* glob."""
    skills = load_skills()
    secrets = [
        s
        for s in skills
        if s.bundle == "security" and "secret" in s.name.lower()
    ]
    assert secrets, "expected a security skill for committed secrets"
    assert any("**/*" in s.applies_to for s in secrets)


def test_skills_packaged_and_readable() -> None:
    """Pitfall 2: at least one .md readable via importlib.resources (packaging guard)."""
    root = resources.files("prevue.skills")
    md_files = [p for p in root.rglob("*.md")]
    assert md_files, "expected packaged .md skills under prevue.skills"
    assert md_files[0].read_text(encoding="utf-8")
