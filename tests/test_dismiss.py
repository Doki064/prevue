"""Dismiss suppress-list model + parse/render (D-14/D-15)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prevue.dismiss import (
    DISMISS_BLOCK_CLOSE,
    DISMISS_BLOCK_OPEN,
    DismissEntry,
    active_suppressed_fingerprints,
    parse_dismiss_block,
    render_dismiss_block,
)
from prevue.fingerprint import fingerprint
from prevue.gate import ReviewConfig
from prevue.models import Finding


def _sample_entry(*, fp: str = "a" * 16) -> DismissEntry:
    return DismissEntry(
        fingerprint=fp,
        path="src/example.py",
        region=(10, 20),
        side="RIGHT",
        severity="warning",
        actor="alice",
        timestamp="2026-06-16T00:00:00Z",
        reason="false positive",
    )


def test_dismiss_entry_round_trip() -> None:
    entries = [_sample_entry(fp="0123456789abcdef"), _sample_entry(fp="fedcba9876543210")]
    rendered = render_dismiss_block(entries)
    assert parse_dismiss_block(rendered) == entries


def test_dismiss_entry_empty_list_round_trip() -> None:
    rendered = render_dismiss_block([])
    assert parse_dismiss_block(rendered) == []


def test_parse_dismiss_block_missing_block_returns_empty() -> None:
    assert parse_dismiss_block("## Prevue Review\nno dismiss here") == []


def test_parse_dismiss_block_malformed_json_returns_empty() -> None:
    body = f"{DISMISS_BLOCK_OPEN}\n```json\n{{not json\n```\n{DISMISS_BLOCK_CLOSE}"
    assert parse_dismiss_block(body) == []


def test_parse_dismiss_block_extra_field_returns_empty() -> None:
    import json

    payload = _sample_entry().model_dump()
    payload["evil"] = True
    body = (
        f"### Dismissed findings\n{DISMISS_BLOCK_OPEN}\n"
        f"```json\n{json.dumps([payload])}\n```\n{DISMISS_BLOCK_CLOSE}"
    )
    assert parse_dismiss_block(body) == []


def test_dismiss_entry_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        DismissEntry.model_validate(
            {
                **_sample_entry().model_dump(),
                "extra": "nope",
            }
        )


def test_review_config_max_dismissals_default() -> None:
    assert ReviewConfig().max_dismissals == 50


def test_review_config_max_dismissals_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        ReviewConfig(max_dismissals=-1)


def test_review_config_max_dismissals_rejects_extra_key() -> None:
    with pytest.raises(ValidationError):
        ReviewConfig(max_dismissals=50, bogus=1)


def test_active_suppress_empty_entries() -> None:
    assert active_suppressed_fingerprints([], [], {}) == set()


def test_active_suppress_untouched_no_reemission() -> None:
    entry = _sample_entry(fp="0123456789abcdef")
    active = active_suppressed_fingerprints(
        [entry],
        [],
        {entry.path: [(20, 25)]},
    )
    assert active == {entry.fingerprint}


def test_active_suppress_guard2_region_changed() -> None:
    entry = _sample_entry(fp="0123456789abcdef")
    active = active_suppressed_fingerprints(
        [entry],
        [],
        {entry.path: [(8, 12)]},
    )
    assert active == set()


def test_active_suppress_guard3_escalation() -> None:
    title = "Same issue"
    entry = _sample_entry(fp="0123456789abcdef").model_copy(
        update={"severity": "warning", "path": "src/example.py", "region": (10, 20)}
    )
    current = Finding(
        path=entry.path,
        line=15,
        side="RIGHT",
        severity="error",
        title=title,
        body="still bad",
    )
    fp = fingerprint(current.path, current.title)
    entry = entry.model_copy(update={"fingerprint": fp})
    active = active_suppressed_fingerprints(
        [entry],
        [current],
        {entry.path: [(20, 25)]},
    )
    assert active == set()


def test_active_suppress_equal_severity_stays_active() -> None:
    title = "Same issue"
    entry = _sample_entry(fp="0123456789abcdef").model_copy(
        update={"severity": "warning", "path": "src/example.py", "region": (10, 20)}
    )
    current = Finding(
        path=entry.path,
        line=15,
        side="RIGHT",
        severity="warning",
        title=title,
        body="still bad",
    )
    fp = fingerprint(current.path, current.title)
    entry = entry.model_copy(update={"fingerprint": fp})
    active = active_suppressed_fingerprints(
        [entry],
        [current],
        {entry.path: [(20, 25)]},
    )
    assert active == {fp}
