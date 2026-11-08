from __future__ import annotations

import hashlib
from io import StringIO
import json
import logging
import os
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import warnings

import pytest

from bibdesk_rag import cli
from bibdesk_rag.config import init_config
from bibdesk_rag.embeddings import SentenceTransformerBackend
from bibdesk_rag.indexer import IndexProgress
from bibdesk_rag.progress import IndexProgressBar, model_loading_progress
from bibdesk_rag.semantic_config import SemanticOptions


@pytest.fixture
def model_loader(monkeypatch):
    """Exercise real tqdm formatting with generated weights, without a model or network."""
    tqdm = pytest.importorskip("tqdm").tqdm
    state = SimpleNamespace(hook=None)

    def set_hook(hook):
        previous, state.hook = state.hook, hook
        return previous

    def loading_bar(*args, **kwargs):
        factory = state.tqdm_lib.tqdm
        return state.hook(factory, args, kwargs) if state.hook else factory(*args, **kwargs)

    state.set_tqdm_hook = set_hook
    state.tqdm_lib = SimpleNamespace(tqdm=tqdm)
    state.tqdm = loading_bar
    transformers = ModuleType("transformers")
    utils = ModuleType("transformers.utils")
    utils.logging = state
    transformers.utils = utils
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "transformers.utils", utils)

    class GeneratedModel:
        max_seq_length = 512

        def __init__(self, snapshot, **kwargs):
            assert snapshot == "generated-snapshot"
            assert kwargs == dict(device="cpu", local_files_only=True, trust_remote_code=False,
                                  model_kwargs={"use_safetensors": True})
            for _ in loading_bar(range(199), desc="Loading weights"):
                pass

        def get_embedding_dimension(self):
            return 384

    def local_snapshot(*args, **kwargs):
        assert kwargs["local_files_only"] is True
        return "generated-snapshot"

    sentence_transformers = ModuleType("sentence_transformers")
    sentence_transformers.SentenceTransformer = GeneratedModel
    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = local_snapshot
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setattr("bibdesk_rag.embeddings.version", lambda name: "generated-fixture")
    # Do not leave the backend's offline flags behind in the test process.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        monkeypatch.setenv(name, "1")
    return state


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


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("files,papers", [(2, 3), (1560, 1718)])
def test_model_and_index_bars_have_matching_columns_and_separate_completed_lines(
    model_loader, legacy, files, papers, monkeypatch
):
    monkeypatch.setattr("bibdesk_rag.progress.shutil.get_terminal_size",
                        lambda **kwargs: os.terminal_size((80, 24)))
    original_class = model_loader.tqdm_lib.tqdm
    if legacy:
        del model_loader.set_tqdm_hook
    stream = TerminalStream(tty=True)
    with IndexProgressBar(enabled=True, stream=stream) as progress:
        progress.update(IndexProgress("reading"))
        SentenceTransformerBackend(SemanticOptions())
        progress.update(IndexProgress("indexing", 0, papers, 0, files))
        progress.update(IndexProgress("done", papers, papers, files, files))

    # Interpret carriage returns as a terminal does, keeping the final version of each row.
    rows = [row.split("\r")[-1].rstrip() for row in stream.getvalue().split("\n") if row]
    assert len(rows) == 3
    assert rows[0] == "Reading bibliography..."
    assert rows[1] == "Loading weights [####################] 100% | 199/199"
    assert rows[2] == ("Indexed         [####################] 100% | "
                       f"files {files}/{files}, papers {papers}/{papers}")
    assert rows[1].index("[") == rows[2].index("[")
    assert "\x1b" not in stream.getvalue()  # No cursor-up sequences or leftover extra rows.
    assert model_loader.hook is None
    assert model_loader.tqdm_lib.tqdm is original_class


@pytest.mark.parametrize(
    "arguments,stdout_tty,stderr_tty,term,visible",
    [((), True, True, "xterm", True),
     (("--no-progress",), True, True, "xterm", False),
     (("--format", "json"), True, True, "xterm", False),
     (("--verbose",), True, True, "xterm", False),
     ((), False, True, "xterm", False),
     ((), True, False, "xterm", False),
     ((), True, True, "dumb", False)],
)
def test_cli_model_bar_obeys_the_same_output_policy_as_index_bar(
    progress_library, monkeypatch, model_loader,
    arguments, stdout_tty, stderr_tty, term, visible,
):
    config, bib, pdf = progress_library
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (bib, pdf)}
    original_index = cli.index_library

    def load_then_index(*args, **kwargs):
        if callback := kwargs.get("progress"):
            callback(IndexProgress("reading"))
        SentenceTransformerBackend(SemanticOptions())
        return original_index(*args, **kwargs)

    monkeypatch.setattr(cli, "index_library", load_then_index)
    code, stdout, stderr = invoke(
        monkeypatch, config, "update", *arguments,
        stdout_tty=stdout_tty, stderr_tty=stderr_tty, term=term,
    )
    assert code == 0
    assert ("Loading weights" in stderr) is visible
    assert ("\r" in stderr) is visible
    assert "Loading weights" not in stdout
    if "json" in arguments:
        assert json.loads(stdout)["papers_added"] == 1
    assert model_loader.hook is None
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("exception", [RuntimeError("load failed"), KeyboardInterrupt()])
def test_model_progress_restores_dependency_state_on_failure(model_loader, legacy, exception):
    original_class = model_loader.tqdm_lib.tqdm

    def previous_hook(factory, args, kwargs):
        return factory(*args, **kwargs)

    model_loader.hook = previous_hook
    if legacy:
        del model_loader.set_tqdm_hook
        model_loader.hook = None
    stream = TerminalStream(tty=True)
    with pytest.raises(type(exception)), IndexProgressBar(enabled=True, stream=stream):
        with model_loading_progress():
            with model_loader.tqdm(total=199, desc="Loading weights") as bar:
                bar.update(1)
                raise exception
    assert "100%" not in stream.getvalue()
    assert stream.getvalue().endswith("\n")
    assert model_loader.hook is (None if legacy else previous_hook)
    assert model_loader.tqdm_lib.tqdm is original_class
    # Outside an indexing scope the optional loader context changes no state.
    with model_loading_progress():
        assert model_loader.hook is (None if legacy else previous_hook)
