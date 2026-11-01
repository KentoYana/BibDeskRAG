import hashlib
from io import StringIO
import json
import subprocess
import sys

import pytest

from bibdesk_rag.config import init_config, load_config
from bibdesk_rag.database import connect
from bibdesk_rag.indexer import index_library
from bibdesk_rag.mcp_server import MAX_INPUT_CHARS, MCPServer, TOOLS, serve


def initialize(server, version="2025-06-18"):
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "synthetic-test", "version": "1"},
            },
        }
    )
    assert "error" not in response
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return response


def tool(server, name, **arguments):
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert "error" not in response
    result = response["result"]
    payload = json.loads(result["content"][0]["text"])
    assert result["isError"] is False, payload
    assert payload["untrusted_source"] is True
    return payload["data"]


@pytest.fixture
def mcp_fixture(tmp_path):
    supplement = tmp_path / "supplement.csv"
    supplement.write_text("gene,observation\nRecQ,helicase repair\n", encoding="utf-8")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{Example2025,title={RecQ genetics},author={Smith, Alice},"
        "year={2025},doi={10.1234/recq},Bdsk-File-1={supplement.csv}}"
    )
    config_path = tmp_path / "app" / "config.toml"
    init_config(bib, config_path)
    index_library(load_config(config_path))
    return config_path, bib, supplement


def test_all_six_tools_preserve_sources_and_index(mcp_fixture):
    config_path, bib, supplement = mcp_fixture
    db_path = load_config(config_path).database
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (bib, supplement, db_path)}
    server = MCPServer(config_path)
    response = initialize(server)
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert "untrusted" in response["result"]["instructions"]
    listing = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert len(listing["result"]["tools"]) == 6
    assert all(item["annotations"]["readOnlyHint"] for item in listing["result"]["tools"])
    papers = tool(server, "search_papers", query="10.1234/recq")
    assert papers[0]["citekey"] == "Example2025"
    matches = tool(server, "search_fulltext", query="helicase", citekeys=["Example2025"])
    assert matches[0]["file_path"] == str(supplement)
    assert matches[0]["row_start"] == 2
    paper = tool(server, "get_paper", citekey="Example2025")
    assert paper["doi"] == "10.1234/recq"
    attachments = tool(server, "get_attachments", citekey="Example2025", limit=1)
    assert attachments["total"] == 1
    assert attachments["items"][0]["file_path"] == str(supplement)
    chunk = tool(server, "get_chunk", chunk_id=matches[0]["chunk_id"], max_chars=8)
    assert len(chunk["text"]) <= 8
    assert chunk["truncated"] is True
    assert chunk["citations"][0]["citekey"] == "Example2025"
    context = tool(server, "build_context", query="helicase", max_chars=1000)
    assert len(context["context"]) <= 1000
    assert context["results"][0]["row_start"] == 2
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


@pytest.mark.parametrize(
    "name,args",
    [
        ("search_papers", {"query": "RecQ", "top": True}),
        ("search_papers", {"query": "RecQ", "top": 101}),
        ("search_fulltext", {"query": "RecQ", "citekeys": ["x"] * 101}),
        ("get_paper", {"citekey": "Example2025", "write": True}),
        ("get_chunk", {"chunk_id": 1, "max_chars": 20001}),
        ("build_context", {"query": "x", "max_chars": 100001}),
    ],
)
def test_bad_tool_arguments_are_bounded_tool_errors(mcp_fixture, name, args):
    server = MCPServer(mcp_fixture[0])
    initialize(server)
    result = server.handle(
        {
            "jsonrpc": "2.0",
            "id": "req",
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
    )["result"]
    assert result["isError"] is True


def test_readonly_connection_used_by_mcp(mcp_fixture, monkeypatch):
    import bibdesk_rag.mcp_server as module

    original = module.connect
    calls = []

    def checked_connect(path, **kwargs):
        assert kwargs == {"readonly": True}
        connection = original(path, **kwargs)
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        calls.append(path)
        return connection

    monkeypatch.setattr(module, "connect", checked_connect)
    server = MCPServer(mcp_fixture[0])
    initialize(server)
    tool(server, "get_paper", citekey="Example2025")
    assert calls


def test_lifecycle_errors_version_negotiation_and_notifications():
    server = MCPServer()
    before = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert before["error"]["code"] == -32002
    initialized = initialize(server, "2099-01-01")
    assert initialized["result"]["protocolVersion"] == "2025-06-18"
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    assert (
        server.handle({"jsonrpc": "2.0", "id": 2, "method": "write_paper"})["error"]["code"]
        == -32601
    )
    assert (
        server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "delete"}}
        )["error"]["code"]
        == -32602
    )
    assert server.handle([])["error"]["code"] == -32600
    assert (
        server.handle({"jsonrpc": "2.0", "id": None, "method": "ping"})["error"]["code"] == -32600
    )


