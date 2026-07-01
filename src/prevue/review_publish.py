"""Sticky + inline + check-run + machine-output publish sequence (T-05, 10-THERMOS).

Extracted from the tail of run_review(): post sticky first, then inline
comments, re-upsert sticky on downgraded placements from failed inline posts,
conclude the check run, and emit machine output (always, even on publish
failure — T-04).

Patchability note: the test suite patches ``prevue.review.upsert_sticky``,
``prevue.review.post_inline_review``, ``prevue.review.conclude_review_check``,
``prevue.review.get_repo``, ``prevue.review.emit_machine_output``, and
``prevue.review._upsert_sticky_with_retry`` directly (dozens of call sites in
tests/test_review_flow.py). Those names all still live in review.py (the real
functions are imported there, and ``_upsert_sticky_with_retry``/``_inline_key``
are defined there). This module therefore looks them up lazily through the
``prevue.review`` module object at call time — a plain
``from prevue.review import X`` import here would bind X once at import time
and silently stop responding to ``unittest.mock.patch("prevue.review.X", ...)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prevue.gate import GateResult, PlacedFinding

if TYPE_CHECKING:
    from prevue.github.client import PrContext
    from prevue.models import ReviewResult


def publish_review_result(
    pr,
    ctx: PrContext,
    diff,
    gate: GateResult,
    result: ReviewResult,
    sticky_base_kwargs: dict,
    *,
    reviewed_paths: set[str],
    regions_by_path: dict,
    owner: str,
    repo_name: str,
    skipped_files: list,
) -> None:
    """Post sticky, inline comments, check run, and machine output for a full run.

    Mirrors the pre-split tail of run_review() byte-for-byte, including the
    T-04 fix (emit machine output before raising on check-publish failure).
    """
    import prevue.review as review

    # Post sticky first so the summary appears before inline comments in the PR timeline.
    sticky, sticky_failed = review._upsert_sticky_with_retry(
        pr,
        result,
        head_sha=diff.head_sha,
        gate=gate,
        **sticky_base_kwargs,
    )

    failed_inline_keys = review.post_inline_review(
        pr,
        gate,
        in_scope_paths=reviewed_paths,
        regions_by_path=regions_by_path,
        owner=owner,
        repo=repo_name,
        resolve_outdated=False,
    )
    if failed_inline_keys and gate.inline:
        downgraded = [
            PlacedFinding(
                finding=placed.finding,
                placement="summary-only"
                if placed.placement == "inline"
                and review._inline_key(placed.finding) in failed_inline_keys
                else placed.placement,
            )
            for placed in gate.placed
        ]
        gate = GateResult(
            conclusion=gate.conclusion,
            severity_counts=gate.severity_counts,
            placed=downgraded,
            inline=[
                finding
                for finding in gate.inline
                if review._inline_key(finding) not in failed_inline_keys
            ],
            config=gate.config,
            degraded=gate.degraded,
            dropped_findings=gate.dropped_findings,
            partial=gate.partial,
        )
        # Re-upsert to reflect the downgraded placements caused by inline post failures.
        sticky, sticky_failed = review._upsert_sticky_with_retry(
            pr,
            result,
            head_sha=diff.head_sha,
            gate=gate,
            **sticky_base_kwargs,
        )
    check_published = review.conclude_review_check(
        review.get_repo(ctx),
        diff.head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
        sticky_failed=sticky_failed,
        skipped_count=len(skipped_files),
    )
    # T-04 (10-THERMOS quick task): emit machine output BEFORE the publish-failure
    # raise so the real result/tokens/findings are always emitted, even when the
    # check-run publish itself fails — the RuntimeError below still propagates
    # afterward so callers still see (and exit non-zero on) the publish failure.
    review.emit_machine_output(result, gate.conclusion)
    if not check_published:
        raise RuntimeError("Failed to publish review check run")
