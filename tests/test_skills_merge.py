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


def test_exclude_typo_warns(skills_fixture_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A skills.exclude key that matches no loaded skill warns on stderr AND is disclosed
    in the skipped/sticky list (not silent, not log-only)."""
    cfg = SkillsConfig(exclude=["security/committed-secret.md"])  # typo: missing 's'
    _skills, skipped = load_skills(
        consumer_skills_root=_consumer_root(),
        builtin_skills_root=skills_fixture_root,
        skills_config=cfg,
        return_skipped=True,
    )
    err = capsys.readouterr().err
    assert "matched no loaded skill" in err
    assert "committed-secret.md" in err
    assert any("committed-secret.md" in e and "exclude key" in e for e in skipped)


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


def test_oversized_skipped_before_full_read(
    skills_fixture_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-skill cap is enforced on file size before the body is read into memory."""
    consumer = tmp_path / "consumer" / "security"
    consumer.mkdir(parents=True)
    big = consumer / "huge.md"
    big.write_text(
        "---\nname: Huge\ndescription: big\napplies-to:\n  - '**/*'\n---\n" + "z" * 80_000
    )

    # read_text must never be called on a file rejected by the st_size precheck.
    real_read_text = Path.read_text

    def _guard_read_text(self: Path, *a, **kw):
        if self.name == "huge.md":
            raise AssertionError("oversized file read into memory despite st_size precheck")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", _guard_read_text)

    cfg = SkillsConfig(max_skill_bytes=65536)
    skills, skipped = load_skills(
        consumer_skills_root=tmp_path / "consumer",
        builtin_skills_root=skills_fixture_root,
        skills_config=cfg,
        return_skipped=True,
    )
    assert any("security/huge.md" in e and "max_skill_bytes" in e for e in skipped)
    assert all(s.filename != "huge.md" for s in skills)


def test_symlinked_skill_escaping_root_disclosed(skills_fixture_root: Path, tmp_path: Path) -> None:
    """A consumer skill file symlinked outside the root is skipped AND disclosed."""
    secret = tmp_path / "outside-secret.md"
    secret.write_text("---\nname: Evil\ndescription: x\napplies-to:\n  - '**/*'\n---\npwn\n")

    consumer = tmp_path / "consumer" / "security"
    consumer.mkdir(parents=True)
    link = consumer / "escape.md"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    skills, skipped = load_skills(
        consumer_skills_root=tmp_path / "consumer",
        builtin_skills_root=skills_fixture_root,
        return_skipped=True,
    )
    assert all(s.filename != "escape.md" for s in skills)
    assert any("escape.md" in e and "symlink guard" in e for e in skipped)
