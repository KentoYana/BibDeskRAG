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
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from mcp import Client, StdioServerParameters


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def validate(app_python: Path):
    with TemporaryDirectory(prefix="bibdesk-rag-sdk-") as directory:
        root = Path(directory).resolve()
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
        command = [str(app_python), "-m", "bibdesk_rag.cli", "--config", str(config)]
        for arguments in (["init", "--bib", str(bib)], ["index"]):
            subprocess.run([*command, *arguments], check=True, capture_output=True, text=True)
        index = root / "index.sqlite3"
        before = {path: sha(path) for path in (bib, supplement, index)}
        server = StdioServerParameters(
            command=str(app_python),
            args=["-m", "bibdesk_rag.mcp_server", "--config", str(config)],
        )
        checks = []
        async with Client(server, read_timeout_seconds=10) as client:
            assert client.protocol_version == "2025-06-18"
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            assert names == {
                "search_papers",
                "search_fulltext",
                "get_paper",
                "get_attachments",
                "get_chunk",
                "build_context",
            }
            assert all(tool.annotations.read_only_hint for tool in listing.tools)

            async def call(name, arguments):
                response = await client.call_tool(name, arguments)
                assert not response.is_error, response
                result = json.loads(response.content[0].text)
                assert result["untrusted_source"] is True
                checks.append(name)
                return result["data"]

            papers = await call("search_papers", {"query": "10.1234/sdk"})
            assert papers[0]["citekey"] == "SDK2025"
            matches = await call("search_fulltext", {"query": "helicase"})
            assert matches[0]["file_path"] == str(supplement)
            assert matches[0]["row_start"] == 2
            paper = await call("get_paper", {"citekey": "SDK2025"})
            assert paper["doi"] == "10.1234/sdk"
            attachments = await call("get_attachments", {"citekey": "SDK2025"})
            assert attachments["items"][0]["file_path"] == str(supplement)
            chunk = await call("get_chunk", {"chunk_id": matches[0]["chunk_id"]})
            assert "helicase" in chunk["text"]
            assert chunk["citations"][0]["citekey"] == "SDK2025"
            context = await call("build_context", {"query": "helicase", "max_chars": 2000})
            assert "helicase" in context["context"]
            assert len(context["context"]) <= 2000
            assert context["results"][0]["file_path"] == str(supplement)
            assert "text" not in context["results"][0]
            rejected = await client.call_tool("get_chunk", {"chunk_id": 1, "max_chars": 20001})
            assert rejected.is_error
            report = {
                "mcp_sdk": version("mcp"),
                "protocol": client.protocol_version,
                "server_version": client.server_info.version,
                "tools_passed": checks,
                "invalid_argument_rejected": True,
            }
        assert {path: sha(path) for path in before} == before
        report["source_and_index_hashes_unchanged"] = True
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
