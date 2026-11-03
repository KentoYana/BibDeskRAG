"""Bundled CLI guidance; reading it never requires configuration or an index."""

from __future__ import annotations

from importlib.resources import files
import os
import shutil
import subprocess
import sys

from . import __version__


def _resource(name: str) -> str:
    return files("bibdesk_rag").joinpath("resources", name).read_text(encoding="utf-8")


def examples_text() -> str:
    return _resource("examples.txt")


def manual_text() -> str:
    return _resource("manual.txt")


def config_template_text() -> str:
    return _resource("config-template.toml")


def brief_help_text() -> str:
    return (
        "usage: bibdesk-rag [OPTIONS]\n\n"
        "  --setup                    Interactive initial setup\n"
        "  -c, --config ACTION [PATH]  Settings: show, path, use, create\n"
        "  -i, --index ACTION         Index: update, rebuild, status, check\n"
        "  -p, --paper ACTION VALUE   Papers: search, show, attachments, context\n"
        "  --temp PATH                Use another configuration for this invocation\n\n"
        "  -h, --help                 Full help\n"
        "  -v, --version              Version and citation\n"
        "  -e, --example              Usage examples\n"
        "  -r, --readme               Full manual\n"
        "  -o, --output RESOURCE      manual, config-template, citation\n"
    )


def citation_text() -> str:
    return (
        "@manual{BibDeskRAG,\n"
        "  author = {Kento Yanagisawa},\n"
        "  title = {BibDesk RAG: Read-only local literature retrieval for BibDesk},\n"
        f"  version = {{{__version__}}},\n"
        "  url = {https://github.com/KentoYana/BibDeskRAG}\n"
        "}\n"
    )


def version_text() -> str:
    return (
        f"bibdesk-rag {__version__}\n"
        "Citation: Kento Yanagisawa. BibDesk RAG: Read-only local literature "
        f"retrieval for BibDesk. Version {__version__}.\n"
        "https://github.com/KentoYana/BibDeskRAG\n"
    )


def show_manual() -> None:
    text = manual_text()
    pager = shutil.which("less") if sys.stdout.isatty() and sys.stdin.isatty() else None
    if pager:
        env = os.environ.copy()
        for name in ("LESS", "LESSOPEN", "LESSCLOSE", "LESSKEY", "LESSKEYIN", "LESSKEY_CONTENT"):
            env.pop(name, None)
        env["LESSSECURE"] = "1"
        try:
            result = subprocess.run(
                [pager, "-F", "-X"], input=text, text=True, env=env, shell=False, check=False,
            )
            if result.returncode == 0:
                return
        except OSError:
            pass
    print(text, end="")
