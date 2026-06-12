"""Skill pydantic model — fail-closed frontmatter validation (D-12)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Skill(BaseModel):
    """One review skill parsed from SKILL.md-style frontmatter + body."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_to: list[str] = Field(alias="applies-to", min_length=1)
    bundle: str = ""
    filename: str = ""
    body: str = ""
