"""Object-oriented CLI grammar and validation, before any application I/O."""

from __future__ import annotations

import argparse
from pathlib import Path


class Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if hasattr(namespace, self.dest):
            parser.error(f"{option_string} may only be specified once")
        setattr(namespace, self.dest, self.const if self.nargs == 0 else values)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bibdesk-rag", description="Read-only local BibDesk literature retrieval",
        argument_default=argparse.SUPPRESS, allow_abbrev=False,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Examples: bibdesk-rag --example\nManual: bibdesk-rag --readme",
    )
    actions = p.add_argument_group("Information and operations (choose one)")
    choice = actions.add_mutually_exclusive_group()
    for short, long, description in (
        ("-v", "--version", "Show version and software citation, then exit"),
        ("-e", "--example", "Show usage examples, then exit"),
        ("-r", "--readme", "View the packaged local manual"),
    ):
        choice.add_argument(short, long, action=Once, nargs=0, const=True, help=description)
    choice.add_argument("-o", "--output", action=Once,
                        choices=("manual", "config-template", "citation"),
                        help="Print an auxiliary resource to stdout")
    choice.add_argument("--setup", action=Once, nargs=0, const=True,
                        help="Interactively configure a library and local Codex connection")
    choice.add_argument("-c", "--config", dest="configuration", nargs="+", action=Once,
                        metavar=("ACTION", "PATH"), help=(
                            "show           Display effective settings\n"
                            "path           Print the selected config path\n"
                            "use PATH       Remember an existing configuration\n"
                            "create [PATH]  Create and remember a config (--bib required)"))
    choice.add_argument("-i", "--index", action=Once,
                        choices=("update", "rebuild", "status", "check"),
                        help=("update   Create or incrementally update the index\n"
                              "rebuild  Re-extract all derived index data\n"
                              "status   Display counts and last update information\n"
                              "check    Check index integrity without changing it"))
    choice.add_argument("-p", "--paper", nargs="+", action=Once, metavar=("ACTION", "VALUE"),
                        help=("search QUERY     Search bibliography metadata and indexed text\n"
                              "show KEY         Retrieve a paper by citekey\n"
                              "attachments KEY  List a paper's linked attachments\n"
                              "context QUERY    Retrieve excerpts with source citations"))
    settings = p.add_argument_group("Configuration")
    settings.add_argument("--temp", type=Path, metavar="PATH",
                          help="Use this config for this invocation; keep the saved selection")
    settings.add_argument("--bib", type=Path, metavar="FILE", help="Library for --config create")
    settings.add_argument("--data-dir", type=Path, metavar="DIR",
                          help="Index directory for --config create")
    output = p.add_argument_group("Result display")
    output.add_argument("--format", choices=("text", "json", "bibtex"),
                        help="Result format (default: text; bibtex only for --paper show)")
    output.add_argument("--verbose", action="store_true", help="Show all indexing diagnostics")
    output.add_argument("--no-progress", action="store_true", help="Hide the indexing progress bar")
    search = p.add_argument_group("Search and context")
    search.add_argument("--scope", choices=("all", "metadata", "fulltext"),
                        help="Search scope (default: all)")
    search.add_argument("--top", type=int, metavar="N", help="Result limit (1..100)")
    search.add_argument("--per-paper", type=int, metavar="N", help="Results per paper (1..10)")
    search.add_argument("--citekey", dest="citekeys", action="append", metavar="KEY",
                        help="Select papers (repeatable; metadata lookup accepts one)")
    search.add_argument("--metadata-query", metavar="QUERY",
                        help="Select candidate papers before searching their text")
    search.add_argument("--doi", metavar="DOI", help="Exact DOI (metadata search)")
    search.add_argument("--author", metavar="NAME", help="Author filter (metadata search)")
    search.add_argument("--year", metavar="YEAR", help="Year filter (metadata search)")
    search.add_argument("--max-chars", type=int, metavar="N",
                        help="Context character budget (256..100000)")
    indexing = p.add_argument_group("Index update")
    indexing.add_argument("--verify-hashes", action="store_true",
                          help="Hash attachments even when size/mtime are unchanged")
    return p


LEGACY = {
    "setup": "--setup", "config": "--config ACTION", "init": "--config create",
    "index": "--index rebuild", "update": "--index update", "status": "--index status",
    "doctor": "--index check", "search": "--paper search QUERY", "get": "--paper show KEY",
    "attachments": "--paper attachments KEY", "context": "--paper context QUERY",
}


