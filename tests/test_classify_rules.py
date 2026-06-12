"""Tests for classification rule loading and RuleSet validation (CLSF-03)."""

from __future__ import annotations

import importlib.resources

import pytest
import yaml
from pydantic import ValidationError

from prevue.classify.models import RuleSet
from prevue.classify.rules import load_default_rules, load_ruleset

EXPECTED_LABELS = frozenset({"frontend", "backend", "infra", "data", "security"})


def test_load_default_rules_has_required_keys() -> None:
    raw = load_default_rules()
    assert "ignore" in raw
    assert "labels" in raw
    assert "routing" in raw
    assert isinstance(raw["ignore"], list)
    assert isinstance(raw["labels"], dict)
    assert isinstance(raw["routing"], dict)


def test_load_ruleset_has_all_five_label_categories() -> None:
    ruleset = load_ruleset()
    assert EXPECTED_LABELS.issubset(ruleset.label_rules.keys())
    assert len(ruleset.ignore_globs) > 0
    assert isinstance(ruleset.routing_map, dict)


@pytest.mark.parametrize(
    "bad_data",
    [
        {"ignore_globs": "not-a-list", "label_rules": {}, "routing_map": {}},
        {"ignore_globs": [], "label_rules": "not-a-dict", "routing_map": {}},
        {"ignore_globs": [], "label_rules": {}, "routing_map": "not-a-dict"},
    ],
)
def test_ruleset_rejects_malformed_mapping(bad_data: dict) -> None:
    with pytest.raises(ValidationError):
        RuleSet.model_validate(bad_data)


@pytest.mark.parametrize(
    "bad_data",
    [
        {"ignore": "not-a-list", "labels": {}, "routing": {}},
        {"ignore": [], "labels": "not-a-dict", "routing": {}},
    ],
)
def test_load_ruleset_rejects_malformed_yaml_shape(bad_data: dict) -> None:
    with pytest.raises(ValidationError):
        RuleSet.model_validate(
            {
                "ignore_globs": bad_data.get("ignore", []),
                "label_rules": bad_data.get("labels", {}),
                "routing_map": bad_data.get("routing", {}),
            }
        )


def test_packaged_default_rules_yml_resolves_via_importlib_resources() -> None:
    """Wheel-packaging trap A2 — default_rules.yml must resolve after build."""
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    assert resource.is_file()
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    ruleset = RuleSet.model_validate(
        {
            "ignore_globs": raw["ignore"],
            "label_rules": raw["labels"],
            "routing_map": raw["routing"],
        }
    )
    assert EXPECTED_LABELS.issubset(ruleset.label_rules.keys())
    assert len(ruleset.ignore_globs) > 0


def test_load_ruleset_matches_packaged_resource() -> None:
    ruleset = load_ruleset()
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    assert ruleset.ignore_globs == raw["ignore"]
    assert ruleset.label_rules == raw["labels"]
    assert ruleset.routing_map == raw["routing"]
