"""Pluggable engine adapter port (ENGN-01)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from prevue.models import ReviewRequest, ReviewResult


class EngineAdapter(ABC):
    name: str

    @abstractmethod
    def review(self, req: ReviewRequest) -> ReviewResult: ...
