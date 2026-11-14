"""Interactive onboarding, using the same read-only sources and index operations as CLI.

All prompts and human diagnostics go to stderr. No source text is printed, and
no command is interpreted by a shell. Only an explicitly chosen semantic.enabled option is changed in existing configuration.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass, field
import io
import json
import os
from pathlib import Path
import shlex
import sqlite3
import sys
import tomllib
from typing import TextIO

from . import __version__
from .bibdesk import read_library
from .config import (
    Config, activate_config, default_config_path, default_data_dir, init_config, load_config,
    set_semantic_enabled,
)
from .config import check_output_locations as check_config_output_locations
from .database import LibraryIdentityError, connect, status
from .indexer import index_library
from .progress import IndexDiagnostics, IndexProgressBar, single_line
from .setup_connection import discover_executable, inspect_registration, probe_mcp, register


def display(value: object) -> str:
    """Escape terminal controls without losing spaces or Unicode in path displays."""
    return "".join(c if c.isprintable() else json.dumps(c)[1:-1] for c in str(value))


class Terminal:
    def __init__(self, stdin: TextIO, stderr: TextIO):
        self.stdin, self.stderr = stdin, stderr

    def say(self, message: str = "") -> None:
        print(message, file=self.stderr, flush=True)

    def ask(self, prompt: str) -> str:
        print(prompt, end="", file=self.stderr, flush=True)
        line = self.stdin.readline()
        if not line:
            raise EOFError
        return line.rstrip("\r\n")

    def yes(self, prompt: str, *, default: bool = True) -> bool:
        while True:
            answer = self.ask(prompt + (" [Y/n] " if default else " [y/N] ")).strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.say("Enter y or n.")

    def choose(self, choices: str, default: str = "1") -> str:
        while True:
            self.say(choices)
            answer = self.ask(f"> [{default}] ").strip() or default
            if answer in ("1", "2", "3"):
                return answer
            self.say("Enter 1, 2, or 3.")


def parse_library_path(value: str) -> Path:
    """Accept literal, quoted, or shell-escaped paths, without shell expansion."""
    value = value.strip()
    if not value or any(not c.isprintable() for c in value):
        raise ValueError("Enter one file path without control characters")
    literal = Path(value).expanduser()
    # Prefer a real literal filename, including apostrophes/backslashes/spaces.
    if literal.is_file():
        return literal.resolve()
    parts = shlex.split(value)
    if len(parts) == 1:
        value = parts[0]
    return Path(value).expanduser().resolve()


@contextmanager
def private_diagnostics(terminal: Terminal):
    """Reuse parser capture but omit examples that could contain private records."""
    with IndexDiagnostics(stream=io.StringIO()) as diagnostics:
        yield
    if diagnostics.count:
        terminal.say(f"Parser diagnostics: {diagnostics.count} messages (source details omitted).")


def read_index_status(config: Config) -> dict:
    try:
        db = connect(config.database, readonly=True, bib=config.bib, allow_unbound=True)
    except LibraryIdentityError as exc:
        raise SetupProblem(str(exc)) from exc
    except ValueError:
        # A first all-or-nothing build can leave only an empty SQLite header.
        # Recognize it read-only; do not adopt any database with user tables.
        with closing(sqlite3.connect(config.database.resolve().as_uri() + "?mode=ro", uri=True)) as empty:
            if (empty.execute("PRAGMA application_id").fetchone()[0] == 0
                    and empty.execute("PRAGMA user_version").fetchone()[0] == 0
                    and not empty.execute("SELECT 1 FROM sqlite_master WHERE name NOT LIKE "
                                          "'sqlite_%' LIMIT 1").fetchone()):
                raise IncompleteIndex("Index has no completed build; choose update to resume")
        raise
    try:
        result = status(db, config)
    finally:
        db.close()
    # An initialized-but-uncommitted index is not a completed first build.
    if not result["settings"].get("last_indexed"):
        raise IncompleteIndex("Index has no completed build; choose update to resume")
    return result


class SetupProblem(ValueError):
    """A diagnostic known to contain no private bibliography or attachment text."""


class IncompleteIndex(SetupProblem):
    """An initialized index whose first transaction did not complete."""


def check_output_locations(config_path: Path, database: Path) -> None:
    """Keep setup output outside the running Python installation and brew prefix."""
    try:
        check_config_output_locations(config_path, database)
    except ValueError as exc:
        raise SetupProblem("Configuration/index paths are inside a Python or Homebrew installation. "
                           "Choose a separate application-data path with --temp or the "
                           "BIBDESK_RAG_HOME environment variable.") from exc


def read_setup_config(path: Path) -> Config:
    try:
        config = load_config(path)
    except tomllib.TOMLDecodeError:
        raise
    except ValueError as exc:
        # load_config validation concerns paths/options, never bibliography content.
        raise SetupProblem("Configuration error: " + single_line(str(exc), 300) +
                           ". Edit this configuration manually before retrying.") from exc
    check_output_locations(path, config.database)
    return config


def show_counts(terminal: Terminal, result: dict) -> None:
    counts = result["counts"]
    extracted = result["extraction_status"].get("ok", 0)
    excluded = result["extraction_status"].get("excluded", 0)
    terminal.say(f"Papers: {counts['papers']:,}")
    terminal.say(f"Attachments: {counts['attachments']:,}")
    terminal.say(f"Text chunks: {counts['chunks']:,}")
    terminal.say(f"Extraction succeeded: {extracted:,}")
    terminal.say(f"Extraction incomplete/failed/unsupported: {counts['attachments'] - extracted - excluded:,}")
    if excluded:
        terminal.say(f"Explicitly excluded images/videos: {excluded:,}")
    semantic = result["semantic"]
    terminal.say(f"Semantic: {semantic['indexed']:,}/{semantic['eligible']:,} papers; "
                 f"{semantic['vectors']:,} vectors; enabled={semantic['enabled']}")


def manual_commands(terminal: Terminal, config_path: Path) -> None:
    base = ["bibdesk-rag", "--temp", str(config_path)]
    terminal.say("Manual CLI steps (replace /path/to/Library.bib with your library):")
    terminal.say("  " + display(shlex.join([
        "bibdesk-rag", "--config", "create", str(config_path), "--bib", "/path/to/Library.bib",
    ])))
    for action in ("update", "status", "check"):
        terminal.say("  " + display(shlex.join([*base, "--index", action])))
    terminal.say("Creating a configuration also saves its selection. For an existing configuration "
                 "skip create; --index update performs incremental indexing.")
    terminal.say("To remember this configuration for future commands:")
    terminal.say("  " + display(shlex.join(["bibdesk-rag", "--config", "use", str(config_path)])))


def manual_connection(terminal: Terminal, mcp: Path | None, config_path: Path | None) -> None:
    terminal.say("Manual Codex connection: in Codex settings, add a local MCP server (STDIO).")
    terminal.say("  Name: bibdesk-rag")
    if mcp is None:
        terminal.say("  MCP executable was not found; locate it with: command -v bibdesk-rag-mcp")
        terminal.say("  Use the installed executable's absolute path as Command.")
    else:
        terminal.say("  Command: " + display(mcp))
    arguments = ["--temp", str(config_path)] if config_path is not None else []
    if arguments:
        terminal.say("  Arguments (two separate values): " + json.dumps(arguments, ensure_ascii=False))
    else:
        terminal.say("  Arguments: leave empty (follow the selected configuration).")
    if mcp is not None:
        terminal.say("With Codex CLI, after checking any existing bibdesk-rag registration:")
        terminal.say("  " + display(shlex.join([
            "codex", "mcp", "add", "bibdesk-rag", "--", str(mcp), *arguments,
        ])))


@dataclass
class SetupState:
    stage: str = "environment check"
    completed: list[str] = field(default_factory=list)
    index_ready: bool = False
    registered: bool = False
    handshake: bool = False
    embedding_backend: object = None


def configure_semantic(terminal: Terminal, config: Config, path: Path,
                       state: SetupState) -> Config:
    terminal.say("Semantic search compares title/abstract meaning locally on CPU.")
    terminal.say("It does not embed PDF text or generate summaries. A model is needed only "
                 "if you choose this feature; selecting no loads/downloads nothing.")
    if not terminal.yes("Use semantic search?", default=config.semantic.enabled):
        selected = set_semantic_enabled(path, False)
        state.completed.append("Semantic search disabled; stored vectors retained")
        return selected
    from .embeddings import SentenceTransformerBackend, download_model, model_is_cached
    from .semantic import protect

    with private_diagnostics(terminal):
        protect(config, path)
    terminal.say("Model: " + display(config.semantic.model) + " @ "
                 + display(config.semantic.revision))
    try:
        cached = model_is_cached(config.semantic)
    except (ImportError, ValueError) as exc:
        raise SetupProblem("Semantic dependencies are missing. Install the semantic extra "
                           "in this Python environment during installation, then retry setup. "
                           "Homebrew requires a Formula that includes semantic dependencies; "
                           "do not pip-install into Cellar/libexec.") from exc
    if not cached:
        terminal.say("The model is not cached. Only model files will be downloaded; "
                     "no bibliography text is uploaded.")
        if not terminal.yes("Download this model from Hugging Face now?", default=False):
            terminal.say("Model download skipped; semantic search is disabled for now.")
            return set_semantic_enabled(path, False)
        try:
            download_model(config.semantic)
        except Exception as exc:
            raise SetupProblem("Model download failed; configuration/index were retained. "
                               "Check network/cache access and retry --setup.") from exc
    else:
        terminal.say("Cached model found; no download needed.")
    try:
        state.embedding_backend = SentenceTransformerBackend(config.semantic)
    except (ImportError, ValueError, RuntimeError, OSError) as exc:
        raise SetupProblem("The local model could not be loaded. Configuration/index retained; "
                           "check semantic dependencies, model dimensions and token limit.") from exc
    config = set_semantic_enabled(path, True)
    state.completed.append("Semantic search enabled; local model verified")
    terminal.say("All subsequent indexing/search uses the local cache.")
    return config


def select_library(terminal: Terminal, config_path: Path, state: SetupState) -> Config:
    while True:
        try:
            bib = parse_library_path(terminal.ask("Enter the path to your BibDesk .bib file:\n> "))
            if not bib.is_file():
                terminal.say("File does not exist or is not a regular file. Try again.")
                continue
            with private_diagnostics(terminal):
                papers = read_library(bib)
        except (OSError, ValueError, RuntimeError, UnicodeError):
            terminal.say("Cannot read this library: invalid path, encoding, or BibTeX (including "
                         "duplicate citation keys). The source was not changed. Try again.")
            continue
        terminal.say("Library: " + display(bib))
        terminal.say(f"Papers: {len(papers):,}; linked attachments: "
                     f"{len({ref.path for paper in papers for ref in paper.files}):,}")
        terminal.say("The library and attachments are opened read-only.")
        if terminal.yes("Use this library and create the configuration?"):
            check_output_locations(config_path, default_data_dir(config_path) / "index.sqlite3")
            with private_diagnostics(terminal):
                init_config(bib, config_path)
            state.completed.append("Configuration created")
            return read_setup_config(config_path)


def use_existing(terminal: Terminal, config: Config) -> bool:
    terminal.say("Existing configuration found.")
    terminal.say("Library: " + display(config.bib))
    terminal.say("Database: " + display(config.database))
    while True:
        choice = terminal.choose(
            "[1] Continue using existing configuration\n"
            "[2] Show configuration details\n[3] Exit setup"
        )
        if choice != "2":
            return choice == "1"
        terminal.say("Library: " + display(config.bib))
        terminal.say("Database: " + display(config.database))
        terminal.say("Extraction limits: " + json.dumps(asdict(config.extraction), sort_keys=True))


def build_index(terminal: Terminal, config: Config, state: SetupState, config_path=None) -> None:
    if config.database.exists():
        choice = terminal.choose(
            "Existing index found.\n[1] Use existing index\n"
            "[2] Incrementally update (--index update)\n[3] Rebuild all (--index rebuild)"
        )
        if choice == "1":
            result = read_index_status(config)
            state.index_ready = True
            state.completed.append("Existing search index retained")
            show_counts(terminal, result)
            terminal.say("Indexed text may be stale. Use --index update --verify-hashes if needed.")
            return
        # Even an explicit update must not repurpose a different library's index.
        if config.database.stat().st_size:
            try:
                read_index_status(config)
            except IncompleteIndex:
                pass  # Explicit update/rebuild can resume an interrupted first build.
        rebuild = choice == "3"
    else:
        if not terminal.yes("Build the initial search index?"):
            terminal.say("Search index skipped; run --setup again or --index update when ready.")
            return
        rebuild = True
    terminal.say("Rebuilding search index..." if rebuild else "Updating search index...")
    with private_diagnostics(terminal), IndexProgressBar(
        enabled=os.environ.get("TERM") != "dumb", stream=terminal.stderr
    ) as progress:
        result = index_library(config, rebuild=rebuild, progress=progress.update,
                               config_path=config_path, backend=state.embedding_backend)
    # Mark the commit before any subsequent diagnostic can fail or be interrupted.
    state.completed.append("Search index built" if rebuild else "Search index updated")
    terminal.say(f"Index operation complete: {result['papers_added']:,} papers added, "
                 f"{result['papers_changed']:,} changed; "
                 f"{result['files_extracted']:,} extraction attempts, "
                 f"{result['files_reused']:,} reused.")
    if result["errors"]:
        terminal.say(f"Attachment issues: {len(result['errors']):,}; available text remains searchable.")
    show_counts(terminal, read_index_status(config))
    state.index_ready = True


def connect_codex(terminal: Terminal, codex: Path | None, mcp: Path | None,
                  config_path: Path | None, state: SetupState) -> None:
    if config_path is None:
        terminal.say("MCP will follow the selected configuration (no arguments).")
    else:
        terminal.say("MCP will pin this temporary configuration with --temp PATH.")
    if codex is None or mcp is None:
        terminal.say("Codex CLI not found; automatic registration skipped." if codex is None
                     else "MCP executable not found; automatic registration skipped.")
    else:
        registration = inspect_registration(codex, mcp, config_path)
        if registration == "matching":
            terminal.say("Matching MCP registration already exists; no changes made.")
            state.registered = True
        elif registration == "missing":
            if terminal.yes("Register BibDesk RAG as a local MCP server in Codex?"):
                state.registered = register(codex, mcp, config_path)
                if not state.registered:
                    terminal.say("Codex registration failed or could not be verified. "
                                 "BibDesk RAG configuration and index are retained.")
            else:
                terminal.say("Codex registration skipped; no Codex settings changed.")
        elif registration == "conflict":
            terminal.say("A different bibdesk-rag MCP registration exists. "
                         "It was not replaced; review it manually in Codex.")
            if config_path is None:
                terminal.say("To follow the selected configuration, remove both the configuration "
                             "option (--temp or --config) and its path from that registration.")
        else:
            terminal.say("Could not safely inspect existing Codex registrations. "
                         "No registration was changed.")
    if state.registered:
        state.completed.append("MCP registered in Codex (configuration verified)")
    else:
        manual_connection(terminal, mcp, config_path)
    if state.index_ready:
        terminal.say("BibDesk RAG and the search index are usable independently of Codex registration.")


def failure_reason(exc: Exception) -> str:
    # Do not echo arbitrary parser records, SQLite data, or subprocess stderr.
    if isinstance(exc, SetupProblem):
        return str(exc)
    if isinstance(exc, tomllib.TOMLDecodeError):
        return "Invalid TOML syntax: " + single_line(str(exc), 200) + ". Check quoting and table/key syntax."
    if isinstance(exc, PermissionError):
        return "Permission denied; check access to the selected configuration, library, and index."
    if isinstance(exc, FileNotFoundError):
        return "A required file is missing; check the configured library and database paths."
    if isinstance(exc, sqlite3.Error):
        return "Cannot read or update the SQLite index; use --index check with the same --temp."
    if isinstance(exc, ValueError):
        # Config validation exceptions contain option names/paths but no source text.
        return "Invalid configuration, library, or index. Check bib/database paths, source/output " \
               "collisions, TOML keys and extraction limits; run --index check with the same --temp."
    return f"Operation failed ({type(exc).__name__}); check file access and retry setup."


def run_setup(config_path: Path | None = None, *, remember: bool = True,
              stdin: TextIO | None = None, stderr: TextIO | None = None) -> int:
    terminal = Terminal(stdin if stdin is not None else sys.stdin,
                        stderr if stderr is not None else sys.stderr)
    state = SetupState()
    path = config_path
    try:
        path = Path(os.path.abspath((config_path or default_config_path()).expanduser()))
        if not terminal.stdin.isatty() or not terminal.stderr.isatty():
            terminal.say("Interactive setup requires TTY stdin and stderr; non-interactive setup "
                         "cannot wait for input.")
            manual_commands(terminal, path)
            return 1
        terminal.say("BibDesk RAG Setup")
        terminal.say(f"Version: {__version__}; platform: {sys.platform}")
        if sys.platform != "darwin":
            terminal.say("macOS was not detected; continuing with this platform's local paths.")
        terminal.say("Configuration: " + display(path))
        mcp = discover_executable("bibdesk-rag-mcp")
        codex = discover_executable("codex")
        terminal.say("MCP executable: " + (display(mcp) if mcp else "not found"))
        terminal.say("Codex CLI: " + (display(codex) if codex else "not found"))
        state.stage = "[1/6] Select your BibDesk library"
        terminal.say("\n" + state.stage)
        if path.exists() or path.is_symlink():
            config = read_setup_config(path)
            state.completed.append("Existing configuration loaded")
            terminal.say("Index: " + ("present" if config.database.exists() else "not yet created"))
            if not use_existing(terminal, config):
                terminal.say("Setup exited; existing configuration retained.")
                return 0
        else:
            terminal.say("No existing configuration found.")
            config = select_library(terminal, path, state)
        state.completed.append("Library registered")
        if remember:
            with private_diagnostics(terminal):
                activate_config(path)
            state.completed.append("Configuration selected for future commands")
            terminal.say("Configuration selection saved. Next time, use bibdesk-rag --index update.")
            if default_config_path() != path.resolve():
                terminal.say("BIBDESK_RAG_CONFIG currently overrides this selection; unset it "
                             "to use the saved configuration.")
        else:
            state.completed.append("Temporary configuration used for this setup only")
            terminal.say("Temporary configuration selection; saved selection unchanged.")
            terminal.say("Configuration and index work is retained. To select this configuration "
                         "for future commands:")
            terminal.say("  " + display(shlex.join([
                "bibdesk-rag", "--config", "use", str(path),
            ])))
        state.stage = "[2/6] Choose semantic search"
        terminal.say("\n" + state.stage)
        config = configure_semantic(terminal, config, path, state)
        state.stage = "[3/6] Build search index"
        terminal.say("\n" + state.stage)
        build_index(terminal, config, state, path)
        state.stage = "[4/6] Connect to Codex"
        terminal.say("\n" + state.stage)
        mcp_config = None if remember else path
        connect_codex(terminal, codex, mcp, mcp_config, state)
        state.stage = "[5/6] Verify local connection"
        terminal.say("\n" + state.stage)
        checked_config = read_setup_config(path)
        terminal.say("Configuration readable.")
        if state.index_ready:
            checked_status = read_index_status(checked_config)
            terminal.say("Search index opened read-only; status retrieved.")
            semantic_status = checked_status["semantic"]
            if checked_config.semantic.enabled and (
                semantic_status["missing"] or semantic_status["stale"]
                or state.embedding_backend is None
                or semantic_status["model"] != state.embedding_backend.info.as_dict()
            ):
                terminal.say("Semantic vectors are not ready; the existing keyword/text index "
                             "was retained as chosen. Run --index update before semantic search.")
        if mcp is not None:
            terminal.say("MCP executable: " + display(mcp))
            if state.index_ready:
                state.handshake = probe_mcp(mcp, mcp_config)
                if state.handshake:
                    state.completed.append("MCP server handshake verified (initialize + tools/list)")
                else:
                    terminal.say("MCP server handshake failed or was not verified. "
                                 "Configuration and search index are retained.")
        else:
            terminal.say("MCP server handshake not verified: executable not found.")
        state.stage = "[6/6] Finish"
        terminal.say("\n" + state.stage)
        terminal.say("BibDesk RAG Setup Complete" if state.index_ready
                     else "BibDesk RAG Setup Finished (index creation skipped)")
        for item in state.completed:
            terminal.say("✓ " + item)
        if not state.registered:
            terminal.say("- Codex MCP registration not verified; use the manual connection details above.")
        if not state.handshake:
            terminal.say("- MCP server handshake not verified.")
        terminal.say("- Actual search from Codex is not verified.")
        if state.index_ready:
            terminal.say('Next step: after connecting, restart Codex and ask:\n'
                         '"Use bibdesk-rag to find papers about RecQ."')
        else:
            resume = ["bibdesk-rag", *(["--temp", str(path)] if not remember else []), "--setup"]
            terminal.say("Next step: build the search index with " + display(shlex.join(resume)))
        return 0
    except (KeyboardInterrupt, EOFError) as exc:
        terminal.say(f"\nSetup interrupted at {state.stage} "
                     f"({'Ctrl+C' if isinstance(exc, KeyboardInterrupt) else 'EOF'}).")
        code = 130 if isinstance(exc, KeyboardInterrupt) else 1
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error) as exc:
        terminal.say(f"\nSetup stopped at {state.stage}: {failure_reason(exc)}")
        terminal.say("Existing configuration is not automatically repaired or replaced. "
                     "Review its paths and options manually before retrying.")
        code = 1
    terminal.say("Completed: " + ("; ".join(state.completed) or "none"))
    terminal.say("Completed configuration/index work is retained; rerun --setup to resume.")
    if path is not None:
        terminal.say("Configuration: " + display(path))
        if not remember:
            terminal.say("Resume with: " + display(shlex.join([
                "bibdesk-rag", "--temp", str(path), "--setup",
            ])))
    return code
