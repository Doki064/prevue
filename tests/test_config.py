"""RED contract tests for single-read .github/prevue.yml config loader (WKFL-03)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prevue.config import (
    FallbackConfig,
    PrevueConfig,
    SkillsConfig,
    SkipConfig,
    load_config,
    resolve_consumer_config_path,
)
from prevue.engines.registry import DEFAULT_ENGINE
from prevue.gate import ReviewConfig

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_absent_file_all_defaults(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PREVUE_ENGINE", raising=False)
    missing = tmp_path / ".github" / "prevue.yml"
    cfg = load_config(str(missing))
    assert isinstance(cfg, PrevueConfig)
    assert cfg.review == ReviewConfig()
    assert cfg.skip == SkipConfig()
    assert cfg.fallback == FallbackConfig()
    assert cfg.skills == SkillsConfig()
    assert cfg.engine == DEFAULT_ENGINE
    assert cfg.ruleset.label_rules  # built-in defaults present

    err = capsys.readouterr().err
    assert "no config file" in err
    assert "fallback.enabled=true" in err


def test_review_section_read(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text("review:\n  min_severity_to_fail: error\n  max_inline_comments: 3\n")
    cfg = load_config(str(path))
    assert cfg.review.min_severity_to_fail == "error"
    assert cfg.review.max_inline_comments == 3
    assert cfg.review.min_severity_to_comment == "warning"


def test_skip_section_read(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text(
        "skip:\n"
        "  review_bots:\n"
        "    - dependabot[bot]\n"
        "  skip_labels:\n"
        "    - no-review\n"
        "  skip_title_patterns:\n"
        "    - '^WIP:'\n"
    )
    cfg = load_config(str(path))
    assert cfg.skip.review_bots == ["dependabot[bot]"]
    assert cfg.skip.skip_labels == ["no-review"]
    assert cfg.skip.skip_title_patterns == ["^WIP:"]


def test_fallback_section_read(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text(
        "classification:\n  fallback:\n    enabled: false\n    model: gemini-2.0-flash\n"
    )
    cfg = load_config(str(path))
    assert cfg.fallback.enabled is False
    assert cfg.fallback.model == "gemini-2.0-flash"


def test_engine_section_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PREVUE_ENGINE", raising=False)
    path = tmp_path / "prevue.yml"
    path.write_text("engine:\n  name: claude-code-cli\n")
    cfg = load_config(str(path))
    assert cfg.engine == "claude-code-cli"


def test_extra_forbid_typo_fails(tmp_path: Path) -> None:
    skip_typo = tmp_path / "skip_typo.yml"
    skip_typo.write_text("skip:\n  typo_key: true\n")
    with pytest.raises(ValidationError):
        load_config(str(skip_typo))

    fallback_typo = tmp_path / "fallback_typo.yml"
    fallback_typo.write_text("classification:\n  fallback:\n    typo_key: true\n")
    with pytest.raises(ValidationError):
        load_config(str(fallback_typo))


def test_invalid_skip_title_pattern_fails(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text("skip:\n  skip_title_patterns:\n    - '[unclosed'\n")
    with pytest.raises(ValidationError):
        load_config(str(path))


def test_resolve_consumer_config_path_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "consumer"
    root.mkdir()
    with pytest.raises(ValueError, match="must not contain"):
        resolve_consumer_config_path("../secret.yml", consumer_root=str(root))


def test_resolve_consumer_config_path_under_consumer_root(tmp_path: Path) -> None:
    root = tmp_path / "consumer"
    config_dir = root / ".github"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "prevue.yml"
    config_file.write_text("review:\n  max_inline_comments: 5\n")

    resolved = resolve_consumer_config_path(".github/prevue.yml", consumer_root=str(root))
    assert resolved == config_file.resolve()
    cfg = load_config(str(resolved))
    assert cfg.review.max_inline_comments == 5


def test_consumer_rules_applied(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text("labels:\n  custom:\n    - '**/*.xyz'\n")
    cfg = load_config(str(path))
    assert "custom" in cfg.ruleset.label_rules
    assert cfg.ruleset.label_rules["custom"] == ["**/*.xyz"]


def test_skills_section_read(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text(
        "skills:\n"
        "  exclude:\n"
        "    - security/committed-secrets.md\n"
        "  max_skill_bytes: 32768\n"
        "  max_total_consumer_bytes: 131072\n"
        "  max_consumer_skills: 25\n"
    )
    cfg = load_config(str(path))
    assert cfg.skills.exclude == ["security/committed-secrets.md"]
    assert cfg.skills.max_skill_bytes == 32768
    assert cfg.skills.max_total_consumer_bytes == 131072
    assert cfg.skills.max_consumer_skills == 25


def test_review_output_reserve_above_max_input_fails(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text("review:\n  max_input_tokens: 5000\n  output_reserve_tokens: 8000\n")
    with pytest.raises(ValidationError, match="output_reserve_tokens"):
        load_config(str(path))


def test_resolve_absolute_consumer_config_path_requires_checkout_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "prevue.yml"
    config_file.write_text("review:\n  max_inline_comments: 5\n")
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)
    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    # This invariant covers the non-Actions branch (local/library use); Actions has its
    # own fail-closed sentinel path covered by test_resolve_config_no_workspace_fallback.
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="requires PREVUE_CONSUMER_ROOT or GITHUB_WORKSPACE"):
        resolve_consumer_config_path(str(config_file), consumer_root=None)


def test_resolve_absolute_consumer_config_path_under_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    config_dir = workspace / ".github"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "prevue.yml"
    config_file.write_text("review:\n  max_inline_comments: 2\n")

    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)
    # GITHUB_WORKSPACE fallback only applies outside Actions (SKIL-04 base-ref guard).
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    resolved = resolve_consumer_config_path(str(config_file), consumer_root=None)
    assert resolved == config_file.resolve()


def test_resolve_config_no_workspace_fallback_in_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """SKIL-04: inside Actions without PREVUE_CONSUMER_ROOT, both absolute and relative
    config paths fail closed to a sentinel so load_config() uses framework defaults —
    never reading a PR-head prevue.yml from GITHUB_WORKSPACE or cwd."""
    from prevue.config import NO_CONSUMER_CONFIG_SENTINEL

    workspace = tmp_path / "workspace"
    config_dir = workspace / ".github"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "prevue.yml"
    config_file.write_text("review:\n  max_inline_comments: 2\n")

    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)

    # Absolute path: returns sentinel, not the consumer file.
    resolved_abs = resolve_consumer_config_path(str(config_file), consumer_root=None)
    assert resolved_abs == Path(NO_CONSUMER_CONFIG_SENTINEL)

    # Default relative path: also returns sentinel (the cwd footgun is closed).
    resolved_rel = resolve_consumer_config_path(".github/prevue.yml", consumer_root=None)
    assert resolved_rel == Path(NO_CONSUMER_CONFIG_SENTINEL)

    # Sentinel does not exist → load_config falls back to framework defaults.
    assert not resolved_rel.is_file()
    cfg = load_config(str(resolved_rel))
    assert cfg.review == ReviewConfig()

    assert "consumer config ignored" in capsys.readouterr().err


def test_skills_extra_forbid_typo_fails(tmp_path: Path) -> None:
    path = tmp_path / "prevue.yml"
    path.write_text("skills:\n  bad_key: true\n")
    with pytest.raises(ValidationError):
        load_config(str(path))


def test_dogfood_prevue_yml_fails_on_error_only() -> None:
    """Repo dogfood config blocks merge on errors; warnings are informational."""
    path = REPO_ROOT / ".github" / "prevue.yml"
    if not path.is_file():
        pytest.skip("dogfood prevue.yml not present")
    cfg = load_config(str(path))
    assert cfg.review.min_severity_to_fail == "error"


# --- New multi-call/run caps tests (D-09, ENGN-05/06/07) ---
# Flat-field decision: caps live directly on ReviewConfig rather than a nested multicall:
# sub-model — parity with existing review knobs, extra="forbid" preserved without a nested
# validator. (RESEARCH Open Question 2: lean flat for v1.)


def test_review_cap_all_new_fields_round_trip(tmp_path: Path) -> None:
    """All five new caps parse from prevue.yml review: block with exact values."""
    path = tmp_path / "prevue.yml"
    path.write_text(
        "review:\n"
        "  max_review_calls: 3\n"
        "  review_concurrency: 2\n"
        "  max_tokens_per_call: 60000\n"
        "  max_total_run_tokens: 200000\n"
        "  guardrail_skills:\n"
        "    - security/committed-secrets.md\n"
    )
    cfg = load_config(str(path))
    assert cfg.review.max_review_calls == 3
    assert cfg.review.review_concurrency == 2
    assert cfg.review.max_tokens_per_call == 60000
    assert cfg.review.max_total_run_tokens == 200000
    assert cfg.review.guardrail_skills == ["security/committed-secrets.md"]


def test_review_cap_defaults_when_no_review_block(tmp_path: Path) -> None:
    """All five new caps default correctly when no review: block is present."""
    path = tmp_path / "prevue.yml"
    path.write_text("ignore:\n  - '**/*.lock'\n")
    cfg = load_config(str(path))
    assert cfg.review.max_review_calls == 1
    assert cfg.review.review_concurrency == 1
    assert cfg.review.max_tokens_per_call == 120000
    assert cfg.review.max_total_run_tokens == 500000
    assert cfg.review.guardrail_skills == []


def test_review_cap_invalid_max_review_calls_raises_via_load_config(tmp_path: Path) -> None:
    """Invalid cap value (ge=1 violated) raises ValidationError through the public loader."""
    path = tmp_path / "prevue.yml"
    path.write_text("review:\n  max_review_calls: 0\n")
    with pytest.raises(ValidationError):
        load_config(str(path))


def test_review_cap_per_call_above_run_ceiling_raises_via_load_config(tmp_path: Path) -> None:
    """Incoherent per-call > run-ceiling raises through load_config (coherence validator)."""
    path = tmp_path / "prevue.yml"
    path.write_text("review:\n  max_tokens_per_call: 300000\n  max_total_run_tokens: 100000\n")
    with pytest.raises(ValidationError, match="max_tokens_per_call"):
        load_config(str(path))
