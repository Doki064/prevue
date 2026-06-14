"""Load, select, and assemble review skills from the packaged framework tree."""

from __future__ import annotations

import importlib.resources
from collections.abc import Iterator
from pathlib import Path

import frontmatter
from pathspec import GitIgnoreSpec

from prevue.classify.models import canonical_index
from prevue.config import SkillsConfig
from prevue.skills.models import Skill


def _skills_root():
    """Packaged skills root — never __file__ or PR head (SKIL-04)."""
    return importlib.resources.files("prevue.skills")


def _iter_skill_files(root: Path | object, bundle: str) -> Iterator[tuple[str, str, str]]:
    # Sort by name so byte-cap enforcement drops a deterministic set across runs
    # and machines (Path.iterdir() order is filesystem-dependent) (WR-04).
    for entry in sorted(root.iterdir(), key=lambda p: p.name):  # type: ignore[union-attr]
        if not entry.name.endswith(".md"):
            continue
        yield bundle, entry.name, entry.read_text(encoding="utf-8")


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
        for bundle_name, filename, text in _iter_skill_files(bundle_entry, bundle):
            key = f"{bundle_name}/{filename}"
            post = frontmatter.loads(text)
            # Measure the loaded body (frontmatter stripped) — that is what reaches
            # the prompt via assemble_instructions — not the whole file (WR-03).
            content_bytes = len(post.content.encode("utf-8"))
            if is_consumer:
                if content_bytes > skills_config.max_skill_bytes:
                    skipped.append(f"{key} (exceeds max_skill_bytes)")
                    continue
                if count >= skills_config.max_consumer_skills:
                    skipped.append(f"{key} (exceeds max_consumer_skills)")
                    continue
                if total_bytes + content_bytes > skills_config.max_total_consumer_bytes:
                    skipped.append(f"{key} (exceeds max_total_consumer_bytes)")
                    continue
                total_bytes += content_bytes
                count += 1
            skill = Skill.model_validate(post.metadata)
            skill.bundle = bundle_name
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
        by_key.pop(key, None)

    skills = list(by_key.values())
    if return_skipped:
        return skills, skipped
    return skills


def select_skills(skills: list[Skill], paths: list[str]) -> list[Skill]:
    """Select skills whose applies-to globs match any changed path (D-03/D-04)."""
    matched: list[Skill] = []
    seen: set[str] = set()
    for skill in skills:
        spec = GitIgnoreSpec.from_lines(skill.applies_to)
        if not any(spec.match_file(path) for path in paths):
            continue
        key = f"{skill.bundle}/{skill.filename}"
        if key in seen:
            continue
        seen.add(key)
        matched.append(skill)
    matched.sort(key=lambda s: (canonical_index(s.bundle), s.filename))
    return matched


def assemble_instructions(baseline: str, skills: list[Skill]) -> str:
    """Join baseline preamble with matched skill sections (D-06/D-07)."""
    if not skills:
        return baseline
    sections = [baseline] + [f"## Skill: {skill.name}\n{skill.body.strip()}" for skill in skills]
    return "\n\n".join(sections)
