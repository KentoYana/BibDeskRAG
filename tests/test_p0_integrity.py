"""Generated libraries only: binding, snapshots and processing-version upgrades."""

from contextlib import closing
from dataclasses import replace
import hashlib
import json
import sqlite3
import zipfile

import pytest

from bibdesk_rag import cli, indexer
from bibdesk_rag.config import Config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import LibraryIdentityError, connect, initialize
from bibdesk_rag.mcp_server import MCPServer
from bibdesk_rag.search import SQLiteSearch
from test_semantic import FakeBackend


@pytest.fixture
def collection(tmp_path):
    source = tmp_path / "a.bib"
    attachment = tmp_path / "evidence.csv"
    attachment.write_text("gene,value\nRecQ,42\n")
    source.write_text("@article{A,title={RecQ},doi={10.1234/a},Bdsk-File-1={evidence.csv}}")
    config = Config(source, tmp_path / "index.sqlite3")
    indexer.index_library(config)
    other = tmp_path / "b.bib"
    other.write_text("@article{B,title={Other}}")
    path = tmp_path / "b.toml"
    path.write_text(f"bib={json.dumps(str(other))}\ndatabase={json.dumps(str(config.database))}\n")
    return config, attachment, other, path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("arguments", [
    ["--paper", "search", "RecQ"], ["--paper", "show", "A"],
    ["--paper", "attachments", "A"], ["--paper", "context", "RecQ"],
    ["--index", "status"], ["--index", "check"],
    ["--index", "update"], ["--index", "rebuild"],
])
def test_all_cli_paths_refuse_wrong_library_without_modification(collection, capsys, arguments):
    config, attachment, other, path = collection
    config.database.chmod(0o640)
    paths = [config.database, config.bib, attachment, other, path]
    before = {p: digest(p) for p in paths}
    assert cli.main(["--temp", str(path), *arguments]) == 1
    captured = capsys.readouterr()
    assert "library_mismatch" in captured.err and not captured.out
    assert before == {p: digest(p) for p in paths}
    assert config.database.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize("name,args", [
    ("search_papers", {"query": "RecQ"}), ("search_fulltext", {"query": "RecQ"}),
    ("get_paper", {"citekey": "A"}), ("get_attachments", {"citekey": "A"}),
    ("get_chunk", {"chunk_id": 1}), ("build_context", {"query": "RecQ"}),
    ("semantic_search_papers", {"query": "RecQ"}),
])
def test_all_mcp_tools_refuse_wrong_library(collection, monkeypatch, name, args):
    config, _, _, path = collection
    with path.open("a") as stream:
        stream.write("[semantic]\nenabled=true\ndimensions=4\n")
    monkeypatch.setattr("bibdesk_rag.semantic.SentenceTransformerBackend", FakeBackend)
    before = digest(config.database)
    result = MCPServer(path).call_tool(name, args)
    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["error_code"] == "library_mismatch"
    assert digest(config.database) == before


def test_missing_binding_of_populated_index_is_not_adopted(collection):
    config, *_ = collection
    with closing(connect(config.database)) as db, db:
        db.execute("DELETE FROM settings")
    before = digest(config.database)
    for readonly in (True, False):
        with pytest.raises(LibraryIdentityError, match="library_identity_missing"):
            connect(config.database, readonly=readonly, bib=config.bib, allow_unbound=True)
    assert digest(config.database) == before


def test_only_empty_uncommitted_index_can_resume(tmp_path):
    source = tmp_path / "source.bib"
    source.write_text("@article{A,title={Generated}}")
    config = Config(source, tmp_path / "index.sqlite3")
    with closing(connect(config.database)) as db:
        initialize(db)
    with pytest.raises(LibraryIdentityError, match="library_identity_missing"):
        connect(config.database, readonly=True, bib=config.bib)
    assert indexer.index_library(config)["papers_added"] == 1


def test_edit_is_same_library_but_move_needs_fresh_database(collection):
    config, _, other, _ = collection
    config.bib.write_text(config.bib.read_text().replace("RecQ", "Changed"))
    assert indexer.index_library(config)["papers_changed"] == 1
    other.write_bytes(config.bib.read_bytes())
    with pytest.raises(LibraryIdentityError, match="library_mismatch"):
        indexer.index_library(replace(config, bib=other))
    assert indexer.index_library(replace(config, bib=other, database=other.with_suffix(".sqlite3")))


@pytest.mark.parametrize("source_type", ["metadata", "chunk"])
def test_source_truncation_keeps_later_evidence(source_type):
    class Engine:
        def search(self, *args, **kwargs):
            return [
                dict(citekey="A", title="Generated", abstract="a" * 4000,
                     abstract_truncated=True, chunk_id=1 if source_type == "chunk" else None,
                     source_type="csv" if source_type == "chunk" else "metadata"),
                dict(citekey="B", title="Later evidence", chunk_id=None, source_type="metadata"),
            ]

        def get_chunk(self, *args, **kwargs):
            return {"text": "a" * 20000, "truncated": True}

    result = build_context(Engine(), "generated", top=2, max_chars=100000)
    assert result["returned"] == 2 and not result["budget_exhausted"]
    assert result["results"][0]["source_truncated"]
    assert not result["results"][0]["budget_truncated"]
    limited = build_context(Engine(), "generated", top=2, max_chars=1000)
    assert limited["budget_exhausted"] and len(limited["context"]) <= 1000
    assert limited["results"][0]["budget_truncated"]


