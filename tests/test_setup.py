"""Exercise setup with generated sources and isolated terminal/command doubles."""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path
import runpy
import shlex
import sys

import pytest

from bibdesk_rag import cli
from bibdesk_rag import setup
from bibdesk_rag.config import (
    activate_config, active_config_path, default_config_path, init_config, load_config,
)
from bibdesk_rag.database import connect, doctor, initialize, status
from bibdesk_rag.indexer import index_library


class Terminal(StringIO):
    def __init__(self, events=(), *, tty=True):
        super().__init__()
        self.events = iter(events)
        self.tty = tty
        self.reads = 0

    def isatty(self):
        return self.tty

    def readline(self, *args):
        self.reads += 1
        event = next(self.events, None)
        if isinstance(event, BaseException):
            raise event
        return "" if event is None else event + "\n"


@pytest.fixture(autouse=True)
def isolated_setup(monkeypatch, tmp_path):
    for name in (
        "BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(tmp_path / "application data"))
    monkeypatch.setattr(setup, "discover_executable", lambda name: None)


@pytest.fixture
def sources(tmp_path):
    directory = tmp_path / "資料 with spaces"
    directory.mkdir()
    pdf = directory / "論文.pdf"
    make_pdf = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/package_smoke.py")
    )["synthetic_pdf"]
    pdf.write_bytes(make_pdf())
    bib = directory / "文献 ライブラリ.bib"
    bib.write_text(
        "@article{Synthetic2026,title={RecQ synthetic evidence},"
        "year={2026},Bdsk-File-1={論文.pdf}}\n",
        encoding="utf-8",
    )
    config = tmp_path / "custom settings" / "選択.toml"
    return config, bib, pdf


def fingerprints(*paths):
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def invoke(config, *events):
    stdin, stderr = Terminal(events), Terminal()
    code = setup.run_setup(config, stdin=stdin, stderr=stderr)
    return code, stderr.getvalue()


def index_status(config_path):
    config = load_config(config_path)
    db = connect(config.database, readonly=True)
    try:
        assert doctor(db)["ok"]
        return status(db)
    finally:
        db.close()


def index_dump(config_path):
    db = connect(load_config(config_path).database, readonly=True)
    try:
        return list(db.iterdump())
    finally:
        db.close()


def existing(sources, *, indexed=True):
    config_path, bib, _ = sources
    init_config(bib, config_path)
    if indexed:
        index_library(load_config(config_path))
    return config_path


@pytest.mark.parametrize("style", ["literal", "quoted", "escaped", "relative", "tilde"])
def test_new_setup_indexes_unicode_paths_without_touching_sources(
    sources, monkeypatch, tmp_path, style
):
    config, bib, pdf = sources
    before = fingerprints(bib, pdf)
    value = str(bib)
    if style == "quoted":
        value = shlex.quote(value)
    elif style == "escaped":
        value = value.replace(" ", "\\ ")
    elif style == "relative":
        monkeypatch.chdir(tmp_path)
        value = str(bib.relative_to(tmp_path))
    elif style == "tilde":
        monkeypatch.setenv("HOME", str(tmp_path))
        value = "~/" + str(bib.relative_to(tmp_path))
    code, output = invoke(config, value, "y", "y")
    assert code == 0, output
    assert load_config(config).bib == bib.resolve()
    assert default_config_path() == config.resolve()
    result = index_status(config)
    assert result["counts"] == {"papers": 1, "attachments": 1, "chunks": 2}
    assert result["extraction_status"] == {"ok": 1}
    assert fingerprints(bib, pdf) == before
    assert str(config) in output
    assert "Codex" in output
    assert "Traceback" not in output


def test_invalid_path_reprompts_then_finishes(sources):
    config, bib, _ = sources
    code, output = invoke(config, str(bib.parent / "missing.bib"), str(bib), "y", "y")
    assert code == 0, output
    assert index_status(config)["counts"]["papers"] == 1


def test_malformed_bibtex_reprompts_without_changing_source(sources):
    config, bib, pdf = sources
    invalid = bib.parent / "invalid.bib"
    invalid.write_text("@article{PrivateKey,title={Private content with missing brace")
    before = fingerprints(invalid, bib, pdf)
    code, output = invoke(config, str(invalid), str(bib), "y", "y")
    assert code == 0, output
    assert fingerprints(invalid, bib, pdf) == before
    assert load_config(config).bib == bib
    assert "Private content" not in output


