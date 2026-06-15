"""Skill pydantic model — fail-closed frontmatter validation (D-12)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillSource = Literal["builtin", "consumer"]


class Skill(BaseModel):
    """One review skill parsed from SKILL.md-style frontmatter + body."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_to: list[str] = Field(alias="applies-to", min_length=1)
    bundle: str = ""
    filename: str = ""
    body: str = ""
    source: SkillSource = "builtin"
