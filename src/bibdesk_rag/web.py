"""Read-only localhost search application, with separate browser and CLI authentication."""

from __future__ import annotations

import argparse
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import re
import secrets
import socketserver
import sqlite3
import threading
import time
from urllib.parse import quote

from .bibdesk import normalize_doi
from .cli_arguments import parse_args, parser
from .config import Config
from .database import connect, status
from .search import SQLiteSearch
from . import skim

MAX_BODY = 32768


def search_arguments(body: dict) -> argparse.Namespace:
    """Apply the CLI grammar without interpreting any user string as an option."""
    strings = {"query", "mode", "scope", "doi", "author", "year", "metadata_query"}
    allowed = strings | {"top", "per_paper", "citekeys"}
    if body.keys() - allowed:
        raise ValueError("Unknown search option.")
    for key in strings & body.keys():
        if not isinstance(body[key], str) or len(body[key]) > 2000 or "\x00" in body[key]:
            raise ValueError(f"{key} must be a string of at most 2000 characters.")
    for key in {"top", "per_paper"} & body.keys():
        if type(body[key]) is not int:
            raise ValueError(f"{key} must be an integer.")
    if "citekeys" in body and (
        not isinstance(body["citekeys"], list) or len(body["citekeys"]) > 100
        or any(not isinstance(k, str) or not k or len(k) > 2000 or "\x00" in k
               for k in body["citekeys"])
        or not body["citekeys"]
    ):
        raise ValueError("citekeys must contain 1..100 nonempty strings.")
    argv = ["--paper", "search", "web-query-placeholder"]
    for key, value in body.items():
        if key == "query":
            continue
        if key == "citekeys":
            argv.extend("--citekey=" + item for item in value)
        else:
            argv.append("--" + key.replace("_", "-") + "=" + str(value))
    argument_parser = parser()

    def invalid(message):
        raise ValueError(message)

    argument_parser.error = invalid
    args = parse_args(argv, argument_parser=argument_parser)
    args.value = body.get("query", "")
    return args


def doi_url(value: str) -> str | None:
    doi = normalize_doi(value)
    if not re.fullmatch(r"10\.\d{4,9}/[^\s\x00-\x1f]+", doi):
        return None
    return "https://doi.org/" + quote(doi, safe="/")