def parse_args(argv: list[str]) -> argparse.Namespace | None:
    p = parser()
    if not argv:
        from .cli_resources import brief_help_text

        print(brief_help_text(), end="")
        return None
    args, unknown = p.parse_known_args(argv)
    if unknown:
        hint = next((f"Use {LEGACY[word]} instead of the former '{word}' command."
                     for word in unknown if word in LEGACY), "See --example for the new syntax.")
        if "--json" in unknown:
            hint += " Replace --json with --format json."
        p.error("unrecognized arguments: " + " ".join(unknown) + "\n" + hint)
    supplied = vars(args).copy()
    primary = next((key for key in (
        "version", "example", "readme", "output", "setup", "configuration", "index", "paper"
    ) if key in supplied), None)
    if primary is None:
        p.error("Choose --setup, --config ACTION, --index ACTION, or --paper ACTION VALUE")
    allowed = {"temp", "format"}
    args.command = primary
    if primary in {"version", "example", "readme", "output"}:
        allowed = set()
    elif primary == "setup":
        allowed = {"temp"}
    elif primary == "configuration":
        tokens = args.configuration
        action = tokens[0]
        valid = {"show": (1,), "path": (1,), "use": (2,), "create": (1, 2)}
        if action not in valid:
            p.error("--config expects show, path, use PATH, or create [PATH]. "
                    "For a temporary config file use --temp PATH.")
        if len(tokens) not in valid[action]:
            example = {"show": "show", "path": "path", "use": "use PATH",
                       "create": "create [PATH] --bib FILE"}[action]
            p.error(f"Usage: bibdesk-rag --config {example}")
        args.command, args.config_action = "config", action
        args.path = Path(tokens[1]) if len(tokens) == 2 else None
        if action in {"use", "create"} and "temp" in supplied:
            p.error(f"--temp cannot be combined with --config {action}")
        if action == "create":
            allowed |= {"bib", "data_dir"}
            if "bib" not in supplied:
                p.error("--config create requires --bib FILE")
    elif primary == "index":
        args.index_action = args.index
        if args.index in {"update", "rebuild"}:
            allowed |= {"verify_hashes", "verbose", "no_progress"}
    elif primary == "paper":
        tokens = args.paper
        valid = {"search": "QUERY", "show": "KEY", "attachments": "KEY", "context": "QUERY"}
        if tokens[0] not in valid:
            p.error("--paper expects search QUERY, show KEY, attachments KEY, or context QUERY")
        if len(tokens) != 2:
            p.error(f"Usage: bibdesk-rag --paper {tokens[0]} {valid[tokens[0]]}")
        args.paper_action, args.value = tokens
        if args.paper_action in {"search", "context"}:
            allowed |= {"top", "per_paper", "citekeys", "metadata_query"}
            if "metadata_query" in supplied and "citekeys" in supplied:
                p.error("Choose --metadata-query or --citekey to select papers, not both")
        if args.paper_action == "search":
            allowed |= {"scope", "doi", "year", "author"}
            if supplied.get("scope", "all") == "metadata":
                if {"per_paper", "metadata_query"} & supplied.keys():
                    p.error("--per-paper and --metadata-query require fulltext or all scope")
                if len(supplied.get("citekeys", [])) > 1:
                    p.error("Metadata exact lookup accepts one --citekey")
            elif {"doi", "year", "author"} & supplied.keys():
                p.error("--doi, --year, --author require --scope metadata")
            if "metadata_query" in supplied and supplied.get("scope", "all") != "all":
                p.error("--metadata-query requires --scope all")
        elif args.paper_action == "context":
            allowed |= {"max_chars"}
    irrelevant = supplied.keys() - allowed - {primary}
    if irrelevant:
        names = ", ".join("--" + ("citekey" if key == "citekeys" else key.replace("_", "-"))
                          for key in sorted(irrelevant))
        p.error(f"{names} cannot be used with this operation")
    if supplied.get("format") == "bibtex" and not (
        primary == "paper" and args.paper_action == "show"
    ):
        p.error("--format bibtex is only available with --paper show KEY")
    for name, low, high in (("top", 1, 100), ("per_paper", 1, 10), ("max_chars", 256, 100000)):
        if name in supplied and not low <= supplied[name] <= high:
            p.error(f"--{name.replace('_', '-')} must be between {low} and {high}")
    defaults = {
        "temp": None, "format": "text", "data_dir": None, "scope": "all",
        "top": 5 if getattr(args, "paper_action", None) == "context" else 10,
        "per_paper": 2, "citekeys": None, "metadata_query": None,
        "doi": None, "year": None, "author": None, "max_chars": 10000,
        "verify_hashes": False, "verbose": False, "no_progress": False,
    }
    for key, value in defaults.items():
        if not hasattr(args, key):
            setattr(args, key, value)
    return args
