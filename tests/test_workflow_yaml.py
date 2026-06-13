"""Static SECR-01 guards for .github/workflows/review.yml."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REVIEW_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "review.yml"

# Patterns that indicate checkout of untrusted PR head ref (Pitfall 1).
PR_HEAD_REF_PATTERNS = (
    re.compile(r"github\.event\.pull_request\.head", re.IGNORECASE),
    re.compile(r"pull_request\.head\.sha", re.IGNORECASE),
    re.compile(r"head\.ref", re.IGNORECASE),
    re.compile(r"head_ref", re.IGNORECASE),
)


def _load_review_workflow() -> dict:
    with REVIEW_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_review_workflow_exists() -> None:
    assert REVIEW_WORKFLOW.is_file()


def test_pull_request_trigger_only() -> None:
    wf = _load_review_workflow()
    on = wf.get("on") or wf.get(True)  # yaml key `on` may parse as True
    assert on is not None
    if isinstance(on, dict):
        assert "pull_request" in on
        assert "pull_request_target" not in on
    else:
        assert on == "pull_request"


def test_pull_request_types() -> None:
    wf = _load_review_workflow()
    on = wf.get("on") or wf.get(True)
    assert isinstance(on, dict)
    pr = on["pull_request"]
    if isinstance(pr, dict):
        assert pr.get("types") == ["opened", "synchronize", "reopened"]


def test_minimal_permissions() -> None:
    wf = _load_review_workflow()
    assert wf["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "checks": "write",
    }


def test_no_pull_request_target_in_source() -> None:
    text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text


def test_no_pr_head_checkout() -> None:
    wf = _load_review_workflow()
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" not in uses:
                continue
            with_block = step.get("with") or {}
            ref_value = with_block.get("ref", "")
            ref_str = str(ref_value)
            for pattern in PR_HEAD_REF_PATTERNS:
                assert not pattern.search(ref_str), (
                    f"checkout step must not use PR head ref: {ref_str!r}"
                )


def test_single_prevue_review_invocation() -> None:
    wf = _load_review_workflow()
    invocations: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "prevue review" in run:
                invocations.append(run.strip())
    assert len(invocations) == 1
    assert invocations[0] == "uv run prevue review"


def test_copilot_token_env_separate_from_github_token() -> None:
    wf = _load_review_workflow()
    review_step = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("run", "").strip() == "uv run prevue review":
                review_step = step
                break
    assert review_step is not None
    env = review_step.get("env") or {}
    assert "GITHUB_TOKEN" in env
    assert "COPILOT_GITHUB_TOKEN" in env
    assert "${{ github.token }}" in str(env["GITHUB_TOKEN"])
    assert "${{ secrets.COPILOT_GITHUB_TOKEN }}" in str(env["COPILOT_GITHUB_TOKEN"])


SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
CHECKOUT_SHA = "df4cb1c069e1874edd31b4311f1884172cec0e10"
COPILOT_CLI_VERSION = "1.0.61"


def test_checkout_is_sha_pinned() -> None:
    wf = _load_review_workflow()
    checkout_uses = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" in uses:
                checkout_uses = uses
    assert checkout_uses == f"actions/checkout@{CHECKOUT_SHA}"


def test_setup_uv_is_sha_pinned() -> None:
    wf = _load_review_workflow()
    setup_uv_uses = None
    uv_version = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses.startswith("astral-sh/setup-uv@"):
                setup_uv_uses = uses
                uv_version = (step.get("with") or {}).get("version")
    assert setup_uv_uses == f"astral-sh/setup-uv@{SETUP_UV_SHA}"
    assert uv_version == "0.11.21"


def _copilot_install_command(wf: dict) -> str | None:
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "@github/copilot@" in run:
                return run.strip()
    return None


def test_copilot_cli_version_pinned() -> None:
    install = _copilot_install_command(_load_review_workflow())
    assert install == f"npm install -g @github/copilot@{COPILOT_CLI_VERSION}"
