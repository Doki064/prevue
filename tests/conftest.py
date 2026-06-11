"""Shared pytest fixtures for Prevue tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
import responses

from prevue.engines.base import EngineAdapter
from prevue.models import ReviewRequest, ReviewResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
def event_json() -> dict:
    """Load sample GITHUB_EVENT_PATH pull_request payload."""
    with (FIXTURES_DIR / "event_pull_request.json").open() as f:
        return json.load(f)
