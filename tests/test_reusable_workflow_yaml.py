"""Static guards for .github/workflows/prevue-review.yml reusable workflow (WKFL-01/02/04)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REUSABLE_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-review.yml"
)
INSTALL_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "install-engine-cli.sh"
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
    assert any("github.event.pull_request.base.sha" in ref for ref in refs)
    assert any("inputs.consumer-base-sha" in ref for ref in refs)
    assert any("prevue" in ref.lower() or "inputs.prevue-ref" in ref for ref in refs)


def test_minimal_permissions() -> None:
    """WKFL-04: contents:write required for LIFE-04 resolveReviewThread (live-verified)."""
    wf = _load_reusable_workflow()
    assert wf["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
        "checks": "write",
    }


def test_contents_write_documented_for_life04() -> None:
    """contents:write must be documented — not silent scope broadening."""
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "LIFE-04" in text or "resolveReviewThread" in text
    match = re.search(r"^permissions:\n((?:  .+\n)+)", text, re.MULTILINE)
    assert match is not None, "permissions block missing"
    assert "contents: write" in match.group(0)


def test_draft_if_guard() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "draft" in text.lower()
    assert "if:" in text


def test_fork_pr_job_guard() -> None:
    """Reusable job must self-guard fork PRs (v1 forks-skip), not rely on callers."""
    wf = _load_reusable_workflow()
    guards = [str(job.get("if", "")) for job in wf.get("jobs", {}).values()]
    assert any(
        "github.event.pull_request.head.repo.full_name == github.repository" in guard
        for guard in guards
    )


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
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "cursor.com/install" in script
    assert "npm install -g cursor-agent" not in script
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "install-engine-cli.sh" in text


def test_cursor_install_downloads_then_execs_not_pipe_to_bash() -> None:
    """Hardening guard: fetch installer to a file then exec, never curl | bash."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "cursor.com/install -o" in script
    assert "cursor.com/install -fsS | bash" not in script
    assert "cursor.com/install | bash" not in script


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


def test_cursor_install_supports_optional_sha256_pin() -> None:
    script = (
        Path(__file__).resolve().parents[1] / ".github/scripts/install-engine-cli.sh"
    ).read_text(encoding="utf-8")
    assert "PREVUE_CURSOR_INSTALL_SHA256" in script
    assert "sha256sum -c" in script


# ---------------------------------------------------------------------------
# OUTP-05 / D-08/D-09: job outputs, artifact upload (Plan 05). Copilot's OTEL env
# wiring (formerly asserted here) was removed by gap-closure Plan 08 — Copilot now
# uses the honest ~est bytes/4 estimate path (usage_capture="none") since no CI-viable
# OTEL enablement mechanism exists on @github/copilot@1.0.61 (10-UAT.md gap 1).
# ---------------------------------------------------------------------------


def test_job_outputs_map_declared() -> None:
    """OUTP-05 / D-09: review job must declare outputs: map with all compact keys."""
    wf = _load_reusable_workflow()
    job = wf["jobs"]["review"]
    outputs = job.get("outputs", {})
    expected_keys = {
        "schema_version",
        "conclusion",
        "error_count",
        "warning_count",
        "info_count",
        "tokens",
        "cost_usd",
    }
    assert expected_keys <= set(outputs.keys()), (
        f"Missing job output keys: {expected_keys - set(outputs.keys())}"
    )
    # All outputs must reference the run-review step
    for key, value in outputs.items():
        if key in expected_keys:
            assert "run-review" in str(value), (
                f"Job output '{key}' must reference steps.run-review (got: {value})"
            )


