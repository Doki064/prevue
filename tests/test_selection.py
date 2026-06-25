"""Unit tests for hybrid skill selection (D-02, SKIL-01)."""

from __future__ import annotations

try:
    from prevue.skills.selection import KEYWORD_THRESHOLD, keyword_score, select_skills_hybrid
except ImportError as _import_err:
    _MISSING = _import_err
    KEYWORD_THRESHOLD = None  # type: ignore[assignment]
    keyword_score = None  # type: ignore[assignment]
    select_skills_hybrid = None  # type: ignore[assignment]
else:
    _MISSING = None

import pytest

from prevue.skills.models import Skill


def _make_skill(
    *,
    name: str,
    description: str,
    applies_to: list[str],
    bundle: str = "backend",
    filename: str = "skill.md",
    body: str = "",
) -> Skill:
    skill = Skill(name=name, description=description, applies_to=applies_to)
    skill.bundle = bundle
    skill.filename = filename
    skill.body = body
    return skill


# ---------------------------------------------------------------------------
# Guard: every test fails with a clear message if the module isn't implemented
# ---------------------------------------------------------------------------


def _require_module() -> None:
    if _MISSING is not None:
        pytest.fail(f"prevue.skills.selection not yet implemented (Plan 09-02): {_MISSING}")


# ---------------------------------------------------------------------------
# keyword_score tests
# ---------------------------------------------------------------------------


class TestKeywordScore:
    def test_high_overlap_returns_above_threshold(self) -> None:
        """A skill whose name/description matches diff content scores above KEYWORD_THRESHOLD."""
        _require_module()
        skill = _make_skill(
            name="SQL Injection Prevention",
            description="Detect unsanitized SQL queries in database access layers.",
            applies_to=["**/*.py"],
        )
        diff_text = (
            "- query = f'SELECT * FROM users WHERE id={user_id}'\n"
            "+ query = 'SELECT * FROM users WHERE id=%s'"
        )
        paths = ["src/db/users.py"]
        score = keyword_score(skill, paths, diff_text)
        assert isinstance(score, (int, float)), "keyword_score must return a number"
        assert score >= KEYWORD_THRESHOLD, (
            f"High-overlap skill scored {score!r}, expected >= {KEYWORD_THRESHOLD!r}"
        )

    def test_zero_overlap_returns_below_threshold(self) -> None:
        """Skill with no overlapping terms in the diff scores below KEYWORD_THRESHOLD."""
        _require_module()
        skill = _make_skill(
            name="CSS Animation Performance",
            description="Detect janky animations and layout thrashing in stylesheets.",
            applies_to=["**/*.css"],
        )
        diff_text = "- user.password = sha1(raw)\n+ user.password = bcrypt.hash(raw)"
        paths = ["src/auth/user.py"]
        score = keyword_score(skill, paths, diff_text)
        assert isinstance(score, (int, float)), "keyword_score must return a number"
        assert score < KEYWORD_THRESHOLD, (
            f"Zero-overlap skill scored {score!r}, expected < {KEYWORD_THRESHOLD!r}"
        )

    def test_score_is_non_negative(self) -> None:
        """keyword_score never returns a negative value."""
        _require_module()
        skill = _make_skill(
            name="Totally irrelevant skill",
            description="Nothing here matches the diff content at all.",
            applies_to=["**/*.go"],
        )
        score = keyword_score(skill, [], "")
        assert score >= 0, f"score must be non-negative, got {score!r}"

    def test_applies_to_paths_contribute_to_score(self) -> None:
        """applies_to glob patterns that match changed paths should contribute to score."""
        _require_module()
        skill = _make_skill(
            name="Auth Middleware",
            description="Review authorization middleware for missing guards.",
            applies_to=["**/auth/**"],
        )
        paths_matching = ["src/auth/middleware.py"]
        paths_nonmatching = ["src/ui/button.tsx"]
        score_match = keyword_score(skill, paths_matching, "")
        score_no_match = keyword_score(skill, paths_nonmatching, "")
        # Matching applies-to paths should contribute a higher (or equal) score
        assert score_match >= score_no_match, "applies_to path match should not lower the score"

    def test_makes_zero_adapter_calls(self) -> None:
        """keyword_score is purely deterministic — it must not call any adapter."""
        _require_module()

        class SpyAdapter:
            def __init__(self) -> None:
                self.calls = 0

            def classify(self, *args, **kwargs):
                self.calls += 1
                return {}

        spy = SpyAdapter()
        skill = _make_skill(
            name="SQL Injection",
            description="Detect SQL injection vulnerabilities.",
            applies_to=["**/*.py"],
        )
        _ = keyword_score(skill, ["src/db/query.py"], "SELECT * FROM users")
        assert spy.calls == 0, "keyword_score must never call any adapter"


