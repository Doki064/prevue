"""Parametrized contract suite over registered engine adapters (D-11)."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from prevue.classify.models import CANONICAL_LABEL_ORDER
from prevue.engines.errors import AuthError
from prevue.engines.registry import ENGINES, get_adapter
from tests.engine_helpers import (
    PROSE_REVIEW,
    VALID_FINDING,
    VALID_TOKEN,
    make_sample_request,
    stdout_with_fence,
)

FUNCTIONAL = sorted(ENGINES.keys())  # all four engines are now functional (D-12/D-03)

AUTH_ENV: dict[str, tuple[str, str | None]] = {
    "copilot-cli": ("COPILOT_GITHUB_TOKEN", VALID_TOKEN),
    "claude-code-cli": ("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-test-key"),
    "cursor-cli": ("CURSOR_API_KEY", "cur_test_key"),
    "antigravity-cli": ("ANTIGRAVITY_API_KEY", "agy-test-key"),
}


@pytest.fixture(params=FUNCTIONAL)
def engine_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def adapter(engine_name: str):
    return get_adapter(engine_name)


@pytest.fixture
def authed_env(engine_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in AUTH_ENV:
        env_var, _ = AUTH_ENV[name]
        monkeypatch.delenv(env_var, raising=False)
    env_var, value = AUTH_ENV[engine_name]
    if value:
        monkeypatch.setenv(env_var, value)


def test_valid_fence_returns_result(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout = stdout_with_fence(payload=[VALID_FINDING])

    def _success(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _success)
    result = adapter.review(make_sample_request())
    assert result.degraded is False
    assert len(result.findings) == 1
    assert result.summary_markdown == PROSE_REVIEW
    assert result.engine_meta.get("retried") is False


def test_unparseable_degrades(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    result = adapter.review(make_sample_request())
    assert result.degraded is True
    assert result.findings == []
    assert "parse_error" in result.engine_meta


def test_bad_then_good_sets_retried(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []

    def _run(_cmd, input=None, **_kwargs):
        calls.append(input)
        stdout = PROSE_REVIEW if len(calls) == 1 else stdout_with_fence(payload=[VALID_FINDING])
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    result = adapter.review(make_sample_request())
    assert len(calls) == 2
    assert result.degraded is False
    assert len(result.findings) == 1
    assert result.engine_meta.get("retried") is True


def test_missing_credential_raises_auth_error(
    engine_name: str, adapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    for env_var, _ in AUTH_ENV.values():
        monkeypatch.delenv(env_var, raising=False)

    called = False

    def _run(*_args, **_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    with pytest.raises(AuthError):
        adapter.review(make_sample_request())
    assert not called


def test_vendor_argv(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        captured["input"] = input
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    adapter.review(make_sample_request())

    cmd = captured["cmd"]
    if engine_name == "copilot-cli":
        assert cmd == ["copilot", "-s", "--no-ask-user"]
        assert captured["input"] is not None
    elif engine_name == "claude-code-cli":
        assert cmd == ["claude", "-p", "--output-format", "text"]
        assert captured["input"] is not None
    elif engine_name == "cursor-cli":
        assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "text"]
        assert "-f" in cmd
        assert "--force" not in cmd
    elif engine_name == "antigravity-cli":
        # Pitfall 2 pseudo-TTY wrapper: antigravity runs via `bash -c 'script -qec ...'`
        # to survive the non-TTY stdout-drop bug in CI (T-10-21).
        assert cmd[:2] == ["bash", "-c"], (
            f"Antigravity must invoke via bash -c wrapper for pseudo-TTY; got cmd={cmd}"
        )
        # The shell command string must reference the inner agy invocation
        shell_cmd = cmd[2]
        assert "agy" in shell_cmd, f"Inner shell command missing 'agy': {shell_cmd}"
        assert "script -qec" in shell_cmd, (
            f"Antigravity must use 'script -qec' pseudo-TTY wrapper; got: {shell_cmd}"
        )
    else:
        pytest.fail(f"Unexpected engine {engine_name!r}")


def test_claude_model_mapping_on_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-test-key")
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    req = make_sample_request().model_copy(update={"model": "sonnet"})
    get_adapter("claude-code-cli").review(req)
    assert captured["cmd"] == [
        "claude",
        "-p",
        "--output-format",
        "text",
        "--model",
        "sonnet",
    ]


def test_cursor_model_mapping_and_prompt_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "cur_test_key")
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        file_idx = cmd.index("-f") + 1
        with open(cmd[file_idx], encoding="utf-8") as f:
            captured["prompt"] = f.read()
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    req = make_sample_request().model_copy(update={"model": "sonnet-4"})
    get_adapter("cursor-cli").review(req)
    cmd = captured["cmd"]
    assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "text"]
    assert ["-m", "sonnet-4"] == cmd[-2:]
    assert "src/main.py" in captured["prompt"]


def test_cursor_invoked_with_consumer_cwd_when_env_set(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cursor-agent subprocess.run receives cwd=consumer root when PREVUE_CONSUMER_ROOT is set."""
    monkeypatch.setenv("CURSOR_API_KEY", "cur_test_key")
    monkeypatch.setenv("PREVUE_CONSUMER_ROOT", str(tmp_path))
    captured: dict = {}

    def _capture(cmd, input=None, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    get_adapter("cursor-cli").review(make_sample_request())
    assert captured["cwd"] == str(tmp_path)


def test_cursor_invoked_with_none_cwd_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cursor-agent subprocess.run receives cwd=None when PREVUE_CONSUMER_ROOT is unset."""
    monkeypatch.setenv("CURSOR_API_KEY", "cur_test_key")
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)
    captured: dict = {}

    def _capture(cmd, input=None, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    get_adapter("cursor-cli").review(make_sample_request())
    assert captured["cwd"] is None


def test_classify_valid_json_returns_label_map(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"src/main.py": "backend", "README.md": "frontend"}
    stdout = json.dumps(payload)

    def _success(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _success)
    result = adapter.classify(["src/main.py", "README.md"], CANONICAL_LABEL_ORDER)
    assert result == payload


def test_classify_drops_unknown_labels(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout = json.dumps({"src/main.py": "backend", "README.md": "not-a-label"})

    def _success(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _success)
    result = adapter.classify(["src/main.py", "README.md"], CANONICAL_LABEL_ORDER)
    assert result == {"src/main.py": "backend"}


def test_classify_missing_credential_raises_auth_error(
    engine_name: str, adapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    for env_var, _ in AUTH_ENV.values():
        monkeypatch.delenv(env_var, raising=False)

    called = False

    def _run(*_args, **_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    with pytest.raises(AuthError):
        adapter.classify(["src/main.py"], CANONICAL_LABEL_ORDER)
    assert not called


def test_adapter_cli_commands_contain_no_allow_tool_flags() -> None:
    """D-08 regression: no adapter may pass --allow-tool to its CLI subprocess.
    Static source scan only — live tool-posture verification is a separate required
    pre-production step documented in SECURITY.md (see D-08 row and 07-05 UAT checklist).
    """
    import pathlib

    engines_dir = pathlib.Path("src/prevue/engines")
    violations: list[str] = []

    for py_file in sorted(engines_dir.glob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        if "--allow-tool" in source:
            violations.append(f"{py_file}: contains '--allow-tool' flag")

    assert not violations, "Adapters must not pass --allow-tool to CLI: " + "; ".join(violations)


def test_security_md_documents_d08_live_verification() -> None:
    """D-08 gap: static scan cannot verify vendor-controlled CLI tool access.
    SECURITY.md must document that live engine tool-posture verification is a required
    pre-production checkpoint so consumers know to run it before enabling merge gates.
    """
    import pathlib

    security_md = pathlib.Path("SECURITY.md")
    assert security_md.exists(), "SECURITY.md must exist"
    content = security_md.read_text(encoding="utf-8")
    assert "D-08" in content, "SECURITY.md must document D-08 vector"
    assert "pre-production" in content, (
        "SECURITY.md must describe D-08 as pre-production checkpoint"
    )
    assert "live" in content.lower(), "SECURITY.md must mention live verification for D-08"
