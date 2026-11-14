#!/usr/bin/env python3
"""Check two installed releases against a temporary generated library, offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def validate(old_python: Path, app_python: Path, old_version: str) -> dict:
    with TemporaryDirectory(prefix="bibdesk-rag-upgrade-") as directory:
        root = Path(directory).resolve()
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        for name in ("BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME",
                     "XDG_DATA_HOME", "PYTHONPATH", "PYTHONHOME", "PYENV_VERSION"):
            env.pop(name, None)
        bib, csv, config, index = (root / name for name in
                                   ("refs.bib", "evidence.csv", "config.toml", "index.sqlite3"))
        csv.write_text("gene,value\nRecQ,42\n")
        bib.write_text("@article{Upgrade,title={RecQ generated evidence},"
                       "doi={10.1234/upgrade},Bdsk-File-1={evidence.csv}}")

        def run(python, *args, input=None):
            return subprocess.run([str(python), *args], input=input, env=env, cwd=root,
                                  check=True, capture_output=True, text=True, timeout=60).stdout

        def cli(python, *args):
            return run(python, "-m", "bibdesk_rag.cli", *args)

        def data(python, *args):
            return json.loads(cli(python, "--temp", str(config), *args, "--format", "json"))

        def hashes(paths):
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

        assert cli(old_python, "--version").splitlines()[0] == f"bibdesk-rag {old_version}"
        cli(old_python, "--config", "create", str(config), "--bib", str(bib))
        data(old_python, "--index", "update")
        selection = root / "home/.config/bibdesk-rag/active-config.json"
        sources = hashes([bib, csv, config, selection])
        persisted = hashes([index])
        old_paper = data(old_python, "--paper", "show", "Upgrade")
        old_hits = data(old_python, "--paper", "search", "RecQ", "--scope", "fulltext")

        # Read the old index before the candidate performs any update/migration.
        assert data(app_python, "--paper", "show", "Upgrade") == old_paper
        assert data(app_python, "--paper", "search", "RecQ", "--scope", "fulltext") == old_hits
        assert json.loads(cli(app_python, "--config", "path", "--format", "json"))["config"] == str(config)
        assert persisted == hashes([index])

        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "upgrade-validation", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "get_paper", "arguments": {"citekey": "Upgrade"}}},
        ]
        # Preserve the old, hidden server-only --config PATH spelling.
        replies = [json.loads(line) for line in run(
            app_python, "-m", "bibdesk_rag.mcp_server", "--config", str(config),
            input="".join(json.dumps(r) + "\n" for r in requests),
        ).splitlines()]
        assert replies[0]["result"]["protocolVersion"] == "2024-11-05"
        assert not replies[-1]["result"]["isError"]
        assert json.loads(replies[-1]["result"]["content"][0]["text"])["data"]["citekey"] == "Upgrade"
        assert persisted == hashes([index])

        report = data(app_python, "--index", "update")
        assert report["files_extracted"] == 0 and report["files_reused"] == 1
        assert data(app_python, "--paper", "show", "Upgrade") == old_paper
        assert data(app_python, "--paper", "search", "RecQ", "--scope", "fulltext") == old_hits
        assert data(app_python, "--index", "check")["ok"]
        assert sources == hashes([bib, csv, config, selection])

        # An actual subsequent source change must be observed incrementally.
        csv.write_text("gene,value\nChanged,99\n")
        changed_sources = hashes([bib, csv, config, selection])
        changed = data(app_python, "--index", "update")
        assert changed["files_extracted"] == 1
        assert data(app_python, "--paper", "search", "Changed", "--scope", "fulltext")
        assert not data(app_python, "--paper", "search", "RecQ", "--scope", "fulltext")
        assert changed_sources == hashes([bib, csv, config, selection])
        return {
            "old_version": old_version,
            "candidate": cli(app_python, "--version").splitlines()[0],
            "old_index_read_before_update": True,
            "legacy_mcp_arguments_and_protocol": True,
            "unchanged_attachments_reused": True,
            "logical_data_preserved": True,
            "sources_configuration_selection_unchanged": True,
            "subsequent_incremental_update": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-python", type=Path, required=True)
    parser.add_argument("--app-python", type=Path, required=True)
    parser.add_argument("--old-version", required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.old_python.absolute(), args.app_python.absolute(),
                              args.old_version), indent=2))


if __name__ == "__main__":
    main()