def test_existing_configuration_and_index_are_reused_by_default(sources, monkeypatch):
    config = existing(sources)
    database = load_config(config).database
    before = fingerprints(config, database, *sources[1:])

    def forbidden(*args, **kwargs):
        pytest.fail("Existing settings/index must not be initialized or rebuilt")

    monkeypatch.setattr(setup, "init_config", forbidden)
    monkeypatch.setattr(setup, "index_library", forbidden)
    code, output = invoke(config, "", "")
    assert code == 0, output
    assert fingerprints(config, database, *sources[1:]) == before
    assert default_config_path() == config.resolve()


def test_show_existing_configuration_then_exit_preserves_files(sources):
    config = existing(sources)
    database = load_config(config).database
    before = fingerprints(config, database, *sources[1:])
    code, output = invoke(config, "2", "3")
    assert code == 0, output
    assert str(sources[1]) in output and str(database) in output
    assert fingerprints(config, database, *sources[1:]) == before
    assert not active_config_path().exists()


@pytest.mark.parametrize("choice,rebuild", [("2", False), ("3", True)])
def test_index_mutation_requires_explicit_choice(sources, monkeypatch, choice, rebuild):
    config = existing(sources)
    calls = []

    def traced(selected, **kwargs):
        calls.append((selected, kwargs))
        return index_library(selected, **kwargs)

    monkeypatch.setattr(setup, "index_library", traced)
    code, output = invoke(config, "1", choice)
    assert code == 0, output
    assert len(calls) == 1
    assert calls[0][0].database == load_config(config).database
    assert calls[0][1]["rebuild"] is rebuild


def test_invalid_existing_configuration_is_not_repaired(sources):
    config, bib, pdf = sources
    config.parent.mkdir()
    config.write_text('bib = "unterminated')
    before = fingerprints(config, bib, pdf)
    code, output = invoke(config)
    assert code == 1
    assert fingerprints(config, bib, pdf) == before
    assert "Traceback" not in output
    assert "config" in output.lower()


@pytest.mark.parametrize("event,code", [(KeyboardInterrupt(), 130), (EOFError(), 1), (None, 1)])
@pytest.mark.parametrize("stage", ["library", "confirmation", "index"])
def test_interrupt_new_setup_preserves_sources_and_completed_configuration(
    sources, event, code, stage
):
    config, bib, pdf = sources
    before = fingerprints(bib, pdf)
    events = {
        "library": [event],
        "confirmation": [str(bib), event],
        "index": [str(bib), "y", event],
    }[stage]
    actual, output = invoke(config, *events)
    assert actual == code, output
    assert fingerprints(bib, pdf) == before
    assert config.exists() == (stage == "index")
    if config.exists():
        assert load_config(config).bib == bib
        assert not load_config(config).database.exists()
        assert default_config_path() == config.resolve()
    else:
        assert not active_config_path().exists()
    assert "Traceback" not in output
    assert "completed" in output.lower()


@pytest.mark.parametrize("event,code", [(KeyboardInterrupt(), 130), (None, 1)])
def test_existing_setup_cancel_preserves_originals_config_and_index(sources, event, code):
    config = existing(sources)
    database = load_config(config).database
    before = fingerprints(config, database, *sources[1:])
    actual, output = invoke(config, "1", event)
    assert actual == code, output
    assert fingerprints(config, database, *sources[1:]) == before
    assert "Traceback" not in output


@pytest.mark.parametrize("stdin_tty,stderr_tty", [(False, True), (True, False), (False, False)])
def test_non_tty_never_reads_or_creates_files(sources, stdin_tty, stderr_tty):
    config, bib, _ = sources
    stdin = Terminal([str(bib), "y", "y"], tty=stdin_tty)
    stderr = Terminal(tty=stderr_tty)
    assert setup.run_setup(config, stdin=stdin, stderr=stderr) == 1
    assert stdin.reads == 0
    assert not config.exists()
    output = stderr.getvalue()
    assert "--config create" in output and "--index update" in output
    assert str(config) in output


