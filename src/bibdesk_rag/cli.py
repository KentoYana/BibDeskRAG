"""Command-line interface: results on stdout, diagnostics on stderr."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .config import init_config, load_config
from .context import build_context
from .database import connect, doctor, status
from .indexer import index_library
from .search import SQLiteSearch


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bibdesk-rag", description="Read-only local BibDesk literature retrieval"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, help="Configuration path (or BIBDESK_RAG_CONFIG)")
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Register a library without changing it")
    init.add_argument("--bib", required=True, type=Path)
    init.add_argument("--data-dir", type=Path)
    for name in ("index", "update"):
        sub = commands.add_parser(
            name, help="Rebuild index" if name == "index" else "Incrementally update index"
        )
        sub.add_argument(
            "--verify-hashes", action="store_true", help="Hash even unchanged size/mtime files"
        )
        sub.add_argument("--json", action="store_true")
    search = commands.add_parser("search", help="Search metadata and/or indexed text")
    search.add_argument("query")
    search.add_argument("--scope", choices=["all", "metadata", "fulltext"], default="all")
    search.add_argument("--top", type=int, default=10)
    search.add_argument("--per-paper", type=int, default=2)
    search.add_argument(
        "--citekey",
        action="append",
        dest="citekeys",
        help="Restrict full text to selected keys (repeatable)",
    )
    search.add_argument("--metadata-query", help="Select candidate papers with a separate query")
    search.add_argument("--doi", help="Exact normalized DOI (metadata scope)")
    search.add_argument("--year", help="Publication year (metadata scope)")
    search.add_argument("--author", help="Author substring (metadata scope)")
    search.add_argument("--json", action="store_true")
    get = commands.add_parser("get", help="Retrieve one indexed bibliography record")
    get.add_argument("citekey")
    get.add_argument("--format", choices=["json", "bibtex"], default="json")
    get.add_argument("--json", action="store_true")
    attachments = commands.add_parser("attachments")
    attachments.add_argument("citekey")
    attachments.add_argument("--json", action="store_true")
    context = commands.add_parser("context", help="Retrieve a bounded evidence bundle")
    context.add_argument("query")
    context.add_argument("--top", type=int, default=5)
    context.add_argument("--max-chars", type=int, default=10000)
    context.add_argument("--per-paper", type=int, default=2)
    context.add_argument("--citekey", action="append", dest="citekeys")
    context.add_argument("--metadata-query")
    context.add_argument("--json", action="store_true")
    for name in ("status", "doctor"):
        sub = commands.add_parser(name)
        sub.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            print(
                json.dumps(
                    {"config": str(init_config(args.bib, args.config, args.data_dir))},
                    ensure_ascii=False,
                )
            )
            return 0
        config = load_config(args.config)
        if args.command in ("index", "update"):
            result = index_library(
                config, rebuild=args.command == "index", verify_hashes=args.verify_hashes
            )
            for error in result["errors"]:
                print(f"{error['path']}: {error['error']}", file=sys.stderr)
        else:
            db = connect(config.database, readonly=True)
            try:
                engine = SQLiteSearch(db)
                if args.command == "search":
                    if args.scope == "metadata":
                        if args.citekeys and len(args.citekeys) > 1:
                            raise ValueError("Metadata exact lookup accepts one --citekey")
                        result = engine.search_papers(
                            args.query,
                            args.top,
                            year=args.year,
                            doi=args.doi,
                            author=args.author,
                            citekey=args.citekeys[0] if args.citekeys else None,
                        )
                    else:
                        if args.doi or args.year or args.author:
                            raise ValueError("--doi, --year, --author require --scope metadata")
                        result = engine.search(
                            args.query,
                            args.top,
                            scope=args.scope,
                            citekeys=args.citekeys,
                            per_paper=args.per_paper,
                            metadata_query=args.metadata_query,
                        )
                elif args.command == "get":
                    result = engine.get_paper(args.citekey)
                    if args.format == "bibtex":
                        print(result["bibtex"])
                        return 0
                elif args.command == "attachments":
                    result = engine.get_attachments(args.citekey)
                elif args.command == "context":
                    result = build_context(
                        engine,
                        args.query,
                        args.top,
                        args.max_chars,
                        citekeys=args.citekeys,
                        per_paper=args.per_paper,
                        metadata_query=args.metadata_query,
                    )
                    if not args.json:
                        print(result["context"], end="")
                        for note in result["unverified"]:
                            print(note, file=sys.stderr)
                        return 0
                elif args.command == "doctor":
                    result = doctor(db)
                else:
                    result = status(db)
            finally:
                db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "doctor" and not result["ok"] else 0
    except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError) as exc:
        print(f"bibdesk-rag: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
