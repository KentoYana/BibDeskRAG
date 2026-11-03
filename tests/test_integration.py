import base64
from dataclasses import replace
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import zipfile

from openpyxl import Workbook
import pytest
from reportlab.pdfgen import canvas

from bibdesk_rag.config import Config, init_config, load_config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import connect, doctor
from bibdesk_rag.extractors import ExtractionOptions
from bibdesk_rag.indexer import index_library
from bibdesk_rag.search import SQLiteSearch


def locator(path):
    return base64.b64encode(plistlib.dumps({"relativePath": str(path)})).decode()


def entry(key, title, *files, doi="", extra=""):
    body = (
        f"@article{{{key},title={{{title}}},author={{Muller, Alice}},year={{2025}},doi={{{doi}}},\n"
    )
    body += "".join(f"Bdsk-File-{i}={{{locator(f)}}},\n" for i, f in enumerate(files, 1))
    return body + extra + "}\n"


@pytest.fixture
def library(tmp_path):
    pdf = tmp_path / "論文 main.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(40, 700, "Page one: histone hH3-K4R and mus-9 UV damage")
    c.showPage()
    c.drawString(40, 700, "RecQ helicase promotes DNA repair")
    c.save()
    sup = tmp_path / "supplementary methods.pdf"
    c = canvas.Canvas(str(sup))
    c.drawString(40, 700, "Supplementary RecQ experiments")
    c.save()
    csv = tmp_path / "table.csv"
    csv.write_text("gene,value\nΔset-1,10-15\nRecQ,42\n", encoding="utf-8")
    tsv = tmp_path / "table.tsv"
    tsv.write_text("gene\tvalue\nmus-9\t7\n", encoding="utf-8")
    xlsx = tmp_path / "table.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Genes"
    ws.append(["gene", "count"])
    ws.append(["RecQ", 13])
    wb.save(xlsx)
    archive = tmp_path / "supp.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("inner.csv", "gene,value\nzipgene,8\n")
        z.writestr("notes.xyz", "unsupported")
    bib = tmp_path / "refs.bib"
    text = entry(
        "Example2025",
        "Histone hH3-K4R UV damage",
        pdf.name,
        sup.name,
        csv.name,
        tsv.name,
        xlsx.name,
        archive.name,
        "missing.pdf",
        doi="https://doi.org/10.1234/ABC",
        extra="keywords={RecQ, mus-9},abstract={Histone UV damage},\n",
    )
    text += entry("Shared2025", "RecQ helicase", pdf.name, doi="10.1234/abc")
    bib.write_text(text, encoding="utf-8")
    config = Config(bib, tmp_path / "data/index.sqlite3")
    return config


def test_cross_format_provenance_and_readonly(library):
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in library.bib.parent.iterdir()
        if p.is_file()
    }
    report = index_library(library)
    assert report["papers_added"] == 2
    assert len(report["errors"]) >= 1
    db = connect(library.database, readonly=True)
    engine = SQLiteSearch(db)
    assert engine.search_papers("Example2025")[0]["citekey"] == "Example2025"
    assert len(engine.search_papers("https://DOI.org/10.1234/ABC")) == 2
    assert engine.search_papers("", doi="10.1234/abc", year="2025")
    assert engine.search_papers("Muller")
    assert engine.search_papers("2025")
    for query in ("hH3-K4R", "hH3K4R", "mus-9", "mus–9", "Δset-1", "RecQ"):
        assert engine.search_fulltext(query, top=10), query
    hits = engine.search_fulltext("RecQ", top=30, per_paper=10)
    assert {h["source_type"] for h in hits} >= {"pdf", "csv", "xlsx"}
    assert any(h["page_start"] == 2 and h["file_path"].endswith("main.pdf") for h in hits)
    assert any(h["role"] == "supplementary" for h in hits)
    assert any(h["sheet_name"] == "Genes" and h["row_start"] == 2 for h in hits)
    zipped = engine.search_fulltext("zipgene")[0]
    assert zipped["member_path"] == "inner.csv"
    # Same physical PDF referenced by two papers has one attachment/extraction.
    assert (
        db.execute("SELECT count(*) FROM attachments WHERE path LIKE '%main.pdf'").fetchone()[0]
        == 1
    )
    main_id = db.execute("SELECT id FROM attachments WHERE path LIKE '%main.pdf'").fetchone()[0]
    assert (
        db.execute("SELECT count(*) FROM chunks WHERE attachment_id=?", (main_id,)).fetchone()[0]
        == 2
    )
    assert doctor(db)["ok"]
    with pytest.raises(Exception):
        db.execute("DELETE FROM chunks")
    db.close()
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


