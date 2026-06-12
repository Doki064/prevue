"""Tests for route — 1:1 default bundle mapping with consumer override (D-06)."""

from __future__ import annotations

import pytest

from prevue.classify.router import route


def test_route_one_to_one_default() -> None:
    assert route(["frontend"], {}) == ["frontend"]


def test_route_consumer_override_wins() -> None:
    assert route(["frontend"], {"frontend": "fe-custom"}) == ["fe-custom"]


@pytest.mark.parametrize(
    ("labels", "routing_map", "expected"),
    [
        (["frontend", "backend"], {}, ["frontend", "backend"]),
        (["infra"], {"infra": "terraform-bundle"}, ["terraform-bundle"]),
        (
            ["frontend", "backend"],
            {"frontend": "fe-custom"},
            ["fe-custom", "backend"],
        ),
    ],
)
def test_route_cases(
    labels: list[str],
    routing_map: dict[str, str],
    expected: list[str],
) -> None:
    assert route(labels, routing_map) == expected
