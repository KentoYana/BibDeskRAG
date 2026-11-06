"""Command-line interface: results on stdout, diagnostics on stderr."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import sys

from .cli_arguments import parse_args, parser as parser
from .cli_output import print_result, text_value
from .config import activate_config, config_directory, config_selection, init_config, load_config
from .context import build_context
from .database import connect, doctor, status
from .indexer import index_library
from .progress import IndexDiagnostics, IndexProgressBar, single_line
from .search import SQLiteSearch


def config_command(args: argparse.Namespace) -> None:
    if args.config_action in {"use", "create"}:
        if args.config_action == "create":
            destination = args.path
            if destination is None:
                destination = (Path(os.environ["BIBDESK_RAG_CONFIG"])
                               if os.environ.get("BIBDESK_RAG_CONFIG")
                               else config_directory() / "config.toml")
            selected = init_config(args.bib, destination, args.data_dir)
            try:
                activate_config(selected)
            except (OSError, ValueError) as exc:
                raise ValueError(
                    f"Configuration created at {selected}, but selection could not be saved: "
                    f"{exc}. After fixing this, run 'bibdesk-rag --config use PATH'."
                ) from exc
        else:
            selected = activate_config(args.path)
        effective, source = config_selection()
        print_result({"active_config": str(selected), "config": str(effective),
                      "source": source}, args.format)
        if selected != effective:
            print("The selection was saved, but BIBDESK_RAG_CONFIG overrides it. "
                  "Unset that variable to use the saved selection.", file=sys.stderr)
        return
    path, source = config_selection(args.temp)
    result = {"config": str(path), "source": source}
    if args.config_action == "path":
        if args.format == "json":
            print_result(result, args.format)
        else:
            print(text_value(str(path)))
        return
    config = load_config(path)
    result.update(bib=str(config.bib), database=str(config.database),
                  extraction=asdict(config.extraction))
    result["semantic"] = {key: str(value) if isinstance(value, Path) else value
                          for key, value in asdict(config.semantic).items()}
    if args.format == "json":
        print_result(result, args.format)
        return
    for name in ("config", "source", "bib", "database"):
        print(f"{name} = {json.dumps(result[name], ensure_ascii=False)}")
    print("\n[extraction]")
    for name, value in result["extraction"].items():
        print(f"{name} = {value}")
    print("\n[semantic]")
    for name, value in result["semantic"].items():
        print(f"{name} = {json.dumps(value, ensure_ascii=False)}")


def update_index(config, args: argparse.Namespace) -> None:
    human_output = args.format == "text"
    show_progress = (
        human_output and sys.stdout.isatty() and sys.stderr.isatty()
        and os.environ.get("TERM") != "dumb" and not args.no_progress and not args.verbose
    )
    with IndexDiagnostics(verbose=args.verbose), IndexProgressBar(enabled=show_progress) as progress:
        result = index_library(
            config, rebuild=args.index_action == "rebuild", verify_hashes=args.verify_hashes,
            progress=progress.update if show_progress else None,
            config_path=config_selection(args.temp)[0],
        )
    issues = result["errors"] if args.verbose else result["errors"][:3]
    if human_output or args.verbose:
        for issue in issues:
            message = f"{issue['path']}: {issue['error']}"
            print(message if args.verbose else single_line(message), file=sys.stderr)
    if not human_output:
        print_result(result, args.format)
        return
    label = "Rebuild" if args.index_action == "rebuild" else "Update"
    print(f"{label} complete: {result['papers_added']} papers added, "
          f"{result['papers_changed']} changed, {result['papers_deleted']} deleted, "
          f"{result['papers_renamed']} renamed.")
    print(f"Attachments: {result['files_extracted']} extraction attempts, "
          f"{result['files_reused']} reused, {result['files_hashed']} hashed.")
    print(f"Attachment issues: {len(result['errors'])} "
          "(this run; including partial/unsupported).")
    if result["semantic"]["enabled"]:
        semantic = result["semantic"]
        print(f"Semantic: {semantic['embedded']} embedded, {semantic['reused']} reused, "
              f"{semantic['skipped']} skipped, {semantic['title_only']} title-only.")
    else:
        print("Semantic search: disabled (no model loaded).")
    if result["errors"]:
        print("Use --format json for all issue details, or --paper attachments KEY "
              "--format json with the same configuration to inspect a paper.")


def paper_result(engine: SQLiteSearch, args: argparse.Namespace):
    if args.paper_action == "search":
        if args.scope == "metadata":
            return engine.search_papers(
                args.value, args.top, year=args.year, doi=args.doi, author=args.author,
                citekey=args.citekeys[0] if args.citekeys else None,
            )
        return engine.search(
            args.value, args.top, scope=args.scope, citekeys=args.citekeys,
            per_paper=args.per_paper, metadata_query=args.metadata_query,
        )
    if args.paper_action == "show":
        return engine.get_paper(args.value)
    if args.paper_action == "attachments":
        return engine.get_attachments(args.value)
    return build_context(engine, args.value, args.top, args.max_chars,
                         citekeys=args.citekeys, per_paper=args.per_paper,
                         metadata_query=args.metadata_query)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args is None:
        return 0
    try:
        if args.command in {"version", "example", "readme", "output"}:
            from . import cli_resources

            if args.command == "readme":
                cli_resources.show_manual()
            else:
                functions = {
                    "version": cli_resources.version_text,
                    "example": cli_resources.examples_text,
                    "manual": cli_resources.manual_text,
                    "config-template": cli_resources.config_template_text,
                    "citation": cli_resources.citation_text,
                }
                resource = args.output if args.command == "output" else args.command
                print(functions[resource](), end="")
            return 0
        if args.command == "config":
            config_command(args)
            return 0
        if args.command == "setup":
            from .setup import run_setup

            return run_setup(args.temp, remember=args.temp is None)
        config = load_config(args.temp)
        if args.command == "semantic":
            from .semantic import protect, require_enabled

            from .embeddings import download_model

            require_enabled(config)
            protect(config, config_selection(args.temp)[0])
            result = download_model(config.semantic)
            print_result(result, args.format)
            return 0
        if args.command == "paper" and args.paper_action == "search" and args.mode == "semantic":
            from .semantic import semantic_search

            print_result(semantic_search(config, args.value, args.semantic_limit), args.format)
            return 0
        if args.command == "index" and args.index_action in {"update", "rebuild"}:
            update_index(config, args)
            return 0
        db = connect(config.database, readonly=True)
        try:
            if args.command == "index":
                result = doctor(db, config) if args.index_action == "check" else status(db, config)
            else:
                result = paper_result(SQLiteSearch(db), args)
                if args.format == "bibtex":
                    print(result["bibtex"])
                    return 0
                if args.paper_action == "context" and args.format == "text":
                    print("\n".join(text_value(line) for line in result["context"].split("\n")),
                          end="")
                    for note in result["unverified"]:
                        print(text_value(note), file=sys.stderr)
                    return 0
        finally:
            db.close()
        print_result(result, args.format)
        return 1 if args.command == "index" and args.index_action == "check" and not result["ok"] else 0
    except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError) as exc:
        print(f"bibdesk-rag: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("bibdesk-rag: interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
