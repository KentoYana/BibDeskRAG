from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import subprocess
import sys

import pytest

from bibdesk_rag.mcp_server import MCPServer, serve
from bibdesk_rag import setup_connection as connection


def completed(value=None, returncode=0, *, text=None):
    return subprocess.CompletedProcess([], returncode, json.dumps(value) if text is None else text, "")


def registration(mcp, config, option="--temp"):
    return {
        "name": "bibdesk-rag", "enabled": True, "disabled_reason": None,
        "transport": {
            "type": "stdio", "command": str(mcp), "args": [option, str(config)],
            "env": None, "env_vars": [], "cwd": None,
        },
        "enabled_tools": None, "disabled_tools": None,
    }


def runner(*responses):
    pending = iter(responses)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert isinstance(argv, list)
        assert kwargs["shell"] is False
        assert 0 < kwargs["timeout"] <= 30
        response = next(pending)
        if isinstance(response, BaseException):
            raise response
        return response

    run.calls = calls
    return run


@pytest.fixture
def paths(tmp_path):
    mcp = tmp_path / "日本語 folder" / "bibdesk-rag-mcp $(touch INJECTED);"
    config = tmp_path / "設定 'quoted' $(touch INJECTED).toml"
    codex = tmp_path / "codex"
    return codex, mcp, config


@pytest.mark.parametrize("option", ["--temp", "--config"])
def test_registration_match_without_add(paths, option):
    codex, mcp, config = paths
    run = runner(completed(registration(mcp, config, option)))
    assert connection.register(codex, mcp, config, run=run)
    assert run.calls[0][0] == [str(codex), "mcp", "get", "bibdesk-rag", "--json"]
    assert len(run.calls) == 1


@pytest.mark.parametrize("mutation", [
    lambda item: item.update(enabled=False),
    lambda item: item.update(disabled_reason="disabled"),
    lambda item: item.update(enabled_tools=[]),
    lambda item: item.update(disabled_tools=["search_papers"]),
    lambda item: item["transport"].update(command="relative-mcp"),
    lambda item: item["transport"].update(command="/another/mcp"),
    lambda item: item["transport"].update(args=[]),
    lambda item: item["transport"].update(args=["--temp", "/another/config.toml"]),
    lambda item: item["transport"].update(args=item["transport"]["args"] * 2),
    lambda item: item["transport"].update(env={"BIBDESK_RAG_HOME": "/another"}),
    lambda item: item["transport"].update(env_vars=["PYTHONPATH"]),
    lambda item: item["transport"].update(cwd="/another"),
    lambda item: item["transport"].update(experimental_environment="remote"),
    lambda item: item["transport"].update(type="streamable_http"),
])
def test_registration_conflicts_never_overwritten(paths, mutation):
    codex, mcp, config = paths
    value = registration(mcp, config)
    mutation(value)
    run = runner(completed(value), completed(value))
    assert connection.inspect_registration(codex, mcp, config, run=run) == "conflict"
    assert not connection.register(codex, mcp, config, run=run)
    assert all(call[0][2] == "get" for call in run.calls)


@pytest.mark.parametrize("responses", [
    [completed(text="not json")],
    [completed(None)],
    [completed({"name": "other"})],
    [completed(text="private failure", returncode=1), completed(returncode=1)],
    [completed(returncode=1), completed({})],
    [completed(returncode=1), completed([{"name": "bibdesk-rag"}])],
    [completed(returncode=1), completed(["bad entry"])],
    [subprocess.TimeoutExpired("codex", 15)],
    [OSError("private external error")],
])
def test_unknown_registration_fails_closed(paths, responses, capsys):
    assert connection.inspect_registration(*paths, run=runner(*responses)) == "unknown"
    assert capsys.readouterr() == ("", "")


def test_missing_requires_successful_list_and_add_preserves_literal_arguments(paths, tmp_path):
    codex, mcp, config = paths
    run = runner(
        completed(returncode=1), completed([{"name": "unrelated"}]),
        completed(text="Registered"), completed(registration(mcp, config)),
    )
    assert connection.register(codex, mcp, config, run=run)
    assert [call[0][2] for call in run.calls] == ["get", "list", "add", "get"]
    assert run.calls[2][0] == [
        str(codex), "mcp", "add", "bibdesk-rag", "--", str(mcp), "--temp", str(config),
    ]
    assert run.calls[2][1]["input"] is None
    assert not (tmp_path / "INJECTED").exists()


@pytest.mark.parametrize("addition", [completed(returncode=1), subprocess.TimeoutExpired("x", 15)])
def test_add_failure_returns_false(paths, addition):
    run = runner(completed(returncode=1), completed([]), addition)
    assert not connection.register(*paths, run=run)


