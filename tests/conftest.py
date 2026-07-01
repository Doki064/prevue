"""Shared pytest fixtures for Prevue tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
import responses

from prevue.engines.base import EngineAdapter
from prevue.models import ReviewRequest, ReviewResult
from prevue.skills.models import Skill
from tests.engine_helpers import (
    VALID_TOKEN,
    make_sample_request,
    stdout_with_fence,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Back-compat aliases for plans referencing conftest symbol names.
_stdout_with_fence = stdout_with_fence


@pytest.fixture
def sample_request() -> ReviewRequest:
    return make_sample_request()


@pytest.fixture
def set_all_engine_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-test-key")
    monkeypatch.setenv("CURSOR_API_KEY", "cur_test_key")


class FakeEngine(EngineAdapter):
    name = "fake"

    def review(self, req: ReviewRequest) -> ReviewResult:
        return ReviewResult(
            summary_markdown="## Canned review\n\nNo issues found.",
            findings=[],
            engine_meta={"model": "fake", "duration_s": 0.1},
        )


@pytest.fixture
def responses_activated() -> Generator[None, None, None]:
    """Activate responses mock for GitHub REST API calls."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def fake_engine() -> FakeEngine:
    """Stub engine adapter returning a canned ReviewResult."""
    return FakeEngine()


@pytest.fixture
def skills_fixture_root() -> Path:
    """Path to the skills fixture tree for loader unit tests."""
    return Path(__file__).parent / "fixtures" / "skills"


@pytest.fixture
def event_json() -> dict:
    """Load sample GITHUB_EVENT_PATH pull_request payload."""
    with (FIXTURES_DIR / "event_pull_request.json").open() as f:
        return json.load(f)


@pytest.fixture
def gap_shape_skill() -> Skill:
    """Gap-shape skill: bundle=security, applies_to=['**/auth/**'], body has GAP-DEMO-SKILL-LOADED.

    This fixture represents the gap-demo-sandbox gap shape (D-12): a skill whose applies-to
    does NOT match a path like 'src/pages/Checkout.jsx', but whose bundle IS routed by
    classification — so bundle-scoped selection must load it even when glob matching misses.
    Unit tests that need the gap shape without disk I/O use this fixture directly.
    """
    import frontmatter

    from prevue.skills.models import Skill

    gap_fixture = FIXTURES_DIR / "skills" / "consumer" / "security" / "gap-demo-auth-guard.md"
    post = frontmatter.loads(gap_fixture.read_text(encoding="utf-8"))
    skill = Skill.model_validate(post.metadata)
    skill.bundle = "security"
    skill.filename = "gap-demo-auth-guard.md"
    skill.body = post.content
    skill.source = "consumer"
    return skill