def test_cli_help_works_without_terminal_and_setup_receives_temporary_config(
    sources, monkeypatch, capsys
):
    config, _, _ = sources
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--setup", "--help"])
    assert stopped.value.code == 0
    assert "setup" in capsys.readouterr().out
    stdin, stderr = Terminal(tty=False), Terminal(tty=False)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stderr", stderr)
    assert cli.main(["--temp", str(config), "--setup"]) == 1
    assert stdin.reads == 0
    assert str(config) in stderr.getvalue()


@pytest.mark.parametrize("index_action,expected", [("y", 0), (KeyboardInterrupt(), 130)])
def test_temporary_setup_preserves_saved_selection_even_after_cancellation(
    sources, monkeypatch, tmp_path, index_action, expected
):
    temporary, bib, pdf = sources
    saved = tmp_path / "saved settings/config.toml"
    init_config(bib, saved, tmp_path / "saved data")
    index_library(load_config(saved))
    activate_config(saved)
    before = fingerprints(saved, load_config(saved).database, active_config_path(), bib, pdf)
    stdin, stderr = Terminal([str(bib), "y", index_action]), Terminal()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stderr", stderr)
    assert cli.main(["--temp", str(temporary), "--setup"]) == expected, stderr.getvalue()
    assert temporary.exists()
    assert default_config_path() == saved
    assert fingerprints(*before) == before
    if expected == 0:
        assert index_status(temporary)["counts"]["papers"] == 1
        assert "Configuration selection saved" not in stderr.getvalue()
    else:
        assert not load_config(temporary).database.exists()


def test_cli_setup_without_temp_remembers_environment_selected_config(sources, monkeypatch):
    config, bib, _ = sources
    monkeypatch.setenv("BIBDESK_RAG_CONFIG", str(config))
    stdin, stderr = Terminal([str(bib), "y", "y"]), Terminal()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stderr", stderr)
    assert cli.main(["--setup"]) == 0, stderr.getvalue()
    monkeypatch.delenv("BIBDESK_RAG_CONFIG")
    assert default_config_path() == config
    assert index_status(config)["counts"]["papers"] == 1


def test_failed_initial_index_keeps_configuration_and_can_resume(sources, monkeypatch):
    config, bib, pdf = sources
    before = fingerprints(bib, pdf)

    def fail(*args, **kwargs):
        raise OSError("synthetic disk failure")

    with monkeypatch.context() as patch:
        patch.setattr(setup, "index_library", fail)
        code, output = invoke(config, str(bib), "y", "y")
    assert code == 1, output
    assert config.exists()
    saved = config.read_bytes()
    assert fingerprints(bib, pdf) == before
    code, output = invoke(None, "1", "y")
    assert code == 0, output
    assert config.read_bytes() == saved
    assert index_status(config)["counts"]["papers"] == 1


def test_interrupt_during_update_rolls_back_transaction(sources, monkeypatch):
    config = existing(sources)
    before = fingerprints(config, *sources[1:])
    records_before = index_dump(config)
    import bibdesk_rag.indexer as indexer

    original = indexer._index_attachment

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(indexer, "_index_attachment", interrupted)
    code, output = invoke(config, "1", "2")
    assert code == 130, output
    assert fingerprints(config, *sources[1:]) == before
    assert index_dump(config) == records_before
    assert index_status(config)["counts"]["papers"] == 1
    assert "Traceback" not in output


def test_attachment_extraction_failures_do_not_abort_successful_index(sources):
    config, bib, pdf = sources
    pdf.write_bytes(b"not a PDF")
    before = fingerprints(bib, pdf)
    code, output = invoke(config, str(bib), "y", "y")
    assert code == 0, output
    result = index_status(config)
    assert result["counts"]["papers"] == result["counts"]["attachments"] == 1
    assert result["counts"]["chunks"] == 0
    assert result["extraction_status"] != {"ok": 1}
    assert fingerprints(bib, pdf) == before


def test_path_shell_metacharacters_are_literal_and_never_executed(sources, monkeypatch):
    config, bib, pdf = sources
    monkeypatch.chdir(bib.parent)
    crafted = bib.parent / "$(touch SHOULD_NOT_EXIST); `touch ALSO_NOT_CREATED`.bib"
    crafted.write_bytes(bib.read_bytes())
    before = fingerprints(crafted, pdf)
    code, output = invoke(config, shlex.quote(str(crafted)), "y", "y")
    assert code == 0, output
    assert load_config(config).bib == crafted
    assert fingerprints(crafted, pdf) == before
    assert not (bib.parent / "SHOULD_NOT_EXIST").exists()
    assert not (bib.parent / "ALSO_NOT_CREATED").exists()


