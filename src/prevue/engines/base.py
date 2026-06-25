"""Pluggable engine adapter port (ENGN-01)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from prevue.engines.errors import AuthError, EngineFailure  # re-exported for test compat
from prevue.models import ReviewRequest, ReviewResult

__all__ = ["EngineAdapter", "EngineFailure", "AuthError"]


class EngineAdapter(ABC):
    name: str

    @abstractmethod
    def review(self, req: ReviewRequest) -> ReviewResult: ...

    def classify(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        """Label-only classification for ambiguous file paths (D-11)."""
        raise NotImplementedError(f"{self.name} does not implement classify()")

    def classify_skills(
        self,
        skills: list,
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
        paths: list[str] | None = None,
        diff_excerpt: str | None = None,
    ) -> dict[str, str]:
        """Relevance arbitration over candidate skills, keyed by skill name."""
        raise NotImplementedError(f"{self.name} does not implement classify_skills()")
