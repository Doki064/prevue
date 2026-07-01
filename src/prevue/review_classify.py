"""Classification post-processing + skill-selection refresh helpers (T-05, 10-THERMOS).

Extracted from review.py: the pure (no patched-I/O) pieces of the classify →
skill-select → pack pipeline. The actual ``classify()``/``llm_classify()`` calls
stay in review.py (they are patched directly as ``prevue.review.classify`` /
``prevue.review.llm_classify`` in the test suite — moving those call sites would
silently stop tests from being able to substitute fake classification results).
This module holds the label-merge bookkeeping that runs on the *result* of
those calls, plus the ``_refresh_matched``/``_skill_ratios`` pack-loop helpers
that were already free of patched-name calls.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.skills.selection import _dedup_sort, select_skills_hybrid

if TYPE_CHECKING:
    from prevue.classify.models import ClassificationResult


def apply_fallback_labels(
    result_cls: ClassificationResult,
    fallback_labels: dict[str, str],
    unmatched_pre_pack: list[str],
    classify_real_tokens: int | None,
    *,
    estimate_classify_tokens,
) -> tuple[int, dict[str, str]]:
    """Merge LLM-fallback labels into result_cls; return (classify_tokens, llm_path_labels).

    Pure post-processing of ``llm_classify``'s return value — no adapter/engine
    calls happen here. ``estimate_classify_tokens`` is passed in (rather than
    imported) so this module has no dependency on ``prevue.classify.llm_fallback``
    beyond the pure token-estimate helper the caller already imports.
    """
    classify_tokens = 0
    # Only bill classify tokens when classification actually produced usable
    # labels — a fully degraded fallback ({GENERAL_LABEL: FALLBACK_FAILED_GLOB})
    # obtained no real classification, so reporting a non-zero estimate would
    # overstate the audit-trail cost (WR-02).
    produced_real_labels = bool(fallback_labels.keys() - {GENERAL_LABEL})
    if produced_real_labels:
        # Prefer real token counts from json_envelope engines; fall back to estimate.
        classify_tokens = (
            classify_real_tokens
            if classify_real_tokens is not None
            else estimate_classify_tokens(unmatched_pre_pack)
        )

    from prevue.classify.llm_fallback import FALLBACK_FAILED_GLOB, FALLBACK_PARTIAL_GLOB

    for path_or_label, label_or_glob in fallback_labels.items():
        is_degrade_general = path_or_label == GENERAL_LABEL and label_or_glob in {
            FALLBACK_FAILED_GLOB,
            FALLBACK_PARTIAL_GLOB,
        }
        if is_degrade_general:
            result_cls.labels[GENERAL_LABEL] = label_or_glob
            continue
        if (
            isinstance(path_or_label, str)
            and isinstance(label_or_glob, str)
            and label_or_glob in CANONICAL_LABEL_ORDER
            and label_or_glob not in result_cls.labels
        ):
            result_cls.labels[label_or_glob] = path_or_label
    if (
        fallback_labels
        and GENERAL_LABEL in result_cls.labels
        and GENERAL_LABEL not in fallback_labels
        and any(label != GENERAL_LABEL for label in result_cls.labels)
    ):
        result_cls.labels.pop(GENERAL_LABEL, None)

    # Build path→label map for files classified by LLM so _file_bundle_map
    # can assign the correct routed bundle without re-running glob matching.
    llm_path_labels = {
        p: lbl
        for p, lbl in fallback_labels.items()
        if isinstance(p, str)
        and p != GENERAL_LABEL
        and isinstance(lbl, str)
        and lbl in CANONICAL_LABEL_ORDER
    }
    # Remove successfully LLM-classified paths from unmatched so sticky
    # metadata and disclosure don't report them as unresolved.
    if llm_path_labels:
        result_cls.unmatched = [p for p in result_cls.unmatched if p not in llm_path_labels]

    return classify_tokens, llm_path_labels


def skill_ratios(all_skills: list, matched: list) -> dict[str, tuple[int, int]]:
    """Per-bundle (loaded, total) skill counts for sticky Metadata disclosure."""
    loaded = Counter(s.bundle for s in matched)
    totals = Counter(s.bundle for s in all_skills)
    return {bundle: (loaded[bundle], totals[bundle]) for bundle in totals}


def refresh_matched(
    packed_files: list,
    skills: list,
    bundles: list[str],
    *,
    adapter,
    llm_skill_names: set[str] | None,
    model: str | None,
    guardrail_keys: list[str] | None = None,
) -> tuple[list, str, list]:
    """Recompute (packed_paths, diff_text, matched) after any pack change.

    Centralizes the repeated pattern:
        packed_paths = [f.path for f in packed_files]
        diff_text = "\\n".join(f.patch or "" for f in packed_files)
        matched = select_skills_hybrid(skills, paths, diff_text, bundles, ...)

    WR-01: ``guardrail_keys`` are ``bundle/filename`` skill keys that must load on
    EVERY call (the documented ``review.guardrail_skills`` security backstop). They
    are force-added to ``matched`` regardless of keyword score or routed bundle, so
    a consumer's always-on security skill is never dropped by selection. Unknown
    keys are ignored (a typo can't fabricate a skill).
    """
    packed_paths = [f.path for f in packed_files]
    diff_text = "\n".join(f.patch or "" for f in packed_files)
    matched = select_skills_hybrid(
        skills,
        packed_paths,
        diff_text,
        bundles,
        adapter=adapter,
        llm_skill_names=llm_skill_names,
        model=model,
    )
    if guardrail_keys:
        wanted = set(guardrail_keys)
        present = {f"{s.bundle}/{s.filename}" for s in matched}
        forced = [
            s
            for s in skills
            if f"{s.bundle}/{s.filename}" in wanted and f"{s.bundle}/{s.filename}" not in present
        ]
        if forced:
            # Re-run the shared dedup/sort so guardrail skills slot into the same
            # canonical (bundle, filename) ordering as keyword/escalation matches.
            matched = _dedup_sort([*matched, *forced])
    return packed_paths, diff_text, matched