@pytest.mark.parametrize("collision", ["bib", "attachment", "hardlink"])
def test_output_source_collision_never_overwrites_sources(sources, monkeypatch, collision):
    config, bib, pdf = sources
    data = config.parent
    data.mkdir()
    database = data / "index.sqlite3"
    if collision == "hardlink":
        database.hardlink_to(pdf)
    else:
        source = bib if collision == "bib" else pdf
        database.symlink_to(source)
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(data))
    before = fingerprints(bib, pdf, database)
    code, output = invoke(config, str(bib), "y", "y")
    assert code == 1, output
    assert fingerprints(bib, pdf, database) == before
    assert not config.exists()


def fake_connection(monkeypatch, tmp_path, *, state="missing", registered=True, handshake=True):
    mcp, codex = tmp_path / "bin/bibdesk-rag-mcp", tmp_path / "bin/codex"
    mcp.parent.mkdir(exist_ok=True)
    for executable in (mcp, codex):
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o700)
    calls = []

    def discover(name):
        return {"bibdesk-rag-mcp": mcp, "codex": codex}.get(name)

    def inspect(*args, **kwargs):
        calls.append(("inspect", args))
        return state

    def register(*args, **kwargs):
        calls.append(("register", args))
        return registered

    def probe(*args, **kwargs):
        calls.append(("probe", args))
        return handshake

    monkeypatch.setattr(setup, "discover_executable", discover)
    monkeypatch.setattr(setup, "inspect_registration", inspect)
    monkeypatch.setattr(setup, "register", register)
    monkeypatch.setattr(setup, "probe_mcp", probe)
    return calls, codex, mcp


@pytest.mark.parametrize("state", ["matching", "conflict", "unknown"])
def test_existing_or_uncertain_codex_registration_is_never_replaced(
    sources, monkeypatch, tmp_path, state
):
    config = existing(sources)
    calls, _, _ = fake_connection(monkeypatch, tmp_path, state=state)
    code, output = invoke(config, "1", "1")
    assert code == 0, output
    assert not any(name == "register" for name, _ in calls)
    assert index_status(config)["counts"]["papers"] == 1


def test_declining_codex_registration_leaves_index_ready(sources, monkeypatch, tmp_path):
    config = existing(sources)
    calls, _, _ = fake_connection(monkeypatch, tmp_path)
    code, output = invoke(config, "1", "1", "n")
    assert code == 0, output
    assert not any(name == "register" for name, _ in calls)
    assert index_status(config)["counts"]["papers"] == 1


@pytest.mark.parametrize("registered", [True, False])
def test_codex_registration_result_is_separate_from_index_and_follows_custom_selection(
    sources, monkeypatch, tmp_path, registered
):
    config, bib, _ = sources
    calls, codex, mcp = fake_connection(monkeypatch, tmp_path, registered=registered)
    code, output = invoke(config, str(bib), "y", "y", "y")
    assert code == 0, output
    assert ("inspect", (codex, mcp, None)) in calls
    assert ("register", (codex, mcp, None)) in calls
    assert ("probe", (mcp, None)) in calls
    assert default_config_path() == config.resolve()
    assert "MCP will follow the selected configuration (no arguments)" in output
    assert index_status(config)["counts"]["papers"] == 1
    assert "Actual search from Codex is not verified" in output


def test_codex_registration_does_not_imply_successful_mcp_handshake(
    sources, monkeypatch, tmp_path
):
    config = existing(sources)
    fake_connection(monkeypatch, tmp_path, state="matching", handshake=False)
    code, output = invoke(config, "1", "1")
    assert code == 0, output
    assert "✓ MCP server handshake verified" not in output
    assert "Actual search from Codex is not verified" in output


