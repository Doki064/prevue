"""Skill/risk-weighted whole-file token packing (DIFF-03, D-17/18)."""

from __future__ import annotations

from collections.abc import Callable

from pathspec import GitIgnoreSpec

from prevue.classify.models import CANONICAL_LABEL_ORDER, canonical_index
from prevue.engines.prompt import estimate_file_prompt_tokens, estimate_prompt_overhead_tokens
from prevue.models import ChangedFile

WeightFn = Callable[[ChangedFile], object]


def make_file_weight(label_rules: dict[str, list[str]]) -> WeightFn:
    """Score files by re-running label_rules GitIgnoreSpec (A4 — no classify() change)."""
    specs = {label: GitIgnoreSpec.from_lines(globs) for label, globs in label_rules.items()}
    # Strictly worse than any matched label. A non-canonical custom label resolves
    # to canonical_index == len(CANONICAL_LABEL_ORDER), so the fallback must sit one
    # past that to keep matched custom rules ahead of truly unmatched files (WR-04).
    fallback_priority = len(CANONICAL_LABEL_ORDER) + 1

    def weight(f: ChangedFile) -> tuple[int, int, str]:
        best = fallback_priority
        for label, spec in specs.items():
            res = spec.check_file(f.path)
            if res.include:
                best = min(best, canonical_index(label))
        churn = -(f.additions + f.deletions)
        return (best, churn, f.path)

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
