"""Hybrid skill selection (SKIL-01, D-02).

1. Keyword score each skill; keep ≥ KEYWORD_THRESHOLD.
2. Gap-closure: for routed bundles with no match, LLM-arbitrate below-threshold candidates.
3. Drop skills from non-routed bundles.
"""

from __future__ import annotations

import re
from collections.abc import Collection

from pathspec import GitIgnoreSpec

from prevue.classify.models import canonical_index
from prevue.engines.base import EngineAdapter
from prevue.skills.models import Skill

KEYWORD_THRESHOLD: float = 0.15  # 0.7 * content_score + 0.3 * path_score

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9]|[a-zA-Z]")


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 2)


def keyword_score(skill: Skill, paths: list[str], diff_text: str) -> float:
    """Deterministic relevance score in [0, 1] from diff content and applies-to globs."""
    skill_tokens = _tokenize(skill.name) | _tokenize(skill.description)
    diff_tokens = _tokenize(diff_text)
    if skill_tokens:
        intersection = len(skill_tokens & diff_tokens)
        union = len(skill_tokens | diff_tokens)
        content_signal = intersection / union if union else 0.0
    else:
        content_signal = 0.0

    path_signal = 0.0
    if paths and skill.applies_to:
        spec = GitIgnoreSpec.from_lines(skill.applies_to)
        if any(spec.check_file(p).include for p in paths):
            path_signal = 1.0

    return 0.7 * content_signal + 0.3 * path_signal


def _dedup_sort(skills: list[Skill]) -> list[Skill]:
    """Deduplicate by bundle/filename; sort like select_skills in loader.py."""
    seen: set[str] = set()
    unique: list[Skill] = []
    for skill in skills:
        key = f"{skill.bundle}/{skill.filename}"
        if key not in seen:
            seen.add(key)
            unique.append(skill)
    unique.sort(key=lambda s: (canonical_index(s.bundle), s.filename))
    return unique


def _supports_skill_classify(adapter: EngineAdapter) -> bool:
    """True when adapter implements classify_skills on a real subclass.

    Uses __func__ probe (not bare getattr) to avoid MagicMock false-positives (WR-10).
    When False, hybrid selection passes through without LLM escalation.
    """
    if not isinstance(adapter, EngineAdapter):
        return False
    method = getattr(type(adapter), "classify_skills", None)
    if method is None:
        return False
    return getattr(method, "__func__", method) is not EngineAdapter.classify_skills


def select_skills_hybrid(
    skills: list[Skill],
    paths: list[str],
    diff_text: str,
    bundles: Collection[str],
    *,
    adapter: EngineAdapter | None = None,
    llm_skill_names: set[str] | None = None,
    model: str | None = None,
) -> list[Skill]:
    """Select skills via keyword floor, with LLM escalation for routed below-threshold hits."""
    if not skills:
        return []

    selected: list[Skill] = []
    to_escalate: list[Skill] = []
    bundles_set = set(bundles)

    for skill in skills:
        score = keyword_score(skill, paths, diff_text)
        if score >= KEYWORD_THRESHOLD and skill.bundle in bundles_set:
            selected.append(skill)
        elif skill.bundle in bundles_set:
            to_escalate.append(skill)

    if to_escalate:
        resolved_names: set[str]
        if llm_skill_names is not None:
            resolved_names = llm_skill_names
        elif adapter is not None and _supports_skill_classify(adapter):
            from prevue.classify.llm_fallback import llm_select_skills

            _fetched = llm_select_skills(
                to_escalate, adapter, model=model, paths=paths, diff_text=diff_text
            )
            resolved_names = _fetched if _fetched is not None else {s.name for s in to_escalate}
        else:
            resolved_names = {s.name for s in to_escalate}

        for skill in to_escalate:
            if skill.name in resolved_names:
                selected.append(skill)

    return _dedup_sort(selected)