def test_context_keeps_snapshot_across_actual_concurrent_commit(collection, monkeypatch):
    config, attachment, *_ = collection
    with closing(connect(config.database)) as writer, closing(
        connect(config.database, readonly=True)
    ) as db:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE settings SET value=value WHERE key='last_indexed'")
        writer.commit()
        engine = SQLiteSearch(db)
        original = engine.get_chunk

        def commit_between_selects(*args, **kwargs):
            attachment.write_text("gene,value\nChanged,99\n")
            config.bib.write_text(config.bib.read_text().replace("title={RecQ}", "title={Changed}"))
            indexer.index_library(config)
            return original(*args, **kwargs)

        monkeypatch.setattr(engine, "get_chunk", commit_between_selects)
        result = build_context(engine, "RecQ")
        assert result["results"][0]["title"] == "RecQ"
        assert "RecQ" in result["results"][0]["text"]
        assert "Changed" not in result["results"][0]["text"]
        assert not db.in_transaction
        assert engine.get_paper("A")["title"] == "Changed"


def test_normalization_refreshes_fts_without_parsing_unchanged_attachment(collection, monkeypatch):
    config, attachment, *_ = collection
    before = {p: digest(p) for p in (config.bib, attachment)}
    with closing(connect(config.database, readonly=True)) as db:
        chunk = db.execute("SELECT id,text FROM chunks").fetchone()
    original = indexer.normalize_search
    monkeypatch.setattr(indexer, "NORMALIZATION_REVISION", "generated-v2")
    monkeypatch.setattr(indexer, "normalize_search",
                        lambda text: original(text).replace("recq", "revisiontoken"))
    result = indexer.index_library(config)
    assert result["files_extracted"] == 0 and result["files_reused"] == 1
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        assert engine.search_papers("revisiontoken")[0]["citekey"] == "A"
        assert engine.search_fulltext("revisiontoken")[0]["chunk_id"] == chunk["id"]
        assert tuple(db.execute("SELECT id,text FROM chunks").fetchone()) == tuple(chunk)
    assert before == {p: digest(p) for p in before}
    assert indexer.index_library(config)["papers_changed"] == 0


def test_parser_revision_retries_affected_format_and_containing_zip_only(collection, monkeypatch):
    config, *_ = collection
    archive = config.bib.parent / "supplement.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("table.csv", "gene,value\nRecQ,2\n")
    tex = config.bib.parent / "methods.tex"
    tex.write_text("Generated control")
    config.bib.write_text(config.bib.read_text().replace(
        "Bdsk-File-1={evidence.csv}", "Bdsk-File-1={evidence.csv},"
        "Bdsk-File-2={supplement.zip},Bdsk-File-3={methods.tex}"))
    indexer.index_library(config)
    monkeypatch.setattr(indexer, "EXTRACTION_VERSIONS",
                        {**indexer.EXTRACTION_VERSIONS, ".csv": "generated-v2"})
    report = indexer.index_library(config)
    assert report["files_extracted"] == 2 and report["files_reused"] == 1
    assert indexer.index_library(config)["files_extracted"] == 0


def test_revision_failure_rolls_back_old_searchable_state(collection, monkeypatch):
    config, *_ = collection
    before = digest(config.database)
    monkeypatch.setattr(indexer, "EXTRACTION_VERSIONS",
                        {**indexer.EXTRACTION_VERSIONS, ".csv": "generated-v2"})

    def failure(*args, **kwargs):
        raise RuntimeError("generated extraction failure")

    monkeypatch.setattr(indexer, "extract_file", failure)
    with pytest.raises(RuntimeError, match="generated extraction failure"):
        indexer.index_library(config)
    assert digest(config.database) == before
    with closing(connect(config.database, readonly=True)) as db:
        assert SQLiteSearch(db).search_fulltext("RecQ")


def test_future_schema_refused_without_touching_permissions(collection):
    config, *_ = collection
    with sqlite3.connect(config.database) as db:
        db.execute("PRAGMA user_version=999")
    config.database.chmod(0o640)
    before = digest(config.database)
    with pytest.raises(ValueError, match="Unsupported"):
        indexer.index_library(config)
    assert digest(config.database) == before
    assert config.database.stat().st_mode & 0o777 == 0o640


def test_context_does_not_end_callers_transaction(collection):
    config, *_ = collection
    with closing(connect(config.database)) as db:
        db.execute("BEGIN")
        db.execute("UPDATE papers SET title='Uncommitted' WHERE citekey='A'")
        result = build_context(SQLiteSearch(db), "RecQ")
        assert result["results"][0]["title"] == "Uncommitted"
        assert db.in_transaction
        db.rollback()
        assert SQLiteSearch(db).get_paper("A")["title"] == "RecQ"


def test_rebuild_repairs_paper_search_fields_without_source_edit(collection):
    config, attachment, *_ = collection
    before = {p: digest(p) for p in (config.bib, attachment)}
    with closing(connect(config.database)) as db, db:
        db.execute("UPDATE papers SET search_title='obsolete' WHERE citekey='A'")
    indexer.index_library(config, rebuild=True)
    with closing(connect(config.database, readonly=True)) as db:
        assert SQLiteSearch(db).search_papers("RecQ")
        assert not SQLiteSearch(db).search_papers("obsolete")
    assert before == {p: digest(p) for p in before}
