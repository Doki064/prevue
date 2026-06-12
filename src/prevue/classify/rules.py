"""Load built-in classification rules from packaged YAML (CLSF-03)."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import yaml

from prevue.classify.models import RuleSet


def load_default_rules() -> dict:
    """Read default_rules.yml via importlib.resources — never __file__ (A2)."""
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


def merge_rules(builtin: dict, consumer: dict | None) -> dict:
    """Merge optional consumer prevue.yml over built-ins (D-05/D-06/D-07).

    - ignore: append consumer globs to built-in noise filters (D-07 additive)
    - labels: override-by-label — consumer list replaces that label's globs (D-05)
    - routing: consumer entries override built-in 1:1 defaults (D-06)
    """
    if consumer is None:
        return builtin

    merged = {
        "ignore": list(builtin.get("ignore", [])),
        "labels": {k: list(v) for k, v in builtin.get("labels", {}).items()},
        "routing": dict(builtin.get("routing", {})),
    }

    if "ignore" in consumer:
        merged["ignore"] = merged["ignore"] + list(consumer["ignore"])

    if "labels" in consumer:
        for label, globs in consumer["labels"].items():
            merged["labels"][label] = list(globs)

    if "routing" in consumer:
        merged["routing"].update(consumer["routing"])

    return merged


def load_ruleset(consumer_path: str | None = None) -> RuleSet:
    """Load built-in rules into a validated RuleSet (fail-closed, D-09).

    When consumer_path is provided and the file exists, yaml.safe_load merges
    consumer config over built-ins. Phase 5 wires trusted-base-ref fetch;
    Phase 2 reads from a local path / test fixtures only (never PR head).
    """
    raw = load_default_rules()
    if consumer_path is not None:
        path = Path(consumer_path)
        if path.is_file():
            consumer = yaml.safe_load(path.read_text(encoding="utf-8"))
            if consumer is not None:
                if not isinstance(consumer, dict):
                    RuleSet.model_validate(
                        {
                            "ignore_globs": [],
                            "label_rules": {},
                            "routing_map": consumer,
                        }
                    )
                # Fail-closed on malformed consumer fields before merge (T-02-08)
                RuleSet.model_validate(
                    {
                        "ignore_globs": consumer.get("ignore", []),
                        "label_rules": consumer.get("labels", {}),
                        "routing_map": consumer.get("routing", {}),
                    }
                )
                raw = merge_rules(raw, consumer)

    return RuleSet.model_validate(
        {
            "ignore_globs": raw["ignore"],
            "label_rules": raw["labels"],
            "routing_map": raw["routing"],
        }
    )
