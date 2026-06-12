"""Load, select, and assemble review skills from the packaged framework tree."""

from __future__ import annotations

import importlib.resources

import frontmatter
from pathspec import GitIgnoreSpec

from prevue.classify.models import canonical_index
from prevue.skills.models import Skill


def _skills_root():
    """Packaged skills root — never __file__ or PR head (SKIL-04)."""
    return importlib.resources.files("prevue.skills")


def load_skills() -> list[Skill]:
    """Load every .md skill under the packaged prevue.skills bundle dirs."""
    root = _skills_root()
    skills: list[Skill] = []
    for bundle_entry in root.iterdir():
        if bundle_entry.name.startswith("_") or bundle_entry.name == "__pycache__":
            continue
        if not bundle_entry.is_dir():
            continue
        bundle = bundle_entry.name
        for entry in bundle_entry.iterdir():
            if not entry.name.endswith(".md"):
                continue
            post = frontmatter.loads(entry.read_text(encoding="utf-8"))
            skill = Skill.model_validate(post.metadata)
            skill.bundle = bundle
            skill.filename = entry.name
            skill.body = post.content
            skills.append(skill)
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
    sections = [baseline] + [
        f"## Skill: {skill.name}\n{skill.body.strip()}" for skill in skills
    ]
    return "\n\n".join(sections)
