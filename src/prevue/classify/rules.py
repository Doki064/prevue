"""Load built-in classification rules from packaged YAML (CLSF-03)."""

from __future__ import annotations

import importlib.resources

import yaml

from prevue.classify.models import RuleSet


def load_default_rules() -> dict:
    """Read default_rules.yml via importlib.resources — never __file__ (A2)."""
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


def load_ruleset(consumer_path: str | None = None) -> RuleSet:
    """Load built-in rules into a validated RuleSet (fail-closed, D-09)."""
    # Plan 03: D-05/D-07 consumer additive merge via consumer_path
    _ = consumer_path
    raw = load_default_rules()
    return RuleSet.model_validate(
        {
            "ignore_globs": raw["ignore"],
            "label_rules": raw["labels"],
            "routing_map": raw["routing"],
        }
    )