def test_successful_add_without_matching_readback_is_unverified(paths):
    run = runner(completed(returncode=1), completed([]), completed(), completed({}))
    assert not connection.register(*paths, run=run)


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    return path


def test_discovery_prefers_sibling_and_preserves_upgrade_safe_symlink(tmp_path, monkeypatch):
    installed = executable(tmp_path / "Cellar/bibdesk-rag/1/bin/bibdesk-rag-mcp")
    stable = tmp_path / "prefix/bin/bibdesk-rag-mcp"
    stable.parent.mkdir(parents=True)
    stable.symlink_to(installed)
    launcher = executable(stable.parent / "bibdesk-rag")
    another = executable(tmp_path / "another/bin/bibdesk-rag-mcp")
    monkeypatch.setattr(sys, "argv", [str(launcher)])
    monkeypatch.setattr(connection.shutil, "which", lambda name: str(another))
    assert connection.discover_executable("bibdesk-rag-mcp") == stable
    assert connection.discover_executable("bibdesk-rag-mcp") != installed


def test_discovery_uses_path_for_bare_launcher(tmp_path, monkeypatch):
    mcp = executable(tmp_path / "bin/bibdesk-rag-mcp")
    launcher = executable(tmp_path / "bin/bibdesk-rag")
    monkeypatch.setattr(sys, "argv", ["bibdesk-rag"])
    monkeypatch.setattr(connection.shutil, "which", lambda name: str(launcher))
    assert connection.discover_executable("bibdesk-rag-mcp") == mcp


def test_discovery_missing_or_not_executable(tmp_path, monkeypatch):
    file = tmp_path / "codex"
    file.write_text("not executable")
    monkeypatch.setattr(connection.shutil, "which", lambda name: str(file))
    assert connection.discover_executable("codex") is None
    monkeypatch.setattr(connection.shutil, "which", lambda name: None)
    assert connection.discover_executable("codex") is None


def handshake_reply():
    output = StringIO()

    def run(argv, **kwargs):
        serve(MCPServer(), StringIO(kwargs["input"]), output)
        return completed(text=output.getvalue())

    assert connection.probe_mcp(Path("/mcp"), Path("/config"), run=run)
    return [json.loads(line) for line in output.getvalue().splitlines()]


def test_mcp_probe_sends_only_initialization_and_tools_listing(paths):
    _, mcp, config = paths

    def run(argv, **kwargs):
        assert argv == [str(mcp), "--temp", str(config)]
        assert kwargs["shell"] is False
        messages = [json.loads(line) for line in kwargs["input"].splitlines()]
        assert [item["method"] for item in messages] == [
            "initialize", "notifications/initialized", "tools/list",
        ]
        output = StringIO()
        serve(MCPServer(), StringIO(kwargs["input"]), output)
        return completed(text=output.getvalue())

    assert connection.probe_mcp(mcp, config, run=run)


@pytest.mark.parametrize("mutation", [
    lambda replies: replies.pop(),
    lambda replies: replies[0].update(id=100),
    lambda replies: replies[0].update(error={"message": "failed"}),
    lambda replies: replies[0]["result"].update(protocolVersion="unknown"),
    lambda replies: replies[0]["result"].update(serverInfo={"name": "another"}),
    lambda replies: replies[1]["result"].update(tools=[]),
    lambda replies: replies[1]["result"]["tools"][0]["annotations"].update(readOnlyHint=False),
])
def test_mcp_probe_does_not_mistake_invalid_replies_for_success(paths, mutation):
    replies = handshake_reply()
    mutation(replies)
    run = runner(completed(text="\n".join(json.dumps(item) for item in replies)))
    assert not connection.probe_mcp(paths[1], paths[2], run=run)


@pytest.mark.parametrize("result", [
    completed(text="not json"), completed(returncode=1),
    subprocess.TimeoutExpired("mcp", 15), OSError("missing executable"),
])
def test_mcp_probe_failure_is_bounded_and_silent(paths, result, capsys):
    assert not connection.probe_mcp(paths[1], paths[2], run=runner(result))
    assert capsys.readouterr() == ("", "")


def test_real_local_mcp_stdio_probe(tmp_path):
    # The installed interpreter imports this package; no user library/config is read.
    launcher = tmp_path / "bibdesk-rag-mcp"
    launcher.write_text(
        f"#!{sys.executable}\nfrom bibdesk_rag.mcp_server import main\nraise SystemExit(main())\n"
    )
    launcher.chmod(0o700)
    config = tmp_path / "config.toml"
    config.write_text("synthetic sentinel; handshake does not read library data")
    before = config.read_bytes()
    assert connection.probe_mcp(launcher, config)
    assert config.read_bytes() == before
