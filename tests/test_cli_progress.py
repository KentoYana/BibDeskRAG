from __future__ import annotations

import hashlib
from io import StringIO
import json
import logging
from pathlib import Path
import runpy
import sys
import warnings

import pytest

from bibdesk_rag import cli
from bibdesk_rag.config import init_config
from bibdesk_rag.indexer import IndexProgress


class TerminalStream(StringIO):
    def __init__(self, *, tty: bool):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


@pytest.fixture
def progress_library(tmp_path):
    make_pdf = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/package_smoke.py")
    )["synthetic_pdf"]
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(make_pdf())
    bib = tmp_path / "references.bib"
    bib.write_text(
        "@article{Example2026,title={RecQ synthetic reference},"
        "author={Example, Researcher},year={2026},Bdsk-File-1={paper.pdf}}\n"
    )
    config = tmp_path / "settings/config.toml"
    init_config(bib, config, tmp_path / "derived")
    return config, bib, pdf


def invoke(monkeypatch, config, *args, stdout_tty=True, stderr_tty=True, term="xterm"):
    stdout = TerminalStream(tty=stdout_tty)
    stderr = TerminalStream(tty=stderr_tty)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stdout)
        patch.setattr(sys, "stderr", stderr)
        patch.setenv("TERM", term)
        code = cli.main(["--temp", str(config), "--index", *args])
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize("command", ["rebuild", "update"])
def test_terminal_index_and_update_show_progress_and_compact_summary(
    progress_library, monkeypatch, command
):
    config, bib, pdf = progress_library
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (bib, pdf)}
    code, stdout, stderr = invoke(monkeypatch, config, command)
    assert code == 0
    assert stdout.startswith(f"{command.capitalize()} complete:")
    assert "Attachment issues: 0" in stdout
    assert "\r" in stderr
    assert stderr.endswith("\n")
    assert len(stdout.splitlines()) <= 5
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


@pytest.mark.parametrize(
    "arguments,stdout_tty",
    [(("--format", "json"), False), (("--format", "json"), True),
     (("--format", "json", "--verbose"), True)],
)
def test_explicit_json_output_remains_machine_readable(
    progress_library, monkeypatch, arguments, stdout_tty
):
    config, _, _ = progress_library
    code, stdout, stderr = invoke(
        monkeypatch, config, "rebuild", *arguments, stdout_tty=stdout_tty
    )
    assert code == 0
    report = json.loads(stdout)
    assert report["papers_added"] == 1
    assert report["files_extracted"] == 1
    assert report["errors"] == []
    assert "\r" not in stderr


def test_redirected_default_output_stays_text_without_progress(progress_library, monkeypatch):
    config, _, _ = progress_library
    code, stdout, stderr = invoke(monkeypatch, config, "update", stdout_tty=False)
    assert code == 0
    assert stdout.startswith("Update complete:")
    assert "Attachment issues: 0" in stdout
    assert "\r" not in stderr


@pytest.mark.parametrize(
    "arguments,stderr_tty,term",
    [(("--no-progress",), True, "xterm"), ((), False, "xterm"), ((), True, "dumb")],
)
def test_progress_can_be_disabled_without_losing_human_summary(
    progress_library, monkeypatch, arguments, stderr_tty, term
):
    config, _, _ = progress_library
    code, stdout, stderr = invoke(
        monkeypatch, config, "rebuild", *arguments, stderr_tty=stderr_tty, term=term
    )
    assert code == 0
    assert stdout.startswith("Rebuild complete:")
    assert "\r" not in stderr


def corrupt_startxref(pdf):
    original = pdf.read_bytes()
    start = original.rfind(b"startxref\n") + len(b"startxref\n")
    end = original.find(b"\n", start)
    offset = str(int(original[start:end]) + 1).encode()
    pdf.write_bytes(original[:start] + offset + original[end:])


def test_real_pdf_recovery_warnings_are_summarized_and_json_stays_clean(
    progress_library, monkeypatch
):
    config, _, pdf = progress_library
    corrupt_startxref(pdf)
    before = hashlib.sha256(pdf.read_bytes()).hexdigest()
    code, stdout, stderr = invoke(monkeypatch, config, "rebuild", "--format", "json")
    assert code == 0
    report = json.loads(stdout)
    assert report["files_extracted"] == 1
    assert report["errors"] == []  # Recovery warnings are not extraction failures.
    assert "Parser diagnostics: 2" in stderr
    assert "incorrect startxref pointer" in stderr
    assert "\r" not in stderr
    assert len(stderr) < 2000
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == before