def test_without_codex_cli_manual_connection_uses_detected_absolute_paths(
    sources, monkeypatch, tmp_path
):
    config, bib, _ = sources
    calls, _, mcp = fake_connection(monkeypatch, tmp_path)
    monkeypatch.setattr(
        setup, "discover_executable", lambda name: mcp if name == "bibdesk-rag-mcp" else None
    )
    code, output = invoke(config, str(bib), "y", "y")
    assert code == 0, output
    assert str(mcp) in output and str(config.resolve()) in output
    assert not any(name in {"inspect", "register"} for name, _ in calls)
    assert ("probe", (mcp, None)) in calls
    assert "Arguments: leave empty" in output
    command = next(line.strip() for line in output.splitlines() if "codex mcp add" in line)
    assert shlex.split(command) == ["codex", "mcp", "add", "bibdesk-rag", "--", str(mcp)]
    assert index_status(config)["counts"]["papers"] == 1


@pytest.mark.parametrize("has_codex", [True, False])
def test_temporary_setup_pins_registration_and_probe_without_changing_selection(
    sources, monkeypatch, tmp_path, has_codex,
):
    temporary, bib, pdf = sources
    saved = tmp_path / "saved/config.toml"
    init_config(bib, saved, tmp_path / "saved data")
    index_library(load_config(saved))
    activate_config(saved)
    before = fingerprints(saved, load_config(saved).database, active_config_path(), bib, pdf)
    calls, codex, mcp = fake_connection(monkeypatch, tmp_path)
    if not has_codex:
        monkeypatch.setattr(
            setup, "discover_executable", lambda name: mcp if name == "bibdesk-rag-mcp" else None
        )
    stdin, stderr = Terminal([str(bib), "y", "y", "y"]), Terminal()
    assert setup.run_setup(temporary, stdin=stdin, stderr=stderr, remember=False) == 0
    assert ("probe", (mcp, temporary.resolve())) in calls
    if has_codex:
        assert ("inspect", (codex, mcp, temporary.resolve())) in calls
        assert ("register", (codex, mcp, temporary.resolve())) in calls
    else:
        output = stderr.getvalue()
        command = next(line.strip() for line in output.splitlines() if "codex mcp add" in line)
        assert shlex.split(command) == [
            "codex", "mcp", "add", "bibdesk-rag", "--", str(mcp), "--temp", str(temporary),
        ]
        assert "Arguments (two separate values)" in output
    assert default_config_path() == saved
    assert fingerprints(*before) == before


def test_missing_mcp_executable_does_not_attempt_codex_registration(
    sources, monkeypatch, tmp_path
):
    config = existing(sources)
    calls, codex, _ = fake_connection(monkeypatch, tmp_path)
    monkeypatch.setattr(
        setup, "discover_executable", lambda name: codex if name == "codex" else None
    )
    code, output = invoke(config, "1", "1")
    assert code == 0, output
    assert calls == []
    assert index_status(config)["counts"]["papers"] == 1


def test_declined_initial_index_is_reported_and_can_resume(sources):
    config, bib, _ = sources
    code, output = invoke(config, str(bib), "y", "n")
    assert code == 0, output
    assert config.exists() and not load_config(config).database.exists()
    assert "✓ Search index ready" not in output
    assert "BibDesk RAG Setup Complete" not in output
    saved = config.read_bytes()
    code, output = invoke(config, "1", "y")
    assert code == 0, output
    assert config.read_bytes() == saved
    assert index_status(config)["counts"]["papers"] == 1


def test_eof_before_codex_approval_keeps_completed_index(sources, monkeypatch, tmp_path):
    config, bib, _ = sources
    calls, _, _ = fake_connection(monkeypatch, tmp_path)
    code, output = invoke(config, str(bib), "y", "y", None)
    assert code == 1, output
    assert config.exists()
    assert index_status(config)["counts"]["papers"] == 1
    assert not any(name == "register" for name, _ in calls)
    assert "completed" in output.lower()
    assert "Traceback" not in output


def test_corrupt_existing_index_is_reported_without_overwriting(sources):
    config = existing(sources, indexed=False)
    database = load_config(config).database
    database.parent.mkdir(exist_ok=True)
    database.write_bytes(b"not an SQLite database")
    before = fingerprints(config, database, *sources[1:])
    code, output = invoke(config, "1", "1")
    assert code == 1, output
    assert fingerprints(config, database, *sources[1:]) == before
    assert "Traceback" not in output


