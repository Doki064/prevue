"""Skill/risk-weighted whole-file token packing (DIFF-03, D-17/18)."""

from __future__ import annotations

from collections.abc import Callable

from pathspec import GitIgnoreSpec

from prevue.classify.models import CANONICAL_LABEL_ORDER, canonical_index
from prevue.engines.prompt import estimate_file_prompt_tokens, estimate_prompt_overhead_tokens
from prevue.models import ChangedFile
from prevue.skills.models import Skill

WeightFn = Callable[[ChangedFile], object]


def make_file_weight(
    label_rules: dict[str, list[str]],
    skills: list[Skill] | None = None,
) -> WeightFn:
    """Score files by label_rules + loaded skill applies-to globs (D-18)."""
    specs = {label: GitIgnoreSpec.from_lines(globs) for label, globs in label_rules.items()}
    skill_specs = [GitIgnoreSpec.from_lines(s.applies_to) for s in (skills or [])]
    # Strictly worse than any matched label. A non-canonical custom label resolves
    # to canonical_index == len(CANONICAL_LABEL_ORDER), so the fallback must sit one
    # past that to keep matched custom rules ahead of truly unmatched files (WR-04).
    fallback_priority = len(CANONICAL_LABEL_ORDER) + 1

    def weight(f: ChangedFile) -> tuple[int, int, int, str]:
        # Files covered by at least one skill come first (0) vs uncovered (1).
        skill_match = 0 if any(sp.match_file(f.path) for sp in skill_specs) else 1
        best = fallback_priority
        for label, spec in specs.items():
            res = spec.check_file(f.path)
            if res.include:
                best = min(best, canonical_index(label))
        churn = -(f.additions + f.deletions)
        return (skill_match, best, churn, f.path)

    return weight


def pack_files(
    files: list[ChangedFile],
    *,
    weight: WeightFn,
    budget_tokens: int,
) -> tuple[list[ChangedFile], list[ChangedFile]]:
    """Greedy whole-file pack — never split a file mid-diff (D-17)."""
    ranked = sorted(files, key=weight)
    packed: list[ChangedFile] = []
    skipped: list[ChangedFile] = []
    used = 0
    for f in ranked:
        cost = estimate_file_prompt_tokens(f)
        if used + cost <= budget_tokens:
            packed.append(f)
            used += cost
        else:
            skipped.append(f)
    return packed, skipped


def trim_packed_files(
    packed: list[ChangedFile],
    *,
    instructions: str,
    budget_tokens: int,
    weight: WeightFn,
) -> tuple[list[ChangedFile], list[ChangedFile]]:
    """Drop lowest-priority packed files when matched skills inflate prompt overhead."""
    overhead = estimate_prompt_overhead_tokens(instructions=instructions)
    diff_budget = max(0, budget_tokens - overhead)
    kept: list[ChangedFile] = []
    dropped: list[ChangedFile] = []
    used = 0
    for f in sorted(packed, key=weight):
        cost = estimate_file_prompt_tokens(f)
        if used + cost <= diff_budget:
            kept.append(f)
            used += cost
        else:
            dropped.append(f)
    return kept, dropped


def readmit_files(
    packed: list[ChangedFile],
    skipped: list[ChangedFile],
    *,
    instructions: str,
    available_tokens: int,
    weight: WeightFn,
) -> tuple[list[ChangedFile], list[ChangedFile]]:
    """Re-admit skipped files using actual instruction overhead (second pass after trim)."""
    overhead = estimate_prompt_overhead_tokens(instructions=instructions)
    diff_budget = max(0, available_tokens - overhead)
    used = sum(estimate_file_prompt_tokens(f) for f in packed)
    admitted: list[ChangedFile] = []
    still_skipped: list[ChangedFile] = []
    for f in sorted(skipped, key=weight):
        cost = estimate_file_prompt_tokens(f)
        if used + cost <= diff_budget:
            admitted.append(f)
            used += cost
        else:
            still_skipped.append(f)
    if not admitted:
        return packed, skipped
    return sorted(packed + admitted, key=weight), still_skipped