def test_verbose_keeps_dependency_warnings_and_disables_bar(
    progress_library, monkeypatch, caplog
):
    config, _, pdf = progress_library
    corrupt_startxref(pdf)
    with caplog.at_level(logging.WARNING, logger="pypdf"):
        code, stdout, stderr = invoke(monkeypatch, config, "rebuild", "--verbose")
    assert code == 0
    assert stdout.startswith("Rebuild complete:")
    assert "incorrect startxref pointer" in caplog.text
    assert "Parser diagnostics:" not in stderr
    assert "\r" not in stderr


def test_many_diagnostics_are_bounded_and_logging_warning_state_is_restored(
    progress_library, monkeypatch
):
    config, _, _ = progress_library
    original_index = cli.index_library
    logger = logging.getLogger("pypdf")
    previous = (logger.level, logger.propagate, logger.disabled, logger.handlers[:])
    warning_state = (warnings.showwarning, warnings.filters[:])

    def noisy_index(*args, **kwargs):
        for n in range(1000):
            logging.getLogger("pypdf.synthetic").warning("Synthetic diagnostic %s", n)
        warnings.warn("Synthetic Python warning", UserWarning)
        return original_index(*args, **kwargs)

    monkeypatch.setattr(cli, "index_library", noisy_index)
    code, stdout, stderr = invoke(monkeypatch, config, "rebuild", "--no-progress")
    assert code == 0
    assert stdout.startswith("Rebuild complete:")
    assert "Parser diagnostics: 1001" in stderr
    assert "--verbose" in stderr
    assert len(stderr) < 2000
    assert (logger.level, logger.propagate, logger.disabled, logger.handlers) == previous
    assert (warnings.showwarning, warnings.filters) == warning_state


def test_attachment_issue_previews_are_bounded_but_json_keeps_all_details(
    progress_library, monkeypatch
):
    config, _, _ = progress_library
    original_index = cli.index_library
    issues = [
        {"path": f"file-{n}\n\x1b[31m.pdf", "error": "partial extraction " + "x" * 2000}
        for n in range(100)
    ]

    def index_with_issues(*args, **kwargs):
        result = original_index(*args, **kwargs)
        result["errors"] = issues
        return result

    monkeypatch.setattr(cli, "index_library", index_with_issues)
    code, stdout, stderr = invoke(monkeypatch, config, "rebuild", "--no-progress")
    assert code == 0
    assert "Attachment issues: 100" in stdout
    assert len(stderr) < 2500
    assert "\x1b[31m" not in stderr
    code, stdout, stderr = invoke(monkeypatch, config, "rebuild", "--format", "json")
    assert code == 0
    assert json.loads(stdout)["errors"] == issues
    assert "\r" not in stderr
    code, _, stderr = invoke(monkeypatch, config, "rebuild", "--verbose")
    assert code == 0
    assert "file-99" in stderr
    assert "\r" not in stderr


@pytest.mark.parametrize("exception,expected_code", [(RuntimeError("failed"), 1), (KeyboardInterrupt(), 130)])
def test_failure_or_interrupt_finishes_progress_line_without_false_completion(
    progress_library, monkeypatch, exception, expected_code
):
    config, _, _ = progress_library
    logger = logging.getLogger("pypdf")
    previous = (logger.level, logger.propagate, logger.disabled, logger.handlers[:])
    warning_state = (warnings.showwarning, warnings.filters[:])

    def fail(*args, **kwargs):
        if callback := kwargs.get("progress"):
            callback(IndexProgress("indexing", papers_total=1, files_total=1))
        raise exception

    monkeypatch.setattr(cli, "index_library", fail)
    code, stdout, stderr = invoke(monkeypatch, config, "rebuild")
    assert code == expected_code
    assert "complete" not in stdout.lower()
    assert "\r" in stderr
    assert stderr.endswith("\n")
    assert (logger.level, logger.propagate, logger.disabled, logger.handlers) == previous
    assert (warnings.showwarning, warnings.filters) == warning_state