def test_invalid_existing_extraction_option_explains_sanitized_cause(sources):
    config = existing(sources, indexed=False)
    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n"unknown\\u001b[31m_option" = 1\n')
    before = fingerprints(config, *sources[1:])
    code, output = invoke(config)
    assert code == 1
    assert "Unknown extraction options:" in output
    assert "unknown" in output and "_option" in output
    assert "Edit this configuration manually" in output
    assert "\x1b" not in output
    assert "Traceback" not in output
    assert fingerprints(config, *sources[1:]) == before


@pytest.mark.parametrize("installation", ["python", "base_python", "homebrew"])
@pytest.mark.parametrize("destination", ["config", "database"])
def test_setup_refuses_output_in_python_or_homebrew_before_creation(
    sources, monkeypatch, tmp_path, installation, destination
):
    config, bib, pdf = sources
    prefix = tmp_path / "synthetic installation"
    if installation == "base_python":
        monkeypatch.setattr(sys, "base_prefix", str(prefix))
    elif installation == "homebrew":
        monkeypatch.setattr(sys, "prefix", str(prefix / "Cellar/bibdesk-rag/0.1.1/libexec"))
    else:
        monkeypatch.setattr(sys, "prefix", str(prefix))
    if destination == "config":
        config = prefix / "settings/config.toml"
    else:
        monkeypatch.setenv("BIBDESK_RAG_HOME", str(prefix / "data"))
    before = fingerprints(bib, pdf)
    code, output = invoke(config, str(bib), "y", "y")
    assert code == 1
    assert "inside a Python or Homebrew installation" in output
    assert not config.exists()
    assert not prefix.exists()
    assert fingerprints(bib, pdf) == before


def test_dangling_explicit_configuration_symlink_is_not_followed_for_creation(sources, tmp_path):
    config, bib, pdf = sources
    config.parent.mkdir()
    target = tmp_path / "missing parent" / "never-created.toml"
    config.symlink_to(target)
    before = fingerprints(bib, pdf)
    code, output = invoke(config, str(bib), "y", "y")
    assert code == 1
    assert config.is_symlink()
    assert not target.exists() and not target.parent.exists()
    assert fingerprints(bib, pdf) == before
    assert "Traceback" not in output


def incomplete_index(config_path, bib_path=None):
    db = connect(load_config(config_path).database)
    try:
        initialize(db)
        if bib_path is not None:
            with db:
                db.execute("INSERT INTO settings VALUES ('bib_path', ?)", (str(bib_path),))
    finally:
        db.close()


@pytest.mark.parametrize("choice", ["2", "3"])
def test_incomplete_index_of_another_library_is_not_repurposed(sources, monkeypatch, choice):
    config = existing(sources, indexed=False)
    incomplete_index(config, sources[1].parent / "another-library.bib")
    database = load_config(config).database
    before = fingerprints(config, database, *sources[1:])

    def forbidden(*args, **kwargs):
        pytest.fail("setup must reject the other library before updating its index")

    monkeypatch.setattr(setup, "index_library", forbidden)
    code, output = invoke(config, "1", choice)
    assert code == 1
    assert "Index belongs to another library" in output
    assert fingerprints(config, database, *sources[1:]) == before


@pytest.mark.parametrize("identity", ["own_library", "no_library"])
def test_explicit_update_resumes_initialized_uncommitted_index(sources, identity):
    config = existing(sources, indexed=False)
    incomplete_index(config, sources[1] if identity == "own_library" else None)
    before = fingerprints(config, *sources[1:])
    code, output = invoke(config, "1", "2")
    assert code == 0, output
    assert index_status(config)["counts"] == {"papers": 1, "attachments": 1, "chunks": 2}
    assert fingerprints(config, *sources[1:]) == before


@pytest.mark.parametrize("event,code", [(OSError("synthetic read failure"), 1),
                                        (KeyboardInterrupt(), 130)])
def test_failure_reading_just_created_configuration_reports_completed_stage(
    sources, monkeypatch, event, code
):
    config, bib, pdf = sources
    before = fingerprints(bib, pdf)

    def fail_after_creation(path):
        assert path.exists()
        raise event

    monkeypatch.setattr(setup, "load_config", fail_after_creation)
    actual, output = invoke(config, str(bib), "y")
    assert actual == code, output
    assert "Completed: Configuration created" in output
    assert config.exists() and load_config(config).bib == bib
    assert not load_config(config).database.exists()
    assert fingerprints(bib, pdf) == before
    assert "Traceback" not in output
