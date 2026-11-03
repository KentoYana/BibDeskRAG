"""Public option grammar, local information resources, and side-effect boundaries."""

import hashlib
import json
import socket
import tomllib

import pytest

from bibdesk_rag import cli
from bibdesk_rag.config import active_config_path, load_config


def snapshot(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def run(capsys, *arguments):
    try:
        code = cli.main([str(argument) for argument in arguments])
    except SystemExit as exc:
        code = exc.code
    output = capsys.readouterr()
    return code, output.out, output.err


@pytest.fixture
def forbid_application_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Argument validation/information output accessed application data or network")

    for name in ("load_config", "init_config", "activate_config", "connect", "index_library"):
        monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.mark.parametrize("arguments", [
    (), ("-h",), ("--help",), ("-v",), ("--version",), ("-e",), ("--example",),
    ("-r",), ("--readme",), ("-o", "manual"), ("--output", "config-template"),
    ("--output", "citation"),
])
def test_information_works_without_settings_and_never_creates_files(
    tmp_path, monkeypatch, capsys, forbid_application_io, arguments
):
    monkeypatch.chdir(tmp_path)
    # An invalid selection must not prevent help or bundled resources from working.
    selector = active_config_path()
    selector.parent.mkdir(parents=True)
    selector.write_text("invalid selection")
    before = snapshot(tmp_path)
    code, output, error = run(capsys, *arguments)
    assert code == 0, error
    assert output.strip()
    assert snapshot(tmp_path) == before


def test_help_examples_and_resources_describe_current_public_grammar(
    capsys, forbid_application_io
):
    code, help_text, _ = run(capsys, "--help")
    assert code == 0
    for flag in ("--config", "--index", "--paper", "--setup", "--temp", "--format",
                 "--example", "--readme", "--output"):
        assert flag in help_text
    code, brief_help, _ = run(capsys)
    assert code == 0 and len(brief_help.splitlines()) < len(help_text.splitlines())
    for flag in ("--config", "--index", "--paper", "--setup", "--help"):
        assert flag in brief_help
    assert "--verify-hashes" in help_text and "--verify-hashes" not in brief_help
    code, examples, _ = run(capsys, "--example")
    assert code == 0
    assert "--index update" in examples and "--paper search" in examples
    code, manual, _ = run(capsys, "--output", "manual")
    assert code == 0
    assert "--config" in manual and "--format" in manual
    code, template, _ = run(capsys, "--output", "config-template")
    assert code == 0
    configuration = tomllib.loads(template)
    assert isinstance(configuration["bib"], str) and isinstance(configuration["database"], str)
    assert configuration["extraction"]["chunk_size"] > 0
    code, citation, _ = run(capsys, "--output", "citation")
    assert code == 0
    assert citation.startswith("@manual{BibDeskRAG,")
    assert "author = {Kento Yanagisawa}" in citation
    assert "https://github.com/KentoYana/BibDeskRAG" in citation
    from bibdesk_rag import __version__
    assert __version__ in citation
    code, version, _ = run(capsys, "--version")
    assert code == 0 and __version__ in version
    assert "Citation" in version or "citation" in version


@pytest.mark.parametrize("arguments", [
    ("--config",), ("--config", "unknown"), ("--config", "show", "unexpected"),
    ("--config", "use"), ("--config", "use", "one", "two"),
    ("--config", "create"), ("--config", "create", "one", "two", "--bib", "source.bib"),
    ("--temp", "other.toml", "--config", "create", "--bib", "source.bib"),
    ("--temp", "other.toml", "--config", "use", "selected.toml"),
    ("--index",), ("--index", "unknown"), ("--index", "update", "extra"),
    ("--paper",), ("--paper", "show"), ("--paper", "search"),
    ("--paper", "show", "key", "extra"), ("--paper", "unknown", "key"),
    ("--config", "path", "--index", "update"),
    ("--index", "update", "--index", "rebuild"),
    ("--config", "show", "-c", "path"), ("--paper", "show", "key", "--setup"),
    ("--version", "--index", "update"), ("--example", "--output", "manual"),
    ("--format", "json"), ("--temp", "other.toml"),
    ("--index", "update", "--scope", "fulltext"),
    ("--index", "status", "--verify-hashes"), ("--index", "check", "--no-progress"),
    ("--config", "show", "--bib", "source.bib"),
    ("--config", "path", "--verbose"), ("--setup", "--format", "json"),
    ("--paper", "show", "key", "--top", "5"),
    ("--paper", "attachments", "key", "--format", "bibtex"),
    ("--paper", "search", "query", "--format", "bibtex"),
    ("--paper", "search", "query", "--max-chars", "1000"),
    ("--paper", "context", "query", "--scope", "fulltext"),
    ("--paper", "search", "query", "--doi", "10.1234/x"),
    ("--paper", "search", "query", "--scope", "metadata", "--per-paper", "1"),
    ("--paper", "search", "query", "--scope", "metadata", "--metadata-query", "extra"),
    ("--paper", "search", "query", "--scope", "fulltext", "--metadata-query", "extra"),
    ("--paper", "search", "query", "--citekey", "First", "--metadata-query", "Other"),
    ("--paper", "context", "query", "--citekey", "First", "--metadata-query", "Other"),
    ("--paper", "search", "query", "--top", "0"),
    ("--paper", "search", "query", "--per-paper", "11"),
    ("--paper", "context", "query", "--max-chars", "100001"),
    ("--version", "--temp", "other.toml"),
    ("--output", "manual", "--format", "json"),
    ("--index", "update", "--json"), ("--ind", "update"),
])
def test_invalid_or_unrelated_options_fail_before_application_io(
    tmp_path, capsys, forbid_application_io, arguments
):
    before = snapshot(tmp_path)
    code, output, error = run(capsys, *arguments)
    assert code == 2, (arguments, code, output, error)
    assert "error" in error.lower()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("arguments,replacement", [
    (("init", "--bib", "source.bib"), "--config"),
    (("config", "show"), "--config"),
    (("index",), "--index"), (("update",), "--index"),
    (("doctor",), "--index"), (("get", "key"), "--paper"),
    (("search", "query"), "--paper"), (("setup",), "--setup"),
])
def test_old_subcommands_report_a_migration_hint(capsys, forbid_application_io, arguments, replacement):
    code, output, error = run(capsys, *arguments)
    assert code == 2 and not output
    assert replacement in error


def test_create_explicit_path_is_remembered_and_existing_config_is_preserved(tmp_path, capsys):
    bib = tmp_path / "source.bib"
    bib.write_text("@article{Synthetic2026,title={Generated paper}}\n")
    before = bib.read_bytes()
    config = tmp_path / "custom settings/選択.toml"
    database = tmp_path / "derived/index.sqlite3"
    code, output, error = run(
        capsys, "-c", "create", config, "--bib", bib, "--data-dir", database.parent,
        "--format", "json",
    )
    assert code == 0, error
    assert json.loads(output)["config"] == str(config)
    assert load_config().database == database
    assert load_config().bib == bib
    assert bib.read_bytes() == before and not database.exists()
    saved = snapshot(tmp_path)
    code, output, error = run(capsys, "--config", "create", config, "--bib", bib)
    assert code == 1 and not output and error
    assert snapshot(tmp_path) == saved
    code, output, error = run(capsys, "-c", "path")
    assert code == 0 and output.strip() == str(config)


def test_create_without_path_uses_default_destination_not_saved_custom_config(tmp_path, capsys):
    first_bib = tmp_path / "first.bib"
    second_bib = tmp_path / "second.bib"
    first_bib.write_text("@article{First,title={Generated first}}\n")
    second_bib.write_text("@article{Second,title={Generated second}}\n")
    custom = tmp_path / "custom/config.toml"
    code, _, error = run(capsys, "--config", "create", custom, "--bib", first_bib)
    assert code == 0, error
    custom_before = custom.read_bytes()
    code, output, error = run(
        capsys, "--config", "create", "--bib", second_bib, "--format", "json",
    )
    assert code == 0, error
    default = tmp_path / ".config/bibdesk-rag/config.toml"
    assert json.loads(output)["config"] == str(default)
    assert custom.read_bytes() == custom_before
    assert load_config().bib == second_bib
    assert load_config().database == tmp_path / ".local/share/bibdesk-rag/index.sqlite3"


def test_manual_pager_ignores_shell_environment_and_disables_external_commands(monkeypatch):
    from io import StringIO
    from types import SimpleNamespace
    from bibdesk_rag import cli_resources

    class Terminal(StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(cli_resources.sys, "stdin", Terminal())
    monkeypatch.setattr(cli_resources.sys, "stdout", Terminal())
    monkeypatch.setattr(cli_resources.shutil, "which", lambda name: "/synthetic/bin/less")
    monkeypatch.setenv("PAGER", "untrusted command with shell syntax")
    monkeypatch.setenv("LESS", "untrusted flags")
    monkeypatch.setenv("LESSOPEN", "untrusted preprocessing")
    calls = []

    def run_pager(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_resources.subprocess, "run", run_pager)
    cli_resources.show_manual()
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[0] == "/synthetic/bin/less"
    assert kwargs["input"] == cli_resources.manual_text()
    assert kwargs.get("shell", False) is False
    assert kwargs["env"]["LESSSECURE"] == "1"
    assert "LESS" not in kwargs["env"] and "LESSOPEN" not in kwargs["env"]
