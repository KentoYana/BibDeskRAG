"""Command-line interface: results on stdout, diagnostics on stderr."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .config import init_config, load_config
from .context import build_context
from .database import connect, doctor, status
from .indexer import index_library
from .progress import IndexDiagnostics, IndexProgressBar, single_line
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
        sub.add_argument("--no-progress", action="store_true", help="Disable the terminal progress bar")
        sub.add_argument(
            "--verbose", action="store_true", help="Show all parser diagnostics and attachment issues"
        )
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
            human_output = not args.json and sys.stdout.isatty()
            show_progress = (
                human_output
                and sys.stderr.isatty()
                and os.environ.get("TERM") != "dumb"
                and not args.no_progress
                and not args.verbose
            )
            with IndexDiagnostics(verbose=args.verbose), IndexProgressBar(
                enabled=show_progress
            ) as progress:
                result = index_library(
                    config,
                    rebuild=args.command == "index",
                    verify_hashes=args.verify_hashes,
                    progress=progress.update if show_progress else None,
                )
            # Full structured errors remain available in JSON and in the index.
            # Default terminal previews are bounded even for huge/problematic PDFs.
            issues = result["errors"] if args.verbose else result["errors"][:3]
            if human_output or args.verbose:
                for issue in issues:
                    message = f"{issue['path']}: {issue['error']}"
                    print(message if args.verbose else single_line(message), file=sys.stderr)
            if human_output:
                label = "Index" if args.command == "index" else "Update"
                print(
                    f"{label} complete: {result['papers_added']} papers added, "
                    f"{result['papers_changed']} changed, {result['papers_deleted']} deleted, "
                    f"{result['papers_renamed']} renamed."
                )
                print(
                    f"Attachments: {result['files_extracted']} extraction attempts, "
                    f"{result['files_reused']} reused, {result['files_hashed']} hashed."
                )
                print(
                    f"Attachment issues: {len(result['errors'])} "
                    "(this run; including partial/unsupported)."
                )
                if result["errors"]:
                    print(
                        "Use --json for all issue details, or attachments CITEKEY --json "
                        "with the same --config to inspect a paper."
                    )
                return 0
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
    except KeyboardInterrupt:
        print("bibdesk-rag: interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
