"""Bundled guidance works offline and the pager cannot execute user hooks."""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from bibdesk_rag import __version__
from bibdesk_rag import cli_resources as guidance


class Terminal(StringIO):
    def isatty(self):
        return True


def test_packaged_resources_and_citation_are_self_contained():
    template = Path(__file__).parents[1] / "config.example.toml"
    assert guidance.config_template_text() == template.read_text()
    assert "--config create" in guidance.examples_text()
    assert "--index update" in guidance.manual_text()
    assert f"bibdesk-rag {__version__}" in guidance.version_text()
    assert "Kento Yanagisawa" in guidance.version_text()
    citation = guidance.citation_text()
    assert citation.startswith("@manual{BibDeskRAG,")
    assert f"version = {{{__version__}}}" in citation
    assert "author = {Kento Yanagisawa}" in citation
    assert "https://github.com/KentoYana/BibDeskRAG" in citation
    assert "doi =" not in citation


def test_nonterminal_manual_is_stdout_only(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(guidance.sys, "stdout", output)
    monkeypatch.setattr(guidance.sys, "stdin", StringIO())

    def forbidden(*args, **kwargs):
        pytest.fail("Nonterminal guidance must not start or discover a pager")

    monkeypatch.setattr(guidance.shutil, "which", forbidden)
    monkeypatch.setattr(guidance.subprocess, "run", forbidden)
    guidance.show_manual()
    assert output.getvalue() == guidance.manual_text()


def test_terminal_pager_uses_fixed_argv_and_disables_command_hooks(monkeypatch):
    output = Terminal()
    monkeypatch.setattr(guidance.sys, "stdout", output)
    monkeypatch.setattr(guidance.sys, "stdin", Terminal())
    monkeypatch.setenv("PAGER", "untrusted-pager --execute-something")
    monkeypatch.setenv("LESSOPEN", "|untrusted-filter %s")
    monkeypatch.setenv("LESSCLOSE", "untrusted-cleanup %s")
    monkeypatch.setenv("LESS", "--use-backslash")
    monkeypatch.setenv("LESSKEY", "/untrusted/keys")
    calls = []

    def which(name):
        assert name == "less"
        return "/synthetic/bin/less"

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guidance.shutil, "which", which)
    monkeypatch.setattr(guidance.subprocess, "run", run)
    guidance.show_manual()
    assert output.getvalue() == ""
    argv, options = calls[0]
    assert argv == ["/synthetic/bin/less", "-F", "-X"]
    assert options["shell"] is False
    assert options["input"] == guidance.manual_text()
    assert options["env"]["LESSSECURE"] == "1"
    assert not set(("LESS", "LESSOPEN", "LESSCLOSE", "LESSKEY")) & options["env"].keys()


@pytest.mark.parametrize("failure", ["missing", "oserror", "nonzero"])
def test_unavailable_or_failed_pager_falls_back_to_stdout(monkeypatch, failure):
    output = Terminal()
    monkeypatch.setattr(guidance.sys, "stdout", output)
    monkeypatch.setattr(guidance.sys, "stdin", Terminal())
    monkeypatch.setattr(guidance.shutil, "which", lambda _: None if failure == "missing" else "less")

    def run(*args, **kwargs):
        if failure == "oserror":
            raise OSError("synthetic unavailable pager")
        assert failure == "nonzero"
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(guidance.subprocess, "run", run)
    guidance.show_manual()
    assert output.getvalue() == guidance.manual_text()