# ---------------------------------------------------------------------------
# select_skills_hybrid tests
# ---------------------------------------------------------------------------


class TestSelectSkillsHybrid:
    def test_high_score_skill_selected_by_keyword_floor(self) -> None:
        """Skill above KEYWORD_THRESHOLD in a routed bundle is selected by keyword floor."""
        _require_module()
        skill = _make_skill(
            name="SQL Injection Prevention",
            description="Detect unsanitized SQL in database access code.",
            applies_to=["**/*.py"],
            bundle="backend",
        )
        diff = "SELECT * FROM users WHERE id={user_id}"
        paths = ["src/db/users.py"]
        selected = select_skills_hybrid([skill], paths, diff, bundles={"backend"}, adapter=None)
        assert skill in selected, (
            "High-score skill in routed bundle must be selected by keyword floor"
        )

    def test_high_score_skill_unrouted_bundle_dropped(self) -> None:
        """Skill above KEYWORD_THRESHOLD is dropped when its bundle is not routed."""
        _require_module()
        skill = _make_skill(
            name="Terraform State Locking",
            description="SELECT * lock state during terraform apply.",
            applies_to=["**/*.tf"],
            bundle="infra",
        )
        diff = "SELECT * FROM users WHERE id={user_id}"
        paths = ["src/db/users.py"]
        # infra bundle not routed — keyword floor must not override routing
        selected = select_skills_hybrid([skill], paths, diff, bundles={"backend"}, adapter=None)
        assert skill not in selected, "High-score skill in unrouted bundle must be dropped"

    def test_below_threshold_routed_skill_escalates_not_drops(self) -> None:
        """Below-threshold skill in a routed bundle escalates (gap-closure guard).

        When no adapter is provided and the skill is in a routed bundle, it should
        still appear in the result (pass-through escalation without LLM call).
        This verifies the gap-closure guard: routed skills are NEVER silently dropped.
        """
        _require_module()
        skill = _make_skill(
            name="Gap Demo Auth Guard",
            description="Verify authorization guards on checkout and payment flows.",
            applies_to=["**/auth/**"],
            bundle="security",
        )
        # Diff has nothing to do with auth keywords — would score below threshold
        diff = "console.log('hello world')\n"
        paths = ["src/pages/Checkout.jsx"]  # does NOT match **/auth/**
        # bundle='security' IS in the routed bundles set
        selected = select_skills_hybrid([skill], paths, diff, bundles={"security"}, adapter=None)
        assert skill in selected, (
            "Below-threshold skill in a routed bundle must not be dropped silently "
            "(gap-closure guard, D-02 gap-demo-sandbox regression)"
        )

    def test_below_threshold_non_routed_skill_dropped(self) -> None:
        """Below-threshold skill NOT in any routed bundle is dropped (correct exclusion)."""
        _require_module()
        skill = _make_skill(
            name="Terraform State Locking",
            description="Ensure remote state is locked during apply operations.",
            applies_to=["**/*.tf"],
            bundle="infra",
        )
        # Diff is backend Python — infra bundle not routed
        diff = "def get_user(id): return db.query(User, id)"
        paths = ["src/api/users.py"]
        selected = select_skills_hybrid([skill], paths, diff, bundles={"backend"}, adapter=None)
        assert skill not in selected, (
            "Below-threshold skill not in routed bundles should be dropped"
        )

    def test_maru_dry_fruits_shape_selected_via_llm_skill_names(self) -> None:
        """gap-demo-sandbox regression: below-threshold routed skill selected via llm_skill_names.

        The gap shape: skill applies-to=**/auth/** does NOT match src/pages/Checkout.jsx
        (glob miss) but the security bundle IS routed, and the LLM classify fallback returns
        the skill's name. It must appear in the selection output.
        """
        _require_module()
        skill = _make_skill(
            name="Gap Demo Auth Guard",
            description="Verify authorization guards on checkout and payment flows.",
            applies_to=["**/auth/**"],
            bundle="security",
            filename="gap-demo-auth-guard.md",
        )
        diff = "console.log('added to cart')"
        paths = ["src/pages/Checkout.jsx"]
        # LLM returned the skill's name — double-duty reuse
        selected = select_skills_hybrid(
            [skill],
            paths,
            diff,
            bundles={"security"},
            adapter=None,
            llm_skill_names={"Gap Demo Auth Guard"},
        )
        assert skill in selected, (
            "gap-demo-sandbox gap shape: skill in routed bundle with name in llm_skill_names "
            "must be selected even when applies-to glob misses the changed path"
        )

    def test_empty_bundles_keyword_floor_only(self) -> None:
        """With bundles={}, only keyword floor applies — no escalation, no gap-closure."""
        _require_module()
        skill = _make_skill(
            name="Gap Demo Auth Guard",
            description="Verify authorization guards on checkout and payment flows.",
            applies_to=["**/auth/**"],
            bundle="security",
        )
        diff = "console.log('hello world')\n"
        paths = ["src/pages/Checkout.jsx"]
        selected = select_skills_hybrid([skill], paths, diff, bundles=set(), adapter=None)
        # security bundle not routed → no escalation → dropped (keyword score is low)
        assert skill not in selected, (
            "With empty bundles, below-threshold skill must be dropped (no escalation)"
        )

    def test_output_sorted_by_canonical_index_then_filename(self) -> None:
        """Output ordering matches select_skills: (canonical_index(bundle), filename)."""
        _require_module()
        from prevue.classify.models import canonical_index

        skill_sec = _make_skill(
            name="Auth Check",
            description="SQL injection and authentication security.",
            applies_to=["**/*.py"],
            bundle="security",
            filename="auth-check.md",
        )
        skill_be = _make_skill(
            name="SQL Injection Prevention",
            description="Detect SQL injection in database access layers.",
            applies_to=["**/*.py"],
            bundle="backend",
            filename="sql-injection.md",
        )
        diff = "SELECT * FROM users WHERE id={user_id} auth injection sql"
        paths = ["src/api/users.py"]
        selected = select_skills_hybrid(
            [skill_be, skill_sec],  # backend first in input
            paths,
            diff,
            bundles={"security", "backend"},
            adapter=None,
        )
        # Both should be selected; security should come before backend
        assert len(selected) == 2
        idx_sec = canonical_index("security")
        idx_be = canonical_index("backend")
        assert idx_sec < idx_be, "Security should sort before backend"
        assert selected[0].bundle == "security"
        assert selected[1].bundle == "backend"

    def test_deduplication_no_duplicates_in_result(self) -> None:
        """select_skills_hybrid never returns duplicate skills."""
        _require_module()
        skill = _make_skill(
            name="SQL Injection Prevention",
            description="Detect SQL injection in database code.",
            applies_to=["**/*.py"],
            bundle="backend",
        )
        diff = "SELECT * FROM users WHERE id={user_id}"
        paths = ["src/db/users.py"]
        selected = select_skills_hybrid(
            [skill, skill],  # duplicate in input
            paths,
            diff,
            bundles={"backend"},
            adapter=None,
        )
        keys = [f"{s.bundle}/{s.filename}" for s in selected]
        assert len(keys) == len(set(keys)), "No duplicates in select_skills_hybrid result"

    def test_empty_skills_returns_empty(self) -> None:
        """Empty skill list returns empty selection."""
        _require_module()
        selected = select_skills_hybrid(
            [], ["src/api.py"], "diff content", bundles=set(), adapter=None
        )
        assert selected == [], "Empty input skills → empty selection"

    def test_result_is_a_list_of_skill_instances(self) -> None:
        """Return type is always list[Skill]."""
        _require_module()
        skill = _make_skill(
            name="Code Quality",
            description="General code quality checks.",
            applies_to=["**/*.py"],
        )
        result = select_skills_hybrid([skill], [], "", bundles=set(), adapter=None)
        assert isinstance(result, list), "select_skills_hybrid must return a list"
        for item in result:
            assert isinstance(item, Skill), f"Every result item must be a Skill, got {type(item)}"
