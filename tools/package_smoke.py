#!/usr/bin/env python3
"""Exercise installed CLI/MCP with generated data; also check reinstall persistence."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess


def synthetic_pdf() -> bytes:
    """Make two valid text pages without adding a PDF-generation dependency."""
    first = b"BT /F1 12 Tf 72 720 Td (Synthetic introductory page.) Tj ET\n"
    second = b"BT /F1 12 Tf 72 720 Td (RecQ helicase synthetic evidence on page two.) Tj ET\n"
    page = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R 6 0 R] /Count 2 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        page % 5,
        b"<< /Length %d >>\nstream\n" % len(first) + first + b"endstream",
        page % 7,
        b"<< /Length %d >>\nstream\n" % len(second) + second + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
               f"startxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", default="bibdesk-rag")
    parser.add_argument("--mcp-command", default="bibdesk-rag-mcp")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    workdir = args.workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["BIBDESK_RAG_HOME"] = str(workdir / "data")
    env.pop("BIBDESK_RAG_CONFIG", None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYENV_VERSION", None)
    bib = workdir / "refs.bib"
    supplementary = workdir / "supplement.csv"
    paper_pdf = workdir / "paper.pdf"
    fixture_paths = (bib, supplementary, paper_pdf, workdir / "data")
    if not args.verify_existing and any(p.exists() for p in fixture_paths):
        parser.error("use a fresh workdir; existing fixtures/index will not be overwritten")
    if args.verify_existing and not all(p.exists() for p in fixture_paths):
        parser.error("--verify-existing requires a previously completed synthetic smoke test")

    def hashes_for(paths) -> dict[str, str]:
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    def source_hashes() -> dict[str, str]:
        return hashes_for((bib, supplementary, paper_pdf))

    def cli(*command: str) -> str:
        completed = subprocess.run([args.command, *command], env=env, check=True,
                                   text=True, capture_output=True, timeout=60)
        return completed.stdout

    def check_unattended_setup(config_path: Path) -> None:
        before = hashes_for(path for path in workdir.rglob("*") if path.is_file())
        completed = subprocess.run(
            [args.command, "--config", str(config_path), "setup"], env=env,
            input="This input must never be read.\n", text=True, capture_output=True,
            timeout=10,
        )
        assert completed.returncode == 1, completed
        assert "init" in completed.stderr and "index" in completed.stderr, completed.stderr
        assert "Traceback" not in completed.stderr, completed.stderr
        after = hashes_for(path for path in workdir.rglob("*") if path.is_file())
        assert before == after, "Non-TTY setup changed synthetic files"

    assert "setup" in cli("--help")
    assert "setup" in cli("setup", "--help")
    check_unattended_setup(workdir / "unattended/config.toml")
    assert not (workdir / "unattended").exists(), "Non-TTY setup created a directory"

    if not args.verify_existing:
        supplementary.write_text("gene,result\nRecQ,observed\nmus-9,measured\n")
        paper_pdf.write_bytes(synthetic_pdf())
        linked = base64.b64encode(plistlib.dumps({"relativePath": "supplement.csv"},
                                               fmt=plistlib.FMT_BINARY)).decode()
        linked_pdf = base64.b64encode(plistlib.dumps({"relativePath": "paper.pdf"},
                                                   fmt=plistlib.FMT_BINARY)).decode()
        bib.write_text("@article{Test2026,\n"
                       "  title={RecQ helicase and DNA repair},\n"
                       "  author={Researcher, Example}, year={2026},\n"
                       "  doi={10.1234/synthetic-test},\n"
                       f"  Bdsk-File-1={{{linked}}},\n"
                       f"  Bdsk-File-2={{{linked_pdf}}}\n" + "}\n"
                       "@article{Other2026,\n"
                       "  title={Unrelated synthetic reference}, year={2026},\n"
                       f"  Bdsk-File-1={{{linked_pdf}}}\n" + "}\n")
        hashes = source_hashes()
        cli("init", "--bib", str(bib))
        cli("index")
    else:
        hashes = source_hashes()
    assert "bibdesk" in cli("--version").lower()
    assert "search" in cli("--help")
    found = json.loads(cli("search", "RecQ", "--scope", "fulltext", "--json"))
    assert "Test2026" in json.dumps(found), found
    assert "supplement.csv" in json.dumps(found), found
    pdf_hits = [hit for hit in found if hit["source_type"] == "pdf"]
    assert pdf_hits and all(hit["page_start"] == hit["page_end"] == 2
                            for hit in pdf_hits), found
    assert "RecQ" in cli("get", "Test2026", "--format", "bibtex")
    diagnosis = json.loads(cli("doctor", "--json"))
    assert diagnosis["ok"], diagnosis
    cli("update")
    assert hashes == source_hashes()
    persisted = (workdir / "data/config.toml", workdir / "data/index.sqlite3")
    check_unattended_setup(persisted[0])
    before_mcp = hashes_for(persisted)

    def mcp_request(method: str, params: dict) -> dict:
        # A separate bounded process per step keeps stdio timeout handling portable.
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "package-smoke", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
        ]
        completed = subprocess.run([args.mcp_command], env=env, check=True, text=True,
                                   input="".join(json.dumps(r) + "\n" for r in requests),
                                   capture_output=True, timeout=60)
        replies = {r["id"]: r for line in completed.stdout.splitlines()
                   if (r := json.loads(line)).get("id") is not None}
        assert "result" in replies[1], replies
        assert "result" in replies[2], replies
        return replies[2]["result"]

    def mcp_tool(name: str, arguments: dict):
        result = mcp_request("tools/call", {"name": name, "arguments": arguments})
        assert not result.get("isError"), result
        wrapped = json.loads(result["content"][0]["text"])
        assert wrapped["untrusted_source"], wrapped
        return wrapped["data"]

    tools = mcp_request("tools/list", {})["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {"search_papers", "search_fulltext", "get_paper", "get_attachments",
                     "get_chunk", "build_context"}, names
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools), tools
    papers = mcp_tool("search_papers", {"query": "RecQ", "top": 5})
    assert [paper["citekey"] for paper in papers] == ["Test2026"], papers
    hits = mcp_tool("search_fulltext", {"query": "RecQ", "top": 5, "per_paper": 2,
                                     "citekeys": [paper["citekey"] for paper in papers]})
    assert hits and all(hit["citekey"] == "Test2026" for hit in hits), hits
    assert any(hit["file_path"] == str(supplementary) and hit["row_start"] == 2
               for hit in hits), hits
    evidence = next(hit for hit in hits if hit["source_type"] == "pdf")
    assert evidence["file_path"] == str(paper_pdf), evidence
    assert evidence["page_start"] == evidence["page_end"] == 2, evidence
    assert evidence["doi"] == "10.1234/synthetic-test", evidence
    assert isinstance(evidence["chunk_id"], int) and evidence["chunk_id"] > 0, evidence
    chunk = mcp_tool("get_chunk", {"chunk_id": evidence["chunk_id"], "max_chars": 200})
    assert chunk["chunk_id"] == evidence["chunk_id"], chunk
    assert chunk["file_path"] == str(paper_pdf), chunk
    assert chunk["page_start"] == chunk["page_end"] == 2, chunk
    assert "RecQ" in chunk["text"] and len(chunk["text"]) <= 200, chunk
    assert any(citation["citekey"] == "Test2026"
               and citation["doi"] == "10.1234/synthetic-test"
               for citation in chunk["citations"]), chunk
    assert hashes == source_hashes(), "MCP changed synthetic source files"
    assert before_mcp == hashes_for(persisted), "MCP changed configuration or index"
    print("Installed CLI, setup help/non-TTY safety, PDF page citations, CSV, "
          "source immutability, persisted index and read-only MCP passed")


if __name__ == "__main__":
    main()
