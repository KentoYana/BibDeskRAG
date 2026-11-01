"""Independent regression checks for data safety and transactional updates."""

from dataclasses import replace
import hashlib
from pathlib import Path
import sqlite3

import pytest

from bibdesk_rag.config import Config, init_config, load_config
from bibdesk_rag.database import connect, doctor
from bibdesk_rag.indexer import index_library
from bibdesk_rag.search import SQLiteSearch


def library(tmp_path: Path, title: str = "RecQ") -> tuple[Config, Path]:
    attachment = tmp_path / "supplement.csv"
    attachment.write_text("gene,measurement\nRecQ,10-15\nmus-9,0.002\n")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        f"@article{{A,title={{{title}}},doi={{10.1234/a}},Bdsk-File-1={{{attachment.name}}}}}"
    )
    return Config(bib, tmp_path / "state" / "index.sqlite3"), attachment


def test_index_is_read_only_and_read_queries_cannot_write(tmp_path):
    config, attachment = library(tmp_path)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in [config.bib, attachment]}
    index_library(config)
    with connect(config.database, readonly=True) as db:
        search = SQLiteSearch(db)
        hits = search.search_fulltext("RecQ")
        assert hits[0]["citekey"] == "A"
        assert search.get_chunk(hits[0]["chunk_id"])["row_start"] == 2
        assert doctor(db)["ok"]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM papers")
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


def test_source_overlap_including_sidecar_and_hardlink_is_rejected(tmp_path):
    config, attachment = library(tmp_path)
    with pytest.raises(ValueError, match="overlap|overwrite"):
        index_library(replace(config, database=attachment))
    with pytest.raises(ValueError, match="overlap|overwrite"):
        init_config(config.bib, path=attachment)
    sidecar_target = tmp_path / "indexed"
    Path(str(sidecar_target) + "-journal").symlink_to(attachment)
    with pytest.raises(ValueError, match="overlap|overwrite"):
        index_library(replace(config, database=sidecar_target))
    hardlink = tmp_path / "hardlink.sqlite3"
    hardlink.hardlink_to(attachment)
    with pytest.raises(ValueError, match="overlap|overwrite"):
        index_library(replace(config, database=hardlink))


def test_update_rollback_retains_prior_metadata_and_chunks(tmp_path, monkeypatch):
    config, attachment = library(tmp_path)
    index_library(config)
    with connect(config.database, readonly=True) as db:
        before_id = SQLiteSearch(db).search_fulltext("RecQ")[0]["chunk_id"]
    config.bib.write_text(config.bib.read_text().replace("title={RecQ}", "title={Changed title}"))
    attachment.write_text("gene,measurement\nChanged,3\n")

    def crash(*args, **kwargs):
        raise RuntimeError("simulated interrupted extraction")

    monkeypatch.setattr("bibdesk_rag.indexer.extract_file", crash)
    with pytest.raises(RuntimeError, match="interrupted"):
        index_library(config)
    with connect(config.database, readonly=True) as db:
        search = SQLiteSearch(db)
        assert search.get_paper("A")["title"] == "RecQ"
        assert search.search_fulltext("RecQ")[0]["chunk_id"] == before_id
        assert not search.search_fulltext("Changed")
        assert doctor(db)["ok"]


def test_rename_ambiguous_doi_not_merged_and_delete_fts_clean(tmp_path):
    config, attachment = library(tmp_path)
    original = config.bib.read_text()
    config.bib.write_text(original + "\n" + original.replace("@article{A,", "@article{B,"))
    index_library(config)
    with connect(config.database, readonly=True) as db:
        old_ids = {row[0] for row in db.execute("SELECT id FROM papers")}
        assert db.execute("SELECT count(*) FROM attachments").fetchone()[0] == 1
        chunks_count = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    config.bib.write_text(original.replace("@article{A,", "@article{New,"))
    report = index_library(config)
    assert report["papers_renamed"] == 0
    with connect(config.database, readonly=True) as db:
        assert SQLiteSearch(db).get_paper("New")["id"] not in old_ids
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == chunks_count
    config.bib.write_text("% intentionally empty synthetic library\n")
    index_library(config)
    with connect(config.database, readonly=True) as db:
        assert not SQLiteSearch(db).search_papers("RecQ")
        assert not SQLiteSearch(db).search_fulltext("RecQ")
        assert doctor(db)["ok"]
        assert db.execute("SELECT count(*) FROM attachments").fetchone()[0] == 0


