"""Tests for classification rule loading and RuleSet validation (CLSF-03)."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from prevue.classify.models import RuleSet
from prevue.classify.rules import load_default_rules, load_ruleset, merge_rules

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


def _minimal_builtin() -> dict:
    return {
        "ignore": ["**/*.lock"],
        "labels": {"frontend": ["**/*.tsx"], "backend": ["**/*.py"]},
        "routing": {"frontend": "frontend"},
    }


def test_merge_rules_none_consumer_passthrough() -> None:
    """Optional consumer config — absent → built-ins unchanged."""
    builtin = _minimal_builtin()
    assert merge_rules(builtin, None) == builtin


def test_merge_additive_ignore_globs() -> None:
    """D-07: consumer ignore globs append to built-in noise filters."""
    builtin = _minimal_builtin()
    merged = merge_rules(builtin, {"ignore": ["**/*.generated.ts"]})
    assert merged["ignore"] == ["**/*.lock", "**/*.generated.ts"]


def test_merge_label_override_by_label() -> None:
    """D-05: consumer label entry replaces that label's built-in globs."""
    builtin = _minimal_builtin()
    merged = merge_rules(builtin, {"labels": {"frontend": ["**/*.svelte"]}})
    assert merged["labels"]["frontend"] == ["**/*.svelte"]
    assert merged["labels"]["backend"] == ["**/*.py"]


def test_merge_routing_consumer_override() -> None:
    """D-06: consumer routing entries override built-in 1:1 defaults."""
    builtin = _minimal_builtin()
    merged = merge_rules(builtin, {"routing": {"frontend": "fe-custom"}})
    assert merged["routing"]["frontend"] == "fe-custom"


def test_load_ruleset_none_yields_builtins_only() -> None:
    """Absent consumer_path → packaged defaults unchanged."""
    ruleset = load_ruleset(None)
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    assert ruleset.ignore_globs == raw["ignore"]
    assert ruleset.label_rules == raw["labels"]


def test_load_ruleset_merges_consumer_fixture(tmp_path: Path) -> None:
    consumer = tmp_path / "prevue.yml"
    consumer.write_text(
        yaml.dump(
            {
                "ignore": ["**/*.generated.ts"],
                "labels": {"frontend": ["**/*.svelte"]},
                "routing": {"frontend": "fe-custom"},
            }
        ),
        encoding="utf-8",
    )
    ruleset = load_ruleset(str(consumer))
    assert "**/*.generated.ts" in ruleset.ignore_globs
    assert "**/*.lock" in ruleset.ignore_globs
    assert ruleset.label_rules["frontend"] == ["**/*.svelte"]
    assert ruleset.routing_map["frontend"] == "fe-custom"


def test_load_ruleset_malformed_consumer_fail_closed(tmp_path: Path) -> None:
    consumer = tmp_path / "prevue.yml"
    consumer.write_text("ignore: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_ruleset(str(consumer))