def test_stdio_framing_bad_json_and_oversized_input():
    reader = StringIO(
        "not JSON\n"
        + "x" * (MAX_INPUT_CHARS + 10)
        + "\n"
        + '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
    )
    writer = StringIO()
    serve(MCPServer(), reader, writer)
    results = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert [item["error"]["code"] for item in results[:2]] == [-32700, -32700]
    assert results[2] == {"jsonrpc": "2.0", "id": 2, "result": {}}


def test_huge_metadata_is_truncated_explicitly(mcp_fixture):
    config_path = mcp_fixture[0]
    with connect(load_config(config_path).database) as db:
        db.execute("UPDATE papers SET abstract=?", ("A" * 200000,))
    server = MCPServer(config_path)
    initialize(server)
    result = tool(server, "get_paper", citekey="Example2025", max_chars=500)
    assert result["citekey"] == "Example2025"
    assert result["doi"] == "10.1234/recq"
    assert result["truncated"] is True
    assert "abstract" in result["truncated_fields"]
    assert len(result["abstract"]) <= 500


def test_large_context_avoids_duplicate_excerpt_payload(mcp_fixture, monkeypatch):
    import bibdesk_rag.context as module

    text = "evidence " * 10000
    monkeypatch.setattr(
        module,
        "build_context",
        lambda *args, **kwargs: {
            "context": text,
            "results": [{"citekey": "Example2025", "text": text}],
            "unverified": ["Synthetic validation"],
        },
    )
    server = MCPServer(mcp_fixture[0])
    initialize(server)
    result = tool(server, "build_context", query="evidence", max_chars=100000)
    assert result["context"] == text
    assert result["results"] == [{"citekey": "Example2025"}]
    assert result["unverified"] == ["Synthetic validation"]


def test_long_list_truncation_is_explicit(mcp_fixture):
    config_path = mcp_fixture[0]
    with connect(load_config(config_path).database) as db:
        db.execute("UPDATE papers SET groups_json=?", (json.dumps(["group"] * 101),))
    server = MCPServer(config_path)
    initialize(server)
    result = tool(server, "get_paper", citekey="Example2025")
    assert len(result["groups"]) == 100
    assert result["truncated"] is True
    assert "groups" in result["truncated_fields"]


def test_entrypoint_communicates_real_stdio(mcp_fixture):
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_fulltext", "arguments": {"query": "helicase"}},
        },
    ]
    result = subprocess.run(
        [sys.executable, "-m", "bibdesk_rag.mcp_server", "--config", str(mcp_fixture[0])],
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(responses) == 2
    assert responses[1]["result"]["isError"] is False
    assert "helicase" in responses[1]["result"]["content"][0]["text"]


def test_tool_names_are_exact():
    assert {tool["name"] for tool in TOOLS} == {
        "search_papers",
        "search_fulltext",
        "get_paper",
        "get_attachments",
        "get_chunk",
        "build_context",
    }