def test_attachment_removed_from_disk_has_no_stale_search_results(tmp_path):
    config, attachment = library(tmp_path)
    index_library(config)
    attachment.unlink()
    report = index_library(config)
    assert report["errors"]
    with connect(config.database, readonly=True) as db:
        assert not SQLiteSearch(db).search_fulltext("RecQ")
        assert SQLiteSearch(db).get_attachments("A")[0]["extraction_status"] == "error"
        assert doctor(db)["ok"]


def test_search_snippet_preserves_literal_scientific_values(tmp_path):
    config, attachment = library(tmp_path)
    attachment.write_text("gene,measurement\nΔset-1,10-15\nhH3-K4R,−0.25\n")
    index_library(config)
    with connect(config.database, readonly=True) as db:
        for query in ("Δset-1", "hH3K4R"):
            hit = SQLiteSearch(db).search_fulltext(query)[0]
            assert "Δset-1" in hit["snippet"]
            assert "10-15" in hit["snippet"]
            assert "−0.25" in hit["snippet"]
            assert hit["snippet_truncated"] is False


def test_snippet_locates_late_normalized_identifier():
    from bibdesk_rag.search import _verbatim_snippet

    text = "background " * 100 + "Δset-1 measured 10-15 colonies" + " tail" * 100
    snippet, truncated = _verbatim_snippet(text, "Δset1")
    assert "Δset-1 measured 10-15 colonies" in snippet
    assert snippet in text
    assert len(snippet) == 600 and truncated


def test_unchanged_no_text_file_is_not_rehashed(tmp_path, monkeypatch):
    config, attachment = library(tmp_path)
    attachment.write_text("")
    index_library(config)
    import bibdesk_rag.indexer as indexer

    original = indexer.digest

    def ensure_bib_only(path):
        assert path == config.bib, "unchanged empty attachment must not be read again"
        return original(path)

    monkeypatch.setattr(indexer, "digest", ensure_bib_only)
    report = index_library(config)
    assert report["files_hashed"] == 0 and report["files_extracted"] == 0


def test_bm25_ranking_and_per_paper_cap_do_not_hide_other_papers(tmp_path):
    from bibdesk_rag.extractors import ExtractionOptions

    many = tmp_path / "many.csv"
    few = tmp_path / "few.csv"
    many.write_text("gene,value\n" + "RecQ,42\n" * 100)
    few.write_text("gene,value\nRecQ,1\n")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{TitleMatch,title={RecQ},Bdsk-File-1={many.csv}}\n"
        "@article{AbstractMatch,title={Other},abstract={RecQ},Bdsk-File-1={few.csv}}\n"
    )
    config = Config(
        bib, tmp_path / "index.sqlite3", ExtractionOptions(chunk_size=80, chunk_overlap=0)
    )
    index_library(config)
    with connect(config.database, readonly=True) as db:
        search = SQLiteSearch(db)
        metadata = search.search_papers("RecQ")
        assert [hit["citekey"] for hit in metadata] == ["TitleMatch", "AbstractMatch"]
        hits = search.search_fulltext("RecQ", top=10, per_paper=2)
        assert len([hit for hit in hits if hit["citekey"] == "TitleMatch"]) == 2
        assert len([hit for hit in hits if hit["citekey"] == "AbstractMatch"]) == 1
        assert [hit["score"] for hit in hits] == sorted(hit["score"] for hit in hits)
        assert all(hit["row_start"] >= 2 for hit in hits)


def test_existing_unrelated_database_is_never_adopted_or_chmodded(tmp_path):
    config, _ = library(tmp_path)
    unrelated = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(unrelated) as db:
        db.execute("CREATE TABLE personal (value TEXT)")
        db.execute("INSERT INTO personal VALUES ('do not change')")
    unrelated.chmod(0o640)
    before = unrelated.read_bytes(), unrelated.stat().st_mode
    with pytest.raises(ValueError, match="application identifier"):
        index_library(replace(config, database=unrelated))
    assert (unrelated.read_bytes(), unrelated.stat().st_mode) == before
    with pytest.raises(ValueError, match="application identifier"):
        connect(unrelated, readonly=True)


