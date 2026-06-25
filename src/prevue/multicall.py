"""Multi-call split, execute, and merge (ENGN-05/06/07, D-05/06/07/08)."""

from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from prevue.engines.errors import AuthError, EngineFailure
from prevue.fingerprint import fingerprint
from prevue.gate import SEVERITY_RANK
from prevue.models import ChangedFile, ReviewRequest, ReviewResult

if TYPE_CHECKING:
    from prevue.engines.base import EngineAdapter
    from prevue.gate import ReviewConfig


@dataclasses.dataclass
class CallGroup:
    """Files and bundle labels for one engine.review() call."""

    files: list[ChangedFile]
    bundles: set[str]


def split_into_calls(
    files: list[ChangedFile],
    bundles: set[str],
    file_bundle: dict[str, str],
    cfg: ReviewConfig,
    *,
    instruction_overhead_tokens: int = 0,
) -> list[CallGroup]:
    """Partition files into call groups by bundle, import graph, and token budget."""
    if not files:
        return []

    if cfg.max_review_calls == 1:
        return [
            CallGroup(
                files=list(files),
                bundles=set(bundles) or {file_bundle.get(f.path, "general") for f in files},
            )
        ]

    bundle_groups: dict[str, list[ChangedFile]] = {}
    for f in files:
        label = file_bundle.get(f.path, "general")
        bundle_groups.setdefault(label, []).append(f)

    groups: list[tuple[set[str], list[ChangedFile]]] = [
        ({label}, group_files) for label, group_files in bundle_groups.items()
    ]

    try:
        from prevue.importscan import referenced_paths as _referenced_paths

        known_paths = {f.path for f in files}
        parent: dict[str, str] = {f.path: f.path for f in files}

        def _find(x: str) -> str:
            root = x
            while parent[root] != root:
                root = parent[root]
            while parent[x] != root:
                parent[x], x = root, parent[x]
            return root

        def _union(a: str, b: str) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

        for f in files:
            refs = _referenced_paths(f.path, f.patch)
            for target_path in refs:
                if target_path in known_paths:
                    _union(f.path, target_path)

        root_to_files: dict[str, list[ChangedFile]] = {}
        for f in files:
            root_to_files.setdefault(_find(f.path), []).append(f)

        groups = [
            (
                {file_bundle.get(f.path, "general") for f in gfiles},
                gfiles,
            )
            for gfiles in root_to_files.values()
        ]

    except Exception:  # noqa: BLE001
        pass

    try:
        from prevue.engines.prompt import estimate_file_prompt_tokens as _est_file

        def _group_tokens(gfiles: list[ChangedFile]) -> int:
            return sum(_est_file(f) for f in gfiles)
    except (ImportError, AttributeError):

        def _group_tokens(gfiles: list[ChangedFile]) -> int:  # type: ignore[misc]
            return len(gfiles) * 1000

    max_tpc = cfg.max_tokens_per_call - max(0, instruction_overhead_tokens)
    if cfg.max_tokens_per_call > 0:
        max_tpc = max(1, max_tpc)
    merged: list[tuple[set[str], list[ChangedFile]]] = []
    for bset, gfiles in groups:
        placed = False
        for mbset, mfiles in merged:
            combined_tokens = _group_tokens(mfiles) + _group_tokens(gfiles)
            if combined_tokens <= max_tpc:
                mbset.update(bset)
                mfiles.extend(gfiles)
                placed = True
                break
        if not placed:
            merged.append((set(bset), list(gfiles)))
    groups = merged if merged else groups

    def _split_by_budget(
        bset: set[str], gfiles: list[ChangedFile]
    ) -> list[tuple[set[str], list[ChangedFile]]]:
        if _group_tokens(gfiles) <= max_tpc or len(gfiles) <= 1:
            return [(bset, gfiles)]
        out: list[tuple[set[str], list[ChangedFile]]] = []
        current: list[ChangedFile] = []
        current_tokens = 0
        for f in gfiles:
            ftokens = _group_tokens([f])
            if current and current_tokens + ftokens > max_tpc:
                out.append((set(bset), current))
                current = []
                current_tokens = 0
            current.append(f)
            current_tokens += ftokens
        if current:
            out.append((set(bset), current))
        return out

    if max_tpc > 0:
        split_groups: list[tuple[set[str], list[ChangedFile]]] = []
        for bset, gfiles in groups:
            split_groups.extend(_split_by_budget(bset, gfiles))
        groups = split_groups

    # When natural group count exceeds max_review_calls, merge the tail into the last
    # slot without re-checking max_tokens_per_call — intentional (WR-03). Non-final
    # calls still honor the per-call budget; only the final merged slot may exceed it.
    # review.py byte-guard / D-10 whole-run overflow backstops the oversized final call.
    max_calls = cfg.max_review_calls
    if len(groups) > max_calls:
        head = groups[: max_calls - 1]
        tail = groups[max_calls - 1 :]
        merged_bset: set[str] = set()
        merged_files: list[ChangedFile] = []
        for bset, gfiles in tail:
            merged_bset.update(bset)
            merged_files.extend(gfiles)
        groups = head + [(merged_bset, merged_files)]

    return [CallGroup(files=gfiles, bundles=bset) for bset, gfiles in groups if gfiles]


def execute_calls(
    requests: list[ReviewRequest],
    engine: EngineAdapter,
    *,
    concurrency: int = 1,
) -> tuple[list[ReviewResult], int, list[int]]:
    """Run review requests; fail-soft on EngineFailure (AuthError re-raised)."""
    indexed: list[tuple[int, ReviewResult]] = []
    failures = 0
    failed_indices: list[int] = []

    def _tag(idx: int, res: ReviewResult) -> ReviewResult:
        res.engine_meta = {**res.engine_meta, "call_index": idx}
        return res

    if concurrency <= 1:
        for idx, req in enumerate(requests):
            try:
                indexed.append((idx, _tag(idx, engine.review(req))))
            except AuthError:
                raise
            except EngineFailure:
                failures += 1
                failed_indices.append(idx)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_map = {pool.submit(engine.review, req): idx for idx, req in enumerate(requests)}
            try:
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        indexed.append((idx, _tag(idx, future.result())))
                    except AuthError:
                        for pending in future_map:
                            pending.cancel()
                        raise
                    except EngineFailure:
                        failures += 1
                        failed_indices.append(idx)
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

    indexed.sort(key=lambda item: item[0])
    return [res for _, res in indexed], failures, failed_indices


def merge_findings(results: list[ReviewResult]) -> list:
    """Deduplicate findings by (fingerprint, line, side); higher severity wins.

    Equal severity: prefer suggestion, then longer body, then lexicographically
    smaller body (WR-06).
    """
    from prevue.models import Finding  # local import to avoid circular

    best: dict[tuple[str, int, str], Finding] = {}
    order: list[tuple[str, int, str]] = []

    def _merge_priority(finding) -> tuple:
        rank = SEVERITY_RANK.get(finding.severity, 999)
        has_suggestion = 0 if finding.suggestion else 1
        return (rank, has_suggestion, -len(finding.body or ""), finding.body or "")

    for result in results:
        for finding in result.findings:
            key = (fingerprint(finding.path, finding.title), finding.line, finding.side)
            if key not in best:
                order.append(key)
                best[key] = finding
            elif _merge_priority(finding) < _merge_priority(best[key]):
                best[key] = finding

    return [best[key] for key in order]
