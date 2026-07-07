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

    def classify_with_tokens(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> tuple[dict[str, str], int | None]:
        """Classify with a real-token-count companion (T-09a — 10-THERMOS).

        Default implementation delegates to ``classify()`` and reports no real
        token count (``None`` — caller estimates). Adapters that CAN report real
        usage (e.g. ``CliEngineAdapter`` for json_envelope engines) override this
        with real-token-returning behavior. Having a universal default here means
        callers (``llm_fallback._classify_batch``) never need a ``hasattr`` duck-
        typing check — every adapter has a working ``classify_with_tokens``.
        """
        labels = self.classify(paths, allowed_labels, model=model)
        return labels, None

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