def test_schema_initialization_failure_rolls_back(tmp_path, monkeypatch):
    config, _ = library(tmp_path)
    index_library(config)
    import bibdesk_rag.database as database

    monkeypatch.setattr(
        database,
        "SCHEMA",
        database.SCHEMA + "\nCREATE TABLE accidental (value TEXT);\nINVALID SQL;",
    )
    with pytest.raises(sqlite3.Error):
        index_library(config)
    with connect(config.database, readonly=True) as db:
        assert SQLiteSearch(db).get_paper("A")["title"] == "RecQ"
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='accidental'").fetchone()
        assert db.execute("PRAGMA application_id").fetchone()[0] == database.APPLICATION_ID


@pytest.mark.parametrize(
    "content, message",
    [
        ('bib = true\ndatabase = "db.sqlite3"', "path string"),
        ('bib = "refs.bib"\ndatabase = 123', "path string"),
        ('bib = "refs.bib"\ndatabase = "db.sqlite3"\nextraction = false', "TOML table"),
        (
            'bib = "refs.bib"\ndatabase = "db.sqlite3"\n[extraction]\nchunk_size = true',
            "must be an integer",
        ),
        (
            'bib = "refs.bib"\ndatabase = "db.sqlite3"\n[extraction]\nchunk_size = 1500.5',
            "must be an integer",
        ),
        ('bib = "refs.bib"\ndatabase = "db.sqlite3"\n[extraction]\ntypo = 1', "Unknown extraction"),
        ('bib = "refs.bib"\ndatabase = "db.sqlite3"\ntypo = 1', "Unknown configuration"),
    ],
)
def test_config_type_and_shape_errors_are_clear_value_errors(tmp_path, content, message):
    path = tmp_path / "config.toml"
    path.write_text(content)
    with pytest.raises(ValueError, match=message):
        load_config(path)


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_config_cannot_overlap_sqlite_output_or_sidecars(tmp_path, suffix):
    config, _ = library(tmp_path)
    target = tmp_path / "state" / ("index.sqlite3" + suffix)
    with pytest.raises(ValueError, match="Configuration path overlaps"):
        init_config(config.bib, target, tmp_path / "state")
    assert not target.exists()


def test_metadata_summaries_are_bounded_and_context_marks_omissions(tmp_path):
    from bibdesk_rag.context import build_context

    abstract = "RecQ " + "recorded evidence " * 1000
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{A,title={RecQ},doi={10.1234/a},abstract={" + abstract + "}}")
    config = Config(bib, tmp_path / "index.sqlite3")
    index_library(config)
    with connect(config.database, readonly=True) as db:
        search = SQLiteSearch(db)
        hit = search.search_papers("RecQ")[0]
        assert len(hit["abstract"]) == 4000
        assert hit["abstract_truncated"] and "abstract" in hit["truncated_fields"]
        assert hit["doi"] == "10.1234/a" and hit["citekey"] == "A"
        assert len(search.get_paper("A")["abstract"]) > 4000
        result = build_context(search, "RecQ", top=1, max_chars=10000)
        assert result["results"][0]["truncated"]
        assert "abstract" in result["results"][0]["metadata_truncated_fields"]
        assert len(result["context"]) <= 10000


def test_failed_locator_never_reads_existing_diagnostic_path(tmp_path, monkeypatch):
    from bibdesk_rag.attachments import AttachmentReference
    from bibdesk_rag.bibdesk import PaperRecord
    from bibdesk_rag.config import Config
    from bibdesk_rag.database import connect
    import bibdesk_rag.indexer as indexer

    bib = tmp_path / "refs.bib"
    bib.write_text("% synthetic\n")
    diagnostic = tmp_path / ".unresolved-Key-1"
    diagnostic.write_text("UNRELATED PRIVATE TEXT")
    paper = PaperRecord(
        citekey="Key",
        files=[
            AttachmentReference(str(diagnostic), "invalid locator", "attachment resolution failed")
        ],
    )
    monkeypatch.setattr(indexer, "read_library", lambda _: [paper])
    real_digest = indexer.digest

    def guarded_digest(path):
        assert path != diagnostic, "Failed locator must not be opened"
        return real_digest(path)

    monkeypatch.setattr(indexer, "digest", guarded_digest)
    config = Config(bib, tmp_path / "index.sqlite3")
    report = indexer.index_library(config)
    assert report["files_extracted"] == report["files_hashed"] == 0
    assert report["errors"][0]["error"] == "attachment resolution failed"
    db = connect(config.database, readonly=True)
    assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
    db.close()
