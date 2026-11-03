"""Local setup connection checks, independent of prompts and library contents.

No shell is used. Codex output is treated as untrusted and never echoed to the
terminal; an unavailable or unrecognized CLI cannot authorize an overwrite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__

SERVER_NAME = "bibdesk-rag"
TIMEOUT = 15
MAX_RESPONSE_CHARS = 1_000_000
EXPECTED_TOOLS = {
    "search_papers", "search_fulltext", "get_paper", "get_attachments",
    "get_chunk", "build_context",
}


def _absolute(path: str | Path) -> Path:
    # Preserve Homebrew's stable bin/opt symlinks rather than pinning a Cellar version.
    return Path(os.path.abspath(Path(path).expanduser()))


def discover_executable(name: str) -> Path | None:
    """Find an executable without scanning directories or assuming a brew prefix."""
    candidates = []
    if name == "bibdesk-rag-mcp":
        launcher = sys.argv[0]
        if launcher and Path(launcher).name == "bibdesk-rag":
            located = launcher if os.path.dirname(launcher) else shutil.which(launcher)
            if located:
                candidates.append(_absolute(located).parent / name)
        # Also supports `python -m bibdesk_rag.cli` in the installed environment.
        candidates.append(_absolute(sys.executable).parent / name)
    located = shutil.which(name)
    if located:
        candidates.append(_absolute(located))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _call(argv: list[str], *, run, input: str | None = None):
    return run(
        argv, input=input, capture_output=True, text=True,
        timeout=TIMEOUT, check=False, shell=False,
    )


def _json_output(completed):
    if len(completed.stdout) > MAX_RESPONSE_CHARS:
        raise ValueError("Oversized response")
    return json.loads(completed.stdout)


def _matches(value, mcp: Path, config_path: Path) -> bool:
    if not isinstance(value, dict) or value.get("name") != SERVER_NAME:
        return False
    transport = value.get("transport")
    if not isinstance(transport, dict):
        return False
    command = transport.get("command")
    if not isinstance(command, str) or not Path(command).is_absolute():
        return False
    # Both spellings pin the same configuration. Keep existing --config entries
    # without rewriting registrations. Custom environments/filters require review.
    return (
        value.get("enabled") is True
        and not value.get("disabled_reason")
        and value.get("enabled_tools") is None
        and not value.get("disabled_tools")
        and transport.get("type") == "stdio"
        and _absolute(command) == _absolute(mcp)
        and transport.get("args") in (
            ["--temp", str(_absolute(config_path))],
            ["--config", str(_absolute(config_path))],
        )
        and not transport.get("env")
        and not transport.get("env_vars")
        and not transport.get("cwd")
        and not transport.get("experimental_environment")
    )


def inspect_registration(
    codex: Path, mcp: Path, config_path: Path, *, run=None,
) -> str:
    """Return missing/matching/conflict/unknown without modifying Codex settings."""
    run = subprocess.run if run is None else run
    try:
        result = _call([str(codex), "mcp", "get", SERVER_NAME, "--json"], run=run)
        if result.returncode == 0:
            value = _json_output(result)
            if not isinstance(value, dict) or value.get("name") != SERVER_NAME:
                return "unknown"
            return "matching" if _matches(value, mcp, config_path) else "conflict"
        # A failed get could mean invalid config, an older CLI, or a permission
        # failure. Only a successfully parsed list with no such name proves absence.
        result = _call([str(codex), "mcp", "list", "--json"], run=run)
        if result.returncode != 0:
            return "unknown"
        values = _json_output(result)
        if not isinstance(values, list) or not all(
            isinstance(value, dict) and isinstance(value.get("name"), str)
            for value in values
        ):
            return "unknown"
        return "unknown" if any(value["name"] == SERVER_NAME for value in values) else "missing"
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, RecursionError):
        return "unknown"


def register(codex: Path, mcp: Path, config_path: Path, *, run=None) -> bool:
    """Register after the caller's approval, refusing an existing different entry.

    Recheck immediately before add to avoid overwriting a registration changed
    while the user was answering the prompt. Codex has no atomic create-only API;
    concurrent external edits during the add itself cannot be excluded.
    """
    run = subprocess.run if run is None else run
    state = inspect_registration(codex, mcp, config_path, run=run)
    if state != "missing":
        return state == "matching"
    try:
        result = _call(
            [str(codex), "mcp", "add", SERVER_NAME, "--", str(_absolute(mcp)),
             "--temp", str(_absolute(config_path))],
            run=run,
        )
        return result.returncode == 0 and inspect_registration(
            codex, mcp, config_path, run=run,
        ) == "matching"
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        return False


def probe_mcp(mcp: Path, config_path: Path, *, run=None) -> bool:
    """Check local stdio initialization and tools/list, without retrieving papers.

    These messages are processed in order by our line-oriented server, just as
    in package_smoke.py. Configuration and index readability are separate checks.
    This probe cannot establish a successful search from inside Codex.
    """
    run = subprocess.run if run is None else run
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "bibdesk-rag-setup", "version": __version__},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    try:
        completed = _call(
            [str(_absolute(mcp)), "--temp", str(_absolute(config_path))],
            run=run, input="".join(json.dumps(item) + "\n" for item in requests),
        )
        if completed.returncode or len(completed.stdout) > MAX_RESPONSE_CHARS:
            return False
        replies = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        if len(replies) != 2 or not all(
            isinstance(reply, dict) and reply.get("jsonrpc") == "2.0"
            and "error" not in reply and isinstance(reply.get("result"), dict)
            for reply in replies
        ):
            return False
        initialized, listed = replies
        result = initialized["result"]
        if (
            initialized.get("id") != 1 or listed.get("id") != 2
            or result.get("protocolVersion") != "2024-11-05"
            or not isinstance(result.get("serverInfo"), dict)
            or result["serverInfo"].get("name") != SERVER_NAME
            or not isinstance(result.get("capabilities"), dict)
            or not isinstance(result["capabilities"].get("tools"), dict)
        ):
            return False
        available = listed["result"].get("tools")
        return (
            isinstance(available, list) and len(available) == len(EXPECTED_TOOLS)
            and all(
                isinstance(tool, dict) and isinstance(tool.get("name"), str)
                and isinstance(tool.get("inputSchema"), dict)
                and isinstance(tool.get("annotations"), dict)
                and tool["annotations"].get("readOnlyHint") is True
                for tool in available
            )
            and {tool["name"] for tool in available} == EXPECTED_TOOLS
        )
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, RecursionError):
        return False
