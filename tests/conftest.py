"""Shared pytest fixtures for Prevue tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
import responses

from prevue.engines.base import EngineAdapter
from prevue.models import ReviewRequest, ReviewResult
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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
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