def test_workflow_call_outputs_block_declared() -> None:
    """OUTP-05 gap-closure (10-08, Gap 3): a job-level `jobs.review.outputs:` block alone
    does NOT propagate across the workflow_call boundary — GitHub Actions requires a
    sibling top-level `on.workflow_call.outputs:` block re-mapping the same keys, or every
    job output comes back empty to a caller's `needs.<job>.outputs.*` (live-confirmed via
    a downstream probe job in 10-UAT.md gap 3). This regression test fails if the block is
    missing entirely, or if a key drifts between the two output declarations (the exact
    failure mode UAT gap 3 describes as "easy to reintroduce").
    """
    wf = _load_reusable_workflow()
    on = wf.get("on") or wf.get(True)
    workflow_call = (on or {}).get("workflow_call", {})
    call_outputs = workflow_call.get("outputs")
    assert call_outputs, (
        "on.workflow_call.outputs block is missing — job-level jobs.review.outputs alone "
        "never reaches a caller's needs.<job>.outputs.* (OUTP-05 gap 3)"
    )

    job_outputs = wf["jobs"]["review"].get("outputs", {})
    expected_keys = {
        "schema_version",
        "conclusion",
        "error_count",
        "warning_count",
        "info_count",
        "tokens",
        "cost_usd",
    }

    # Per-key existence check (not "at least these keys exist") — catches drift between
    # on.workflow_call.outputs and jobs.review.outputs in either direction.
    assert expected_keys <= set(call_outputs.keys()), (
        f"Missing workflow_call output keys: {expected_keys - set(call_outputs.keys())}"
    )
    assert set(call_outputs.keys()) == set(job_outputs.keys()), (
        "on.workflow_call.outputs and jobs.review.outputs key sets have drifted: "
        f"workflow_call-only={set(call_outputs.keys()) - set(job_outputs.keys())}, "
        f"job-only={set(job_outputs.keys()) - set(call_outputs.keys())}"
    )

    for key in expected_keys:
        entry = call_outputs.get(key) or {}
        value_expr = str(entry.get("value", ""))
        assert f"jobs.review.outputs.{key}" in value_expr, (
            f"on.workflow_call.outputs.{key} must re-map to jobs.review.outputs.{key} "
            f"(got: {value_expr!r})"
        )


def test_run_review_step_has_id() -> None:
    """Run review step must have id: run-review so job outputs can reference its $GITHUB_OUTPUT."""
    wf = _load_reusable_workflow()
    steps = wf["jobs"]["review"]["steps"]
    run_review_steps = [s for s in steps if s.get("id") == "run-review"]
    assert len(run_review_steps) == 1, (
        f"Expected exactly one step with id: run-review; found {len(run_review_steps)}"
    )
    step = run_review_steps[0]
    assert "prevue review" in str(step.get("run", "")), (
        "The run-review step must invoke 'prevue review'"
    )


def test_upload_artifact_step_present() -> None:
    """OUTP-05 / D-08 (Pitfall 6): full JSON goes to artifact to avoid 1 MB job-output limit."""
    wf = _load_reusable_workflow()
    steps = wf["jobs"]["review"]["steps"]
    artifact_steps = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert artifact_steps, "No upload-artifact step found in the review job"
    step = artifact_steps[0]
    # Must run with if: always() so artifact is produced even on degraded/neutral reviews
    assert step.get("if") == "always()", (
        f"upload-artifact step must have 'if: always()'; got: {step.get('if')}"
    )
    # Must upload prevue-result.json (or reference it)
    path = str((step.get("with") or {}).get("path", ""))
    assert "prevue-result" in path, f"upload-artifact must upload prevue-result.json; path={path}"


# ---------------------------------------------------------------------------
# Plan 06 — Task 1: Antigravity install + secret pass-through + pseudo-TTY
# ---------------------------------------------------------------------------


def test_antigravity_install_case_exists() -> None:
    """antigravity-cli case must exist in the install script (D-12 / T-10-17)."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "antigravity-cli)" in script, (
        "install-engine-cli.sh is missing the antigravity-cli) case"
    )


def test_antigravity_install_checksum_gate() -> None:
    """Antigravity install must include PREVUE_ANTIGRAVITY_INSTALL_SHA256 checksum gate
    mirroring the Cursor PREVUE_CURSOR_INSTALL_SHA256 pattern (T-10-17 mitigation)."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "PREVUE_ANTIGRAVITY_INSTALL_SHA256" in script, (
        "Missing PREVUE_ANTIGRAVITY_INSTALL_SHA256 checksum gate for antigravity install"
    )
    assert "sha256sum -c" in script, "Missing sha256sum -c verification in install script"


