"""Only generated libraries/PDFs; no personal bibliography or real Skim launch."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
from http.client import HTTPConnection
from importlib.resources import files
import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import threading
import time

import pytest

from bibdesk_rag import cli, skim, web, web_runtime
from bibdesk_rag.cli_arguments import parse_args
from bibdesk_rag.config import activate_config, init_config, load_config
from bibdesk_rag.indexer import index_library


@pytest.fixture
def web_library(tmp_path, monkeypatch):
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("BIBDESK_RAG_CONFIG", raising=False)
    make_pdf = runpy.run_path(str(Path(__file__).parents[1] / "tools/package_smoke.py"))["synthetic_pdf"]
    for name in ("論文 ' $() ` test.pdf", "supplement.pdf"):
        (tmp_path / name).write_bytes(make_pdf())
    (tmp_path / "table.csv").write_text("gene,value\nRecQ,42\n")
    bib = tmp_path / "library.bib"
    bib.write_text(
        "@article{One,title={RecQ helicase},author={Example, Alice},year={2026},"
        "doi={10.1234/test},abstract={<script>alert(1)</script> DNA repair},"
        "Bdsk-File-1={論文 ' $() ` test.pdf},Bdsk-File-2={supplement.pdf},"
        "Bdsk-File-3={table.csv},Bdsk-File-4={missing.pdf}}\n"
        "@article{Two,title={RecQ mechanisms},author={Other, Bob},year={2025},"
        "Bdsk-File-1={supplement.pdf}}\n", encoding="utf-8")
    path = tmp_path / "settings/config.toml"
    init_config(bib, path, tmp_path / "data")
    config = load_config(path)
    index_library(config)
    return path, config


@contextmanager
def running(app):
    server = web.bind_server(app, 0)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02})
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def request(server, app, path, body=None, *, method="POST", headers=None, internal=False):
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    auth = ({"Authorization": "Bearer " + app.owner_token} if internal else
            {"Origin": f"http://127.0.0.1:{server.server_port}", "X-CSRF-Token": app.csrf})
    auth["Content-Type"] = "application/json"
    if headers:
        for key, value in headers.items():
            if value is None:
                auth.pop(key, None)
            else:
                auth[key] = value
    conn.request(method, path, None if method == "GET" else json.dumps(body or {}), auth)
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


@pytest.mark.parametrize("body", [
    {"query": "RecQ", "scope": "metadata"}, {"query": "RecQ", "scope": "fulltext", "per_paper": 1},
    {"query": "RecQ", "scope": "all", "top": 3},
    {"query": "", "scope": "metadata", "doi": "https://doi.org/10.1234/test"},
    {"query": "", "scope": "metadata", "citekeys": ["One"]},
    {"query": "RecQ", "scope": "fulltext", "citekeys": ["Two"]},
    {"query": "RecQ", "scope": "all", "metadata_query": "mechanisms"},
    {"query": "RecQ", "scope": "metadata", "author": "Alice", "year": "2026"},
    {"query": "相同組換え"}, {"query": "no-such-result"}, {"query": "-option $(touch /tmp/no)"},
])
def test_search_matches_cli_service_exactly_and_preserves_ranking(web_library, body):
    path, config = web_library
    app = web.WebApp(config, path)
    args = web.search_arguments(body)
    with app.database() as db:
        expected = cli.paper_result(web.SQLiteSearch(db), args)
    result = app.search(body)
    assert result["hit_count"] == len(expected)
    assert [c["paper"]["citekey"] for c in result["papers"]] == list(dict.fromkeys(h["citekey"] for h in expected))
    for card in result["papers"]:
        assert card["hits"] == [h for h in expected if h["citekey"] == card["paper"]["citekey"]]
    assert result["paper_count"] == len(result["papers"])


@pytest.mark.parametrize("body", [
    {"top": True}, {"top": 101}, {"top": 0}, {"per_paper": 11}, {"query": []},
    {"query": "x" * 2001}, {"path": "/etc/passwd"}, {"citekeys": "One"},
    {"citekeys": []}, {"citekeys": ["x"] * 101}, {"scope": "metadata", "citekeys": ["One", "Two"]},
    {"scope": "fulltext", "doi": "10.1234/test"}, {"scope": "metadata", "per_paper": 2},
    {"scope": "fulltext", "metadata_query": "RecQ"}, {"citekeys": ["One"], "metadata_query": "RecQ"},
    {"mode": "semantic", "scope": "all"}, {"mode": "semantic", "author": "Alice"},
])
def test_input_validation_reuses_cli_restrictions(body):
    with pytest.raises(ValueError):
        web.search_arguments(body)


def test_api_auth_xss_assets_and_readonly_hashes(web_library):
    path, config = web_library
    app = web.WebApp(config, path)
    paths = [path, config.bib, config.database, *config.bib.parent.glob("*.pdf")]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with running(app) as server:
        code, headers, html = request(server, app, "/", method="GET")
        assert code == 200 and app.csrf.encode() in html
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["Cache-Control"] == "no-store"
        assert headers["Referrer-Policy"] == "no-referrer"
        for asset in ("/app.js", "/app.css"):
            assert request(server, app, asset, method="GET")[0] == 200
        code, headers, data = request(server, app, "/api/search", {"query": "RecQ"})
        assert code == 200
        assert b"<script>alert(1)</script>" in data
        assert "Access-Control-Allow-Origin" not in headers
        assert request(server, app, "/api/paper", {"citekey": "One"})[0] == 200
        assert request(server, app, "/api/status")[0] == 200
        for route in ("/api/attachments/1/open", "/api/search", "/api/paper", "/api/status", "/api/initial"):
            for headers in ({"Origin": "https://evil.example"}, {"Origin": None},
                            {"X-CSRF-Token": None}, {"Host": f"evil.example:{server.server_port}"}):
                assert request(server, app, route, headers=headers)[0] == 403
            assert request(server, app, route, method="GET")[0] == 404
        assert request(server, app, "/internal/health", internal=True)[0] == 200
        assert request(server, app, "/internal/health", internal=True, headers={"Authorization": None})[0] == 403
        assert request(server, app, "/internal/health", internal=True,
                       headers={"Origin": f"http://127.0.0.1:{server.server_port}"})[0] == 403
        assert request(server, app, "/../library.bib", method="GET")[0] == 404
        assert request(server, app, "/api/search", {"query": "x" * 40000})[0] == 413
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    js = files("bibdesk_rag").joinpath("resources/web/app.js").read_text()
    assert "innerHTML" not in js and "localStorage" not in js and "eval(" not in js


def test_attachment_membership_and_hit_target(web_library, monkeypatch):
    path, config = web_library
    app = web.WebApp(config, path)
    result = app.search({"query": "RecQ", "scope": "fulltext"})
    card = result["papers"][0]
    assert len(card["attachments"]) == 4
    calls = []
    monkeypatch.setattr(skim, "open_pdf", lambda path, page: calls.append((path, page)) or {"opened": True})
    for hit in card["hits"]:
        if hit["source_type"] == "pdf":
            app.open_attachment(hit["attachment_id"], {"page": hit["page_start"]})
            assert calls[-1] == (Path(hit["file_path"]), hit["page_start"])
    with pytest.raises(KeyError):
        app.open_attachment(999999, {})
    for body in ({"page": True}, {"page": 0}, {"page": None}, {"path": "/tmp/other.pdf"}):
        with pytest.raises(ValueError):
            app.open_attachment(1, body)
    other_bib = config.bib.parent / "other.bib"
    other_bib.write_text("@article{Other,title={Other}}")
    with pytest.raises(ValueError):
        web.WebApp(replace(config, bib=other_bib), path)


def test_semantic_disabled_loading_error_and_backend_reuse(web_library, monkeypatch):
    path, config = web_library
    app = web.WebApp(config, path)
    with pytest.raises(ValueError, match="disabled"):
        app.search({"query": "DNA", "mode": "semantic"})
    config.semantic.enabled = True
    from bibdesk_rag import embeddings, semantic
    created = []

    def backend(options):
        created.append(object())
        return created[-1]

    def search(config, query, limit, *, backend):
        assert backend is created[0]
        assert query == "相同組換え"
        return []

    monkeypatch.setattr(embeddings, "SentenceTransformerBackend", backend)
    monkeypatch.setattr(semantic, "semantic_search", search)
    for _ in range(2):
        assert app.search({"query": "相同組換え", "mode": "semantic"})["hit_count"] == 0
    assert len(created) == 1
    app.backend = None

    def fail(options):
        raise ValueError("Model is not cached. Run bibdesk-rag --semantic download.")

    monkeypatch.setattr(embeddings, "SentenceTransformerBackend", fail)
    with pytest.raises(ValueError, match="not cached"):
        app.search({"query": "DNA", "mode": "semantic"})
    assert app.backend is None


@pytest.mark.parametrize("page", [None, 2])
def test_skim_fixed_commands_data_arguments_and_no_source_writes(web_library, monkeypatch, page):
    _, config = web_library
    path = next(config.bib.parent.glob("論文*.pdf"))
    before = path.read_bytes()
    calls = []
    monkeypatch.setattr(sys, "platform", "darwin")

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs == {"check": True, "capture_output": True, "timeout": 10}

    monkeypatch.setattr(skim.subprocess, "run", run)
    result = skim.open_pdf(path, page)
    assert calls[0] == ["/usr/bin/open", "-a", "Skim", str(path.resolve())]
    if page:
        assert calls[1][0] == "/usr/bin/osascript"
        assert calls[1][-2:] == [str(path.resolve()), "2"]
        assert "on run argv" in Path(calls[1][1]).read_text()
        assert str(path) not in Path(calls[1][1]).read_text()
    assert result["page_navigated"] == bool(page)
    assert path.read_bytes() == before


def test_skim_failures_are_english_and_page_failure_preserves_open(web_library, monkeypatch):
    _, config = web_library
    path = next(config.bib.parent.glob("論文*.pdf"))
    monkeypatch.setattr(sys, "platform", "darwin")

    def run(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv, stderr="日本語のOSエラー")

    monkeypatch.setattr(skim.subprocess, "run", run)
    with pytest.raises(ValueError, match="Check that Skim is installed"):
        skim.open_pdf(path)

    def fail_page(argv, **kwargs):
        if argv[0] == "/usr/bin/osascript":
            raise subprocess.TimeoutExpired(argv, 10)

    monkeypatch.setattr(skim.subprocess, "run", fail_page)
    result = skim.open_pdf(path, 2)
    assert result["opened"] and not result["page_navigated"]
    assert "could not navigate to page 2" in result["message"]
    for bad in (config.bib, path.parent / "missing.pdf"):
        with pytest.raises(ValueError):
            skim.open_pdf(bad)


def test_initial_request_one_use_expiry_and_bounds(web_library, monkeypatch):
    path, config = web_library
    app = web.WebApp(config, path)
    for query in ("", "相同組換え", "-x ' \" $(touch sentinel) `echo hi`\nnext"):
        key = app.initial_request(query)["request_id"]
        assert query not in key or not query
        assert app.consume_request(key) == {"query": query}
        with pytest.raises(ValueError, match="already used"):
            app.consume_request(key)
    key = app.initial_request("RecQ")["request_id"]
    app.requests[key] = (time.monotonic() - 1, "RecQ")
    with pytest.raises(ValueError, match="expired"):
        app.consume_request(key)
    for _ in range(100):
        app.initial_request("RecQ")
    with pytest.raises(ValueError, match="Too many"):
        app.initial_request("RecQ")


@pytest.mark.parametrize("argv", [
    ["--web", "--index", "update"], ["--web", "--port", "0"], ["--web", "--port", "65536"],
    ["--web", "--top", "2"], ["--web-open=x", "--no-browser"], ["--web-stop", "--port", "1234"],
    ["--web", "--format", "json"], ["--web-open=x", "--web-stop"],
])
def test_web_cli_rejects_irrelevant_options(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_web_cli_pin_and_config_selection(web_library, monkeypatch):
    path, config = web_library
    calls = []
    monkeypatch.setattr(web_runtime, "serve", lambda path, **kwargs: calls.append(path))
    activate_config(path)
    assert cli.main(["--web"]) == 0
    other = path.parent / "other.toml"
    other.write_text(path.read_text())
    monkeypatch.setenv("BIBDESK_RAG_CONFIG", str(other))
    assert cli.main(["--web"]) == 0
    assert cli.main(["--temp", str(path), "--web"]) == 0
    assert calls == [path, other, path]
    app = web.WebApp(config, path)
    activate_config(other)
    assert app.config_path == path and app.config.bib == config.bib


def test_port_conflicts_and_default_fallback(web_library, monkeypatch):
    path, config = web_library
    app = web.WebApp(config, path)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(ValueError, match="already in use"):
            web.bind_server(app, port)
        original = web.LocalServer

        def mapped(address, handler):
            return original((address[0], port if address[1] == 8765 else address[1]), handler)

        monkeypatch.setattr(web, "LocalServer", mapped)
        server = web.bind_server(app)
        assert server.server_port != port
        server.server_close()


def test_runtime_private_discovery_stale_information_and_real_lifecycle(web_library, monkeypatch):
    path, config = web_library
    runtime = web_runtime.Runtime(path, config)
    assert runtime.directory.stat().st_mode & 0o777 == 0o700
    urls = []
    monkeypatch.setattr(web_runtime, "open_browser", urls.append)
    query = "相同組換え ' $(touch sentinel) `echo test`\n-next"
    try:
        assert cli.main(["--temp", str(path), "--web-open=" + query]) == 0
        data = runtime.read()
        assert web_runtime.alive(data)
        assert runtime.path.stat().st_mode & 0o777 == 0o600
        assert query not in runtime.path.read_text()
        assert query not in urls[0]
        assert cli.main(["--temp", str(path), "--web-open="]) == 0
        assert runtime.read() == data  # Same owned process, independent tab request.
        assert urls[0] != urls[1]
        assert cli.main(["--temp", str(path), "--web-stop"]) == 0
        deadline = time.monotonic() + 5
        while web_runtime.alive(data) and time.monotonic() < deadline:
            time.sleep(.05)
        assert not web_runtime.alive(data)
        assert cli.main(["--temp", str(path), "--web-open=restart"]) == 0
        assert runtime.read()["instance"] != data["instance"]
    finally:
        current = runtime.read()
        if web_runtime.alive(current):
            web_runtime.call(current, "stop", {})


def test_runtime_rejects_symlinks_and_source_collisions(web_library):
    path, config = web_library
    directory = config.database.parent / "web-runtime"
    directory.symlink_to(config.bib.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        web_runtime.Runtime(path, config)
    directory.unlink()
    runtime = web_runtime.Runtime(path, config)
    runtime.lock_path.symlink_to(config.bib)
    before = config.bib.read_bytes()
    with pytest.raises(OSError):
        with runtime.lock():
            pass
    assert config.bib.read_bytes() == before


def test_simultaneous_launches_have_one_owned_server(web_library):
    path, config = web_library
    runtime = web_runtime.Runtime(path, config)

    def launch():
        with runtime.lock():
            return web_runtime.launch(runtime)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            states = list(pool.map(lambda _: launch(), range(3)))
        assert states[0] == states[1] == states[2]
    finally:
        data = runtime.read()
        if web_runtime.alive(data):
            web_runtime.call(data, "stop", {})


def test_busy_owned_server_cannot_cause_duplicate_startup(web_library, monkeypatch):
    path, config = web_library
    runtime = web_runtime.Runtime(path, config)
    lease = runtime.acquire_lease()
    try:
        monkeypatch.setattr(web_runtime, "alive", lambda data: False)

        def unexpected(*args, **kwargs):
            pytest.fail("A busy owned server must not trigger another process")

        monkeypatch.setattr(web_runtime.subprocess, "Popen", unexpected)
        with runtime.lock(), pytest.raises(ValueError, match="busy"):
            web_runtime.launch(runtime)
    finally:
        os.close(lease)


def test_background_start_survives_python_launcher_closing_inherited_descriptors(
    web_library, monkeypatch,
):
    path, config = web_library
    runtime = web_runtime.Runtime(path, config)
    real_python = sys.executable
    launcher = path.parent / "python-launcher"
    launcher.write_text(
        f"#!{real_python}\nimport os, sys\nos.closerange(3, 256)\n"
        f"os.execv({real_python!r}, [{real_python!r}, *sys.argv[1:]])\n")
    launcher.chmod(0o700)
    monkeypatch.setattr(sys, "executable", str(launcher))
    try:
        with runtime.lock():
            state = web_runtime.launch(runtime)
        assert web_runtime.alive(state)
    finally:
        state = runtime.read()
        if web_runtime.alive(state):
            web_runtime.call(state, "stop", {})


def test_stale_unrelated_server_never_receives_queries_or_stop(web_library):
    path, config = web_library
    app = web.WebApp(config, path)
    runtime = web_runtime.Runtime(path, config)
    with running(app) as server:
        with runtime.lock():
            data = runtime.write(app, server)
            data["instance"] = "a" * 32
            runtime.path.write_text(json.dumps(data))
        assert not web_runtime.alive(runtime.read())
        assert cli.main(["--temp", str(path), "--web-stop"]) == 0
        assert request(server, app, "/internal/health", internal=True)[0] == 200
        assert not app.requests
        other = path.parent / "second.toml"
        other.write_text(path.read_text())
        assert web_runtime.Runtime(other, config).key != runtime.key


def test_startup_failure_timeout_and_browser_failure(web_library, monkeypatch, capsys):
    path, config = web_library
    runtime = web_runtime.Runtime(path, config)
    child = type("FailedChild", (), {"poll": lambda self: 1})()
    monkeypatch.setattr(web_runtime.subprocess, "Popen", lambda *a, **kw: child)
    with runtime.lock(), pytest.raises(ValueError, match="Could not start"):
        web_runtime.launch(runtime)
    terminated = []
    child.poll = lambda: None
    child.terminate = lambda: terminated.append(True)
    child.wait = lambda **kw: 0
    monkeypatch.setattr(web_runtime, "START_TIMEOUT", 0)
    with runtime.lock(), pytest.raises(ValueError, match="timed out"):
        web_runtime.launch(runtime)
    assert terminated == [True]
    monkeypatch.setattr(web_runtime.webbrowser, "open", lambda *a, **kw: False)
    web_runtime.open_browser("http://127.0.0.1:8765/")
    assert "Open the displayed localhost URL manually" in capsys.readouterr().err


def test_missing_configuration_and_index_provide_setup_guidance(web_library, capsys):
    path, config = web_library
    assert cli.main(["--temp", str(path.parent / "missing.toml"), "--web"]) == 1
    assert "--setup" in capsys.readouterr().err
    config.database.unlink()
    assert cli.main(["--temp", str(path), "--web"]) == 1
    assert "--index update" in capsys.readouterr().err
    assert not config.database.exists()