def test_update_reuses_chunks_rehashes_only_changed_and_removes_stale(library, monkeypatch):
    index_library(library)
    db = connect(library.database, readonly=True)
    ids = [tuple(row) for row in db.execute("SELECT id,text FROM chunks ORDER BY id")]
    db.close()
    import bibdesk_rag.indexer as module

    real_extract = module.extract_file
    calls = []

    def traced(*args):
        calls.append(args[0])
        return real_extract(*args)

    monkeypatch.setattr(module, "extract_file", traced)
    report = index_library(library)
    assert not calls
    assert report["files_hashed"] == 0
    db = connect(library.database, readonly=True)
    assert ids == [tuple(row) for row in db.execute("SELECT id,text FROM chunks ORDER BY id")]
    db.close()
    csv = library.bib.parent / "table.csv"
    os.utime(csv, ns=(csv.stat().st_atime_ns, csv.stat().st_mtime_ns + 1000000000))
    report = index_library(library)
    assert report["files_hashed"] == 1 and not calls
    csv.write_text("gene,value\nnewgene,12\n")
    report = index_library(library)
    assert calls == [csv]
    assert report["files_extracted"] == 1
    library.bib.write_text(entry("Shared2025", "RecQ", "論文 main.pdf", doi="10.1234/abc"))
    index_library(library)
    db = connect(library.database, readonly=True)
    assert db.execute("SELECT count(*) FROM papers").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM attachments").fetchone()[0] == 1
    assert not SQLiteSearch(db).search_fulltext("newgene")
    assert doctor(db)["ok"]
    db.close()


def test_unambiguous_rename_preserves_id_and_chunks(tmp_path):
    csv = tmp_path / "table.csv"
    csv.write_text("gene\nRecQ\n")
    bib = tmp_path / "refs.bib"
    bib.write_text(entry("Old", "Paper", csv.name, doi="10.1234/x"))
    cfg = Config(bib, tmp_path / "index.sqlite3")
    index_library(cfg)
    db = connect(cfg.database, readonly=True)
    paper_id = db.execute("SELECT id FROM papers").fetchone()[0]
    chunk_id = db.execute("SELECT id FROM chunks").fetchone()[0]
    db.close()
    bib.write_text(entry("New", "Paper", csv.name, doi="10.1234/x"))
    report = index_library(cfg)
    assert report["papers_renamed"] == 1
    db = connect(cfg.database, readonly=True)
    assert tuple(db.execute("SELECT id,citekey FROM papers").fetchone()) == (paper_id, "New")
    assert db.execute("SELECT id FROM chunks").fetchone()[0] == chunk_id
    db.close()


def test_context_budgets_and_staged_selection(library):
    index_library(library)
    db = connect(library.database, readonly=True)
    engine = SQLiteSearch(db)
    result = build_context(engine, "RecQ", top=5, max_chars=900, metadata_query="histone")
    assert len(result["context"]) <= 900
    assert result["results"]
    assert {r["citekey"] for r in result["results"]} == {"Example2025"}
    assert result["unverified"]
    assert not build_context(engine, "missingwords")["results"]
    assert not build_context(engine, "RecQ", metadata_query="missingwords")["results"]
    for invalid in (-1, 0, 101):
        with pytest.raises(ValueError):
            engine.search("RecQ", invalid)
    for weird in ('" OR *', "near(", "---", "'; DROP TABLE papers; --"):
        engine.search(weird)
    assert doctor(db)["ok"]
    db.close()


def test_changed_extraction_options_trigger_rebuild(library):
    index_library(library)
    report = index_library(
        replace(library, extraction=ExtractionOptions(chunk_size=300, chunk_overlap=30))
    )
    assert report["files_extracted"] == 6


def test_cli_install_commands_json_and_config(library, tmp_path):
    config_path = tmp_path / "app/config.toml"
    init_config(library.bib, config_path)
    env = {**os.environ, "BIBDESK_RAG_CONFIG": str(config_path)}

    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "bibdesk_rag.cli", *args],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    from bibdesk_rag import __version__

    assert f"bibdesk-rag {__version__}" in run("--version")
    assert "Read-only" in run("--help")
    assert json.loads(run("--index", "rebuild", "--format", "json"))["papers_added"] == 2
    assert json.loads(run("--index", "update", "--format", "json"))["files_extracted"] == 0
    assert json.loads(run("--paper", "search", "RecQ", "--scope", "fulltext", "--format", "json"))[0]["chunk_id"]
    assert json.loads(run("--paper", "show", "Example2025", "--format", "json"))["citekey"] == "Example2025"
    assert "@article{Example2025" in run("--paper", "show", "Example2025", "--format", "bibtex")
    assert json.loads(run("--paper", "attachments", "Example2025", "--format", "json"))
    assert json.loads(run("--paper", "context", "RecQ", "--format", "json"))["returned"]
    assert json.loads(run("--index", "status", "--format", "json"))["counts"]["papers"] == 2
    assert json.loads(run("--index", "check", "--format", "json"))["ok"]
    assert load_config(config_path).bib == library.bib
    with pytest.raises(FileExistsError):
        init_config(library.bib, config_path)


def test_entire_local_pipeline_does_not_open_network(library, monkeypatch):
    import socket

    def denied(*args, **kwargs):
        pytest.fail("Local retrieval attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    index_library(library)
    db = connect(library.database, readonly=True)
    engine = SQLiteSearch(db)
    assert engine.search_fulltext("RecQ")
    assert build_context(engine, "RecQ")["returned"]
    db.close()