def test_antigravity_install_downloads_then_execs() -> None:
    """Hardening guard: fetch Antigravity installer to a file then exec, never pipe to bash."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "antigravity.google/cli/install.sh" in script, (
        "Missing antigravity.google/cli/install.sh in install script"
    )
    # Must download to a file (not curl | bash)
    assert "antigravity.google/cli/install.sh -o" in script, (
        "Antigravity install must use -o to save to a file, not pipe to bash"
    )
    assert "antigravity.google/cli/install.sh | bash" not in script, (
        "Antigravity install must NOT use pipe-to-bash pattern"
    )


def test_antigravity_secret_in_workflow_call_secrets() -> None:
    """ENGN-10: antigravity-api-key must be declared in workflow_call secrets block."""
    wf = _load_reusable_workflow()
    on = wf.get("on") or wf.get(True)
    secrets = (on or {}).get("workflow_call", {}).get("secrets", {})
    assert "antigravity-api-key" in secrets, (
        "antigravity-api-key missing from workflow_call secrets block"
    )
    assert secrets["antigravity-api-key"].get("required") is False, (
        "antigravity-api-key must be required: false (optional secret)"
    )


def test_antigravity_secret_gated_on_engine_input() -> None:
    """ANTIGRAVITY_API_KEY in Run-review env must be gated on inputs.engine == 'antigravity-cli'
    (T-10-20: secret not leaked to non-Antigravity runs)."""
    wf = _load_reusable_workflow()
    steps = wf["jobs"]["review"]["steps"]
    run_review_steps = [s for s in steps if s.get("id") == "run-review"]
    assert run_review_steps, "run-review step not found"
    env = run_review_steps[0].get("env") or {}
    assert "ANTIGRAVITY_API_KEY" in env, "ANTIGRAVITY_API_KEY missing from Run-review step env"
    antigravity_val = str(env["ANTIGRAVITY_API_KEY"])
    assert "antigravity-cli" in antigravity_val, (
        "ANTIGRAVITY_API_KEY must be gated on inputs.engine == 'antigravity-cli';"
        f" got: {antigravity_val}"
    )
    assert "antigravity-api-key" in antigravity_val, (
        "ANTIGRAVITY_API_KEY must reference the antigravity-api-key named secret;"
        f" got: {antigravity_val}"
    )


def test_antigravity_pseudo_tty_wrapper_present() -> None:
    """Pitfall 2 / T-10-21: the pseudo-TTY script -qec wrapper must be encoded in the
    Antigravity invocation path to survive the non-TTY stdout-drop bug in CI."""
    import subprocess

    # Check cli_adapter.py for the workaround (the canonical location per plan)
    cli_adapter = (
        Path(__file__).resolve().parents[1] / "src" / "prevue" / "engines" / "cli_adapter.py"
    )
    result = subprocess.run(
        ["grep", "-l", "script -qec", str(cli_adapter)],
        capture_output=True,
        text=True,
    )
    found_in_adapter = result.returncode == 0

    # Also accept it in the .github/ tree as a documented wrapper
    result2 = subprocess.run(
        ["grep", "-rl", "script -qec", str(Path(__file__).resolve().parents[1] / ".github")],
        capture_output=True,
        text=True,
    )
    found_in_github = bool(result2.stdout.strip())

    assert found_in_adapter or found_in_github, (
        "pseudo-TTY wrapper 'script -qec' not found in cli_adapter.py or .github/ — "
        "Antigravity non-TTY stdout-drop workaround (Pitfall 2) must be encoded somewhere "
        "in the invocation path"
    )


def test_otel_env_end_to_end_capture(tmp_path) -> None:
    """WARNING 3 end-to-end: with COPILOT_OTEL_FILE_EXPORTER_PATH set and a fixture OTEL log,
    capture_usage returns estimated=False (real tokens, not bytes/4 estimate).
    """
    from prevue.engines.usage import capture_usage

    # Simulate the CliEngineSpec otel-jsonl strategy
    class _FakeSpec:
        usage_capture = "otel-jsonl"

    # Use the fixture copilot_otel.jsonl that already exists from Plan 01/03
    fixture_otel = (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "usage" / "copilot_otel.jsonl"
    )
    if not fixture_otel.exists():
        # Fallback path used when running from project root
        fixture_otel = Path(__file__).resolve().parent / "fixtures" / "usage" / "copilot_otel.jsonl"
    assert fixture_otel.exists(), f"copilot_otel.jsonl fixture not found at {fixture_otel}"

    result = capture_usage(_FakeSpec(), stdout="", otel_path=str(fixture_otel))
    assert result is not None, (
        "capture_usage returned None for otel-jsonl strategy with a valid OTEL log path — "
        "COPILOT_OTEL_FILE_EXPORTER_PATH cross-wave dependency not satisfied"
    )
    assert result.get("estimated") is False, (
        f"capture_usage must return estimated=False for otel-jsonl strategy; got: {result}"
    )