class WebApp:
    def __init__(self, config: Config, config_path: Path):
        self.config = config
        self.config_path = config_path.resolve()
        self.csrf = secrets.token_urlsafe(32)
        self.owner_token = secrets.token_urlsafe(32)
        self.instance = secrets.token_hex(16)
        self.backend = None
        self.model_lock = threading.Lock()
        self.requests_lock = threading.Lock()
        self.requests = {}
        # Fail before binding or launching a browser. Never create an index.
        with self.database():
            pass

    def database(self):
        if not self.config.database.is_file():
            raise ValueError("Index missing. Run bibdesk-rag --index update first.")
        db = connect(self.config.database, readonly=True, bib=self.config.bib)
        db.execute("PRAGMA busy_timeout=2000")
        return closing(db)

    def search(self, body):
        args = search_arguments(body)
        if args.mode == "semantic":
            from .embeddings import SentenceTransformerBackend
            from .semantic import require_enabled, semantic_search

            require_enabled(self.config)
            with self.model_lock:
                if self.backend is None:
                    self.backend = SentenceTransformerBackend(self.config.semantic)
                hits = semantic_search(self.config, args.value, args.top, backend=self.backend)
        else:
            from .cli import paper_result

            with self.database() as db:
                hits = paper_result(SQLiteSearch(db), args)
        # Group exactly the returned hits, in ranking order; do not fetch extra hits.
        cards = {}
        with self.database() as db:
            engine = SQLiteSearch(db)
            for hit in hits:
                key = hit["citekey"]
                if key not in cards:
                    paper = engine.get_paper(key)
                    attachments = self.attachments(engine, key)
                    cards[key] = {"paper": paper, "doi_url": doi_url(paper["doi"]),
                                  "attachments": attachments, "hits": []}
                cards[key]["hits"].append(hit)
        return {"papers": list(cards.values()), "paper_count": len(cards),
                "hit_count": len(hits), "mode": args.mode}

    @staticmethod
    def attachments(engine, key):
        values = engine.get_attachments(key)
        for value in values:
            path = Path(value["file_path"])
            value["name"] = path.name
            value["exists"] = path.is_file()
            value["can_open"] = value["exists"] and path.suffix.lower() == ".pdf"
        return values

    def open_attachment(self, attachment_id, body):
        if body.keys() - {"page"}:
            raise ValueError("Only an optional page number is accepted.")
        page = body.get("page")
        if "page" in body and (type(page) is not int or not 1 <= page <= 1000000):
            raise ValueError("page must be a positive integer (at most 1000000).")
        with self.database() as db:
            row = db.execute(
                "SELECT a.path FROM attachments a JOIN paper_attachments pa ON pa.attachment_id=a.id "
                "JOIN papers p ON p.id=pa.paper_id WHERE a.id=? LIMIT 1", (attachment_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Unknown attachment in this library.")
            path = Path(row["path"])
        # Indexed paths are already resolved by the existing BibDesk resolver.
        # Never guess a moved path, scan a directory or unpack ZIP members here.
        return skim.open_pdf(path, page)

    def initial_request(self, query):
        if not isinstance(query, str) or len(query) > 2000 or "\x00" in query:
            raise ValueError("query must be a string of at most 2000 characters.")
        with self.requests_lock:
            now = time.monotonic()
            self.requests = {k: v for k, v in self.requests.items() if v[0] > now}
            if len(self.requests) >= 100:
                raise ValueError("Too many pending search tabs. Please wait a minute.")
            key = secrets.token_urlsafe(24)
            self.requests[key] = (now + 60, query)
        return {"request_id": key}

    def consume_request(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32}", key):
            raise ValueError("Invalid initial search request.")
        with self.requests_lock:
            item = self.requests.pop(key, None)
        if item is None or item[0] <= time.monotonic():
            raise ValueError("This initial search has expired or was already used. Enter a new search.")
        return {"query": item[1]}

    def info(self):
        with self.database() as db:
            summary = status(db, self.config)
        return {"library": str(self.config.bib), "configuration": str(self.config_path),
                "database": str(self.config.database), "status": summary,
                "semantic_enabled": self.config.semantic.enabled}


class LocalServer(ThreadingHTTPServer):
    """Bound sockets, headers, bodies and concurrency; model inference is serialized."""
    daemon_threads = False
    block_on_close = True
    request_queue_size = 8

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(4)
        super().__init__(address, handler)

    def server_bind(self):
        # HTTPServer normally reverse-resolves the bound address with getfqdn.
        # This is a fixed IPv4 loopback service: no DNS is necessary or desired.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(5)
        return request, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Do not log request content, tokens, file paths or tracebacks.
        pass


def handler_for(app: WebApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BibDeskRAG"
        sys_version = ""

        def log_message(self, *args):
            pass

        @property
        def origin(self):
            return f"http://127.0.0.1:{self.server.server_port}"

        def reply(self, code, value, content_type="application/json; charset=utf-8"):
            payload = (json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json")
                       else value if isinstance(value, bytes) else value.encode())
            self.send_response(code)
            for key, val in {
                "Content-Type": content_type, "Content-Length": str(len(payload)),
                "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            }.items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(payload)

        def host_valid(self):
            hosts = self.headers.get_all("Host", [])
            return hosts == [f"127.0.0.1:{self.server.server_port}"]

        def do_GET(self):
            if not self.host_valid() or (self.headers.get("Origin") not in {None, self.origin}):
                self.reply(403, {"error": "This server accepts only its own localhost origin."})
                return
            resources = {"/": ("index.html", "text/html; charset=utf-8"),
                         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                         "/app.css": ("app.css", "text/css; charset=utf-8")}
            if self.path not in resources:
                self.reply(404, {"error": "Not found. Use POST for API requests."})
                return
            name, mime = resources[self.path]
            data = files("bibdesk_rag").joinpath("resources/web", name).read_text()
            if name == "index.html":
                data = data.replace("__CSRF__", app.csrf)
            self.reply(200, data, mime)

        def do_POST(self):
            self.close_connection = True
            if not self.host_valid():
                self.reply(403, {"error": "Invalid localhost Host header."})
                return
            internal = self.path.startswith("/internal/")
            if internal:
                valid = ("Origin" not in self.headers
                         and len(self.headers.get_all("Authorization", [])) == 1
                         and secrets.compare_digest(self.headers.get("Authorization", "").encode(),
                                                    ("Bearer " + app.owner_token).encode()))
            else:
                valid = (self.headers.get_all("Origin", []) == [self.origin]
                         and len(self.headers.get_all("X-CSRF-Token", [])) == 1
                         and secrets.compare_digest(self.headers.get("X-CSRF-Token", "").encode(),
                                                    app.csrf.encode()))
            if not valid:
                self.reply(403, {"error": "Request authentication failed. Reload this page."})
                return
            try:
                if (self.headers.get("Transfer-Encoding") is not None
                        or len(self.headers.get_all("Content-Length", [])) != 1
                        or self.headers.get_content_type() != "application/json"):
                    raise ValueError("A bounded JSON request body is required.")
                length = int(self.headers["Content-Length"])
                if not 0 < length <= MAX_BODY:
                    self.reply(413, {"error": "Request body is too large or empty."})
                    return
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("The request body must be a JSON object.")
                if internal:
                    result = self.internal(body)
                elif self.path == "/api/search":
                    result = app.search(body)
                elif self.path == "/api/status" and not body:
                    result = app.info()
                elif self.path == "/api/initial" and body.keys() == {"request_id"}:
                    result = app.consume_request(body["request_id"])
                elif match := re.fullmatch(r"/api/attachments/([1-9]\d{0,9})/open", self.path):
                    result = app.open_attachment(int(match[1]), body)
                elif self.path == "/api/paper" and body.keys() == {"citekey"}:
                    key = body["citekey"]
                    if not isinstance(key, str) or not 0 < len(key) <= 2000:
                        raise ValueError("citekey must be a nonempty string of at most 2000 characters.")
                    with app.database() as db:
                        result = SQLiteSearch(db).get_paper(key)
                else:
                    self.reply(404, {"error": "Unknown API operation."})
                    return
                self.reply(200, result)
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {"error": str(exc)})
            except KeyError:
                self.reply(404, {"error": "The requested item is not in this library."})
            except sqlite3.Error:
                self.reply(503, {"error": "The index is unavailable or busy. Retry, or run bibdesk-rag --index check."})
            except (OSError, RuntimeError, ImportError):
                self.reply(503, {"error": "The operation could not be completed. Check local files and optional semantic setup using bibdesk-rag --setup."})

        def internal(self, body):
            if self.path == "/internal/health" and not body:
                return {"instance": app.instance, "config": str(app.config_path)}
            if self.path == "/internal/initial" and body.keys() == {"query"}:
                return app.initial_request(body["query"])
            if self.path == "/internal/stop" and not body:
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return {"stopping": True}
            raise ValueError("Unknown internal operation.")

    return Handler


def bind_server(app, port=None):
    import errno

    try:
        return LocalServer(("127.0.0.1", 8765 if port is None else port), handler_for(app))
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise ValueError("Could not bind the localhost search server.") from None
        if port is not None:
            raise ValueError(f"Port {port} is already in use. Choose another --port.") from None
        return LocalServer(("127.0.0.1", 0), handler_for(app))
