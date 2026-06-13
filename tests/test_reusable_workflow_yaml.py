"""Static guards for .github/workflows/prevue-review.yml reusable workflow (WKFL-01/02/04)."""

from __future__ import annotations

from pathlib import Path

import yaml

REUSABLE_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-review.yml"
)

SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
CHECKOUT_SHA = "df4cb1c069e1874edd31b4311f1884172cec0e10"


def _load_reusable_workflow() -> dict:
    with REUSABLE_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_workflow_call_trigger() -> None:
    wf = _load_reusable_workflow()
    on = wf.get("on") or wf.get(True)
    assert on is not None
    assert "workflow_call" in on


def test_two_checkouts() -> None:
    wf = _load_reusable_workflow()
    checkout_steps: list[dict] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" in uses:
                checkout_steps.append(step)
    assert len(checkout_steps) >= 2
    refs = [str((step.get("with") or {}).get("ref", "")) for step in checkout_steps]
    assert any("${{ github.event.pull_request.base.sha }}" in ref for ref in refs)
    assert any("prevue" in ref.lower() or "inputs.prevue-ref" in ref for ref in refs)


def test_minimal_permissions() -> None:
    wf = _load_reusable_workflow()
    assert wf["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "checks": "write",
    }


def test_draft_if_guard() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "draft" in text.lower()
    assert "if:" in text


def test_named_secrets_not_required() -> None:
    wf = _load_reusable_workflow()
    on = wf.get("on") or wf.get(True)
    secrets = (on or {}).get("workflow_call", {}).get("secrets", {})
    assert secrets
    for spec in secrets.values():
        assert spec.get("required") is False


def test_sha_pinned_actions() -> None:
    wf = _load_reusable_workflow()
    uses_values: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses:
                uses_values.append(uses)
    checkout_uses = [u for u in uses_values if "checkout" in u]
    setup_uv_uses = [u for u in uses_values if u.startswith("astral-sh/setup-uv@")]
    assert checkout_uses
    assert all("@" in u and not u.endswith("@main") for u in checkout_uses)
    assert setup_uv_uses == [f"astral-sh/setup-uv@{SETUP_UV_SHA}"]


def test_no_pull_request_target() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text


def test_no_secrets_inherit() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets: inherit" not in text
    assert "secrets:inherit" not in text.replace(" ", "")


def test_cursor_install_uses_official_curl_not_npm_impostor() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "cursor.com/install" in text
    assert "npm install -g cursor-agent" not in text


def test_self_checkout_ref_not_main() -> None:
    wf = _load_reusable_workflow()
    prevue_refs: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" not in uses:
                continue
            with_block = step.get("with") or {}
            ref = str(with_block.get("ref", ""))
            path = str(with_block.get("path", ""))
            repository = str(with_block.get("repository", ""))
            if "prevue" in path.lower() or "prevue" in repository.lower():
                prevue_refs.append(ref)
    assert prevue_refs
    assert all(ref not in ("main", "master", "HEAD") for ref in prevue_refs)
