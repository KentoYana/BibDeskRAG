#!/usr/bin/env python3
"""Optional interoperability check: run with the separately installed MCP SDK.

No SDK is imported by the application. This script creates only temporary
synthetic sources and starts the installed application as a stdio subprocess.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from mcp import Client, StdioServerParameters


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def validate(app_python: Path):
    with TemporaryDirectory(prefix="bibdesk-rag-sdk-") as directory:
        root = Path(directory).resolve()
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        for name in ("BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            env.pop(name, None)
        for name in ("PYTHONPATH", "PYTHONHOME", "PYENV_VERSION"):
            env.pop(name, None)
        bib, supplement, config = (
            root / "references.bib",
            root / "supplement.csv",
            root / "config.toml",
        )
        supplement.write_text("gene,observation\nRecQ,helicase repair\n", encoding="utf-8")
        bib.write_text(
            "@article{SDK2025,title={RecQ genetics},year={2025},"
            "doi={10.1234/sdk},Bdsk-File-1={supplement.csv}}",
            encoding="utf-8",
        )
        command = [str(app_python), "-m", "bibdesk_rag.cli"]
        for arguments in (
            ["--config", "create", str(config), "--bib", str(bib)],
            ["--temp", str(config), "--index", "update"],
        ):
            subprocess.run([*command, *arguments], env=env, check=True,
                           capture_output=True, text=True)
        index = root / "index.sqlite3"
        selection = root / "home/.config/bibdesk-rag/active-config.json"
        before = {path: sha(path) for path in (bib, supplement, config, index, selection)}
        server = StdioServerParameters(
            command=str(app_python),
            args=["-m", "bibdesk_rag.mcp_server", "--temp", str(config)],
            env=env,
        )
        checks = []
        expected_version = subprocess.run(
            [str(app_python), "-c",
             "from importlib.metadata import version; from bibdesk_rag import __version__; "
             "assert version('bibdesk-rag') == __version__; print(__version__)"],
            env=env, check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        cli_version = subprocess.run([*command, "--version"], env=env, check=True,
                                     capture_output=True, text=True, timeout=10).stdout
        assert cli_version.splitlines()[0] == f"bibdesk-rag {expected_version}"
        async with Client(server, read_timeout_seconds=10) as client:
            assert client.protocol_version == "2025-06-18"
            assert client.server_info.version == expected_version
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            assert names == {
                "search_papers",
                "search_fulltext",
                "get_paper",
                "get_attachments",
                "get_chunk",
                "build_context",
                "get_index_status",
                "semantic_search_papers",
                "similar_papers",
            }
            assert all(tool.annotations.read_only_hint for tool in listing.tools)

            async def call(name, arguments):
                response = await client.call_tool(name, arguments)
                assert not response.is_error, response
                assert len(response.content[0].text) <= 120000
                result = json.loads(response.content[0].text)
                assert result["untrusted_source"] is True
                checks.append(name)
                return result["data"]

            saved_status = await call("get_index_status", {})
            assert saved_status["freshness"] == "unverified" and saved_status["index_generation"]
            assert saved_status["counts"]["papers"] == 1
            papers = await call("search_papers", {"query": "10.1234/sdk"})
            assert papers[0]["citekey"] == "SDK2025"
            matches = await call("search_fulltext", {"query": "helicase"})
            assert matches[0]["file_path"] == str(supplement)
            assert matches[0]["row_start"] == 2
            assert matches[0]["table_provenance"]["cells"]
            paper = await call("get_paper", {"citekey": "SDK2025"})
            assert paper["doi"] == "10.1234/sdk"
            attachments = await call("get_attachments", {"citekey": "SDK2025"})
            assert attachments["items"][0]["file_path"] == str(supplement)
            chunk = await call("get_chunk", {"chunk_id": matches[0]["chunk_id"]})
            assert "helicase" in chunk["text"]
            assert chunk["citations"][0]["citekey"] == "SDK2025"
            assert all(c["complete"] for c in chunk["table_provenance"]["cells"])
            context = await call("build_context", {"query": "helicase", "max_chars": 2000})
            assert "helicase" in context["context"]
            assert len(context["context"]) <= 2000
            assert context["results"][0]["file_path"] == str(supplement)
            assert "text" not in context["results"][0]
            assert context["results"][0]["table_provenance"]["cells"]
            assert context["index"]["index_generation"] == saved_status["index_generation"]
            assert context["search_scope"]["fulltext_citekeys"] is None
            assert context["search_scope"]["fulltext_scope"] == "all_indexed_papers"
            assert context["results"][0]["content_hash"] == before[supplement]
            assert context["results"][0]["indexed_bib_hash"] == before[bib]
            broad = await call("build_context", {"query": "helicase", "scope": "fulltext", "max_chars": 2000})
            assert broad["search_scope"]["requested_scope"] == "fulltext"
            assert broad["search_scope"]["fulltext_status"] == "matched"
            assert broad["results"][0]["citekey"] == "SDK2025"
            strict = await call("build_context", {"query": "helicase", "scope": "fulltext",
                                                   "metadata_query": "NoSuchSyntheticPaper"})
            assert strict["returned"] == 0 and strict["search_scope"]["fulltext_status"] == "not_searched"
            invalid_scope = await client.call_tool("build_context", {"query": "x", "scope": "metadata"})
            assert invalid_scope.is_error
            rejected = await client.call_tool("get_chunk", {"chunk_id": 1, "max_chars": 20001})
            assert rejected.is_error
            optional = await client.call_tool("semantic_search_papers", {"query": "DNA repair"})
            assert optional.is_error and "disabled" in optional.content[0].text
            checks.append("semantic_search_papers (disabled, no model download)")
            disabled_similar = await client.call_tool("similar_papers", {"citekey": "SDK2025"})
            assert disabled_similar.is_error and "semantic_disabled" in disabled_similar.content[0].text
            checks.append("similar_papers (disabled, no model load)")
            report = {
                "mcp_sdk": version("mcp"),
                "protocol": client.protocol_version,
                "server_version": client.server_info.version,
                "tools_passed": checks,
                "invalid_argument_rejected": True,
                "response_bounds_checked": True,
                "installed_metadata_cli_server_versions_match": True,
            }
        assert {path: sha(path) for path in before} == before
        report["source_and_index_hashes_unchanged"] = True
        report["configuration_and_selection_hashes_unchanged"] = True
        try:
            from .similarity_fixture import create_saved_fixture
        except ImportError:
            from similarity_fixture import create_saved_fixture

        saved_config, saved_index, saved_env = create_saved_fixture(command, root / "saved-vectors", env)
        saved_paths = [p for p in saved_config.parent.rglob("*") if p.is_file()]
        saved_before = {path: sha(path) for path in saved_paths}
        saved_server = StdioServerParameters(command=str(app_python),
            args=["-m", "bibdesk_rag.mcp_server", "--temp", str(saved_config)], env=saved_env)
        async with Client(saved_server, read_timeout_seconds=10) as client:
            response = await client.call_tool("similar_papers", {"citekey": "SavedSeed", "top": 2})
            assert not response.is_error, response
            related = json.loads(response.content[0].text)["data"]
            assert [p["citekey"] for p in related["results"]] == ["SavedRelated", "SavedOther"]
            assert related["results"][0]["title_only"] and related["candidates"]["missing_vectors"] == 1
            filtered = await client.call_tool("similar_papers", {"citekey": "SavedSeed", "year": "2026"})
            assert not filtered.is_error and len(json.loads(filtered.content[0].text)["data"]["results"]) == 1
            assert related["assessment"]["calibrated"]
            rejected = await client.call_tool("similar_papers", {"citekey": "SavedUnrelatedControl"})
            rejection = json.loads(rejected.content[0].text)["data"]
            assert not rejected.is_error and rejection["results"] == []
            assert rejection["assessment"]["decision"] == "insufficient_evidence"
        assert saved_before == {path: sha(path) for path in saved_paths}
        report["saved_similarity_fixture_passed_without_model"] = True
        report["transport"] = "stdio subprocess; official SDK default auto negotiation"
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app-python",
        type=Path,
        required=True,
        help="Python executable in the installed application's environment",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(validate(args.app_python.absolute())), indent=2))


if __name__ == "__main__":
    main()
