"""Load, select, and assemble review skills from the packaged framework tree."""

from __future__ import annotations

import importlib.resources
import sys
from collections.abc import Iterator
from pathlib import Path

import frontmatter
from pathspec import GitIgnoreSpec

from prevue.config import SkillsConfig
from prevue.skills.models import Skill
from prevue.skills.selection import _dedup_sort


def _skills_root():
    """Packaged skills root — never __file__ or PR head (SKIL-04)."""
    return importlib.resources.files("prevue.skills")


def _iter_skill_files(root: Path | object) -> Iterator[Path]:
    # Sort by name so byte-cap enforcement drops a deterministic set across runs
    # and machines (Path.iterdir() order is filesystem-dependent) (WR-04).
    for entry in sorted(root.iterdir(), key=lambda p: p.name):  # type: ignore[union-attr]
        if not entry.name.endswith(".md"):
            continue
        yield entry


def _load_from_tree(
    root: Path | object,
    *,
    is_consumer: bool,
    skills_config: SkillsConfig,
    consumer_bytes: int,
    consumer_count: int,
    skipped: list[str],
) -> tuple[dict[str, Skill], int, int]:
    by_key: dict[str, Skill] = {}
    total_bytes = consumer_bytes
    count = consumer_count

    for bundle_entry in sorted(root.iterdir(), key=lambda p: p.name):  # type: ignore[union-attr]
        if bundle_entry.name.startswith("_") or bundle_entry.name == "__pycache__":
            continue
        if not bundle_entry.is_dir():
            continue
        bundle = bundle_entry.name
        cr = Path(root).resolve() if is_consumer else None
        for entry in _iter_skill_files(bundle_entry):
            filename = entry.name
            key = f"{bundle}/{filename}"
            if is_consumer:
                # Guard against symlinked skill files escaping the consumer root —
                # disclose (don't silently drop) so operators see the security skip.
                resolved = Path(entry).resolve()
                if cr is not None and not resolved.is_relative_to(cr):
                    skipped.append(f"{key} (escapes consumer root — symlink guard)")
                    continue
                # Enforce the per-skill cap on file size BEFORE reading the whole file
                # into memory — a huge base-branch skill must not spike runner memory.
                # st_size >= body bytes (frontmatter only adds), so passing here keeps
                # the post-parse body within the cap too.
                if entry.stat().st_size > skills_config.max_skill_bytes:
                    skipped.append(f"{key} (exceeds max_skill_bytes)")
                    continue
            post = frontmatter.loads(entry.read_text(encoding="utf-8"))
            # Measure the loaded body (frontmatter stripped) — that is what reaches
            # the prompt via assemble_instructions — not the whole file (WR-03).
            content_bytes = len(post.content.encode("utf-8"))
            if is_consumer:
                if count >= skills_config.max_consumer_skills:
                    skipped.append(f"{key} (exceeds max_consumer_skills)")
                    continue
                if total_bytes + content_bytes > skills_config.max_total_consumer_bytes:
                    skipped.append(f"{key} (exceeds max_total_consumer_bytes)")
                    continue
                total_bytes += content_bytes
                count += 1
            skill = Skill.model_validate(post.metadata)
            skill.bundle = bundle
            skill.filename = filename
            skill.body = post.content
            skill.source = "consumer" if is_consumer else "builtin"
            by_key[key] = skill
    return by_key, total_bytes, count


def load_skills(
    *,
    consumer_skills_root: Path | str | None = None,
    builtin_skills_root: Path | str | None = None,
    skills_config: SkillsConfig | None = None,
    return_skipped: bool = False,
) -> list[Skill] | tuple[list[Skill], list[str]]:
    """Load built-in skills, optionally merged with consumer overrides (SKIL-03)."""
    cfg = skills_config or SkillsConfig()
    skipped: list[str] = []
    by_key: dict[str, Skill] = {}

    builtin_root = Path(builtin_skills_root) if builtin_skills_root else _skills_root()
    builtin_loaded, _, _ = _load_from_tree(
        builtin_root,
        is_consumer=False,
        skills_config=cfg,
        consumer_bytes=0,
        consumer_count=0,
        skipped=skipped,
    )
    by_key.update(builtin_loaded)

    if consumer_skills_root is not None:
        consumer_root = Path(consumer_skills_root)
        if consumer_root.is_dir():
            consumer_loaded, _, _ = _load_from_tree(
                consumer_root,
                is_consumer=True,
                skills_config=cfg,
                consumer_bytes=0,
                consumer_count=0,
                skipped=skipped,
            )
            by_key.update(consumer_loaded)

    for key in cfg.exclude:
        if by_key.pop(key, None) is None:
            # D-05 exclude keys are exact bundle/filename; a typo silently excludes
            # nothing. Surface it both on stderr (Action log) and in the sticky
            # disclosure list so a misconfigured exclude is visible without log-diving.
            print(
                f"prevue: skills.exclude key {key!r} matched no loaded skill "
                "(exact bundle/filename expected — check for a typo).",
                file=sys.stderr,
            )
            skipped.append(f"{key} (exclude key matched no loaded skill — check for typo)")

    skills = list(by_key.values())
    if return_skipped:
        return skills, skipped
    return skills


def select_skills(skills: list[Skill], paths: list[str]) -> list[Skill]:
    """Select skills whose applies-to globs match any changed path (D-03/D-04)."""
    matched: list[Skill] = []
    for skill in skills:
        spec = GitIgnoreSpec.from_lines(skill.applies_to)
        # Use check_file().include (not match_file) to agree with pack.make_file_weight
        # and classifier.py — with negated (!) applies-to patterns the two APIs differ,
        # which would let a skill affect pack priority without being loaded (or vice versa).
        if not any(spec.check_file(path).include for path in paths):
            continue
        matched.append(skill)
    return _dedup_sort(matched)


def assemble_instructions(baseline: str, skills: list[Skill]) -> str:
    """Join baseline preamble with matched skill sections (D-06/D-07)."""
    if not skills:
        return baseline
    sections = [baseline] + [f"## Skill: {skill.name}\n{skill.body.strip()}" for skill in skills]
    return "\n\n".join(sections)
