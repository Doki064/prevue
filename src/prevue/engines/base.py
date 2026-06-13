"""Pluggable engine adapter port (ENGN-01)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from prevue.models import ReviewRequest, ReviewResult


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
