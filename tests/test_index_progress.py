import hashlib

import pytest

from bibdesk_rag.config import Config
from bibdesk_rag.database import connect
from bibdesk_rag.indexer import IndexProgress, index_library


def entry(key, *files):
    fields = "".join(
        f",Bdsk-File-{number}={{{filename}}}" for number, filename in enumerate(files, 1)
    )
    return f"@article{{{key},title={{Synthetic reference {key}}}{fields}}}\n"


@pytest.fixture
def library(tmp_path):
    csv = tmp_path / "shared.csv"
    csv.write_text("gene,value\nRecQ,1\n")
    unsupported = tmp_path / "unsupported.xyz"
    unsupported.write_text("Synthetic unsupported attachment")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        entry("First", csv.name, "missing.pdf", unsupported.name)
        + entry("Second", csv.name)
        + entry("MetadataOnly")
    )
    return Config(bib, tmp_path / "data/index.sqlite3"), (bib, csv, unsupported)


def hashes(paths):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def snapshot(database):
    db = connect(database, readonly=True)
    try:
        return {
            table: [tuple(row) for row in db.execute(f"SELECT * FROM {table}")]
            for table in ("papers", "attachments", "paper_attachments", "chunks", "settings")
        }
    finally:
        db.close()


def test_progress_counts_unique_processed_files_and_incremental_reuse(library):
    config, originals = library
    before = hashes(originals)

    for rebuild in (True, False):
        events = []
        committed_counts = []

        def receive(event):
            events.append(event)
            if event.phase == "done":
                # A separate reader must see committed data at completion.
                db = connect(config.database, readonly=True)
                try:
                    committed_counts.append(db.execute("SELECT count(*) FROM papers").fetchone()[0])
                finally:
                    db.close()

        report = index_library(config, rebuild=rebuild, progress=receive)
        assert events[0] == IndexProgress("reading")
        assert events[1] == IndexProgress("indexing", 0, 3, 0, 3)
        assert events[-2].phase == "committing"
        assert events[-1] == IndexProgress("done", 3, 3, 3, 3)
        assert [e.papers_done for e in events] == sorted(e.papers_done for e in events)
        assert [e.files_done for e in events] == sorted(e.files_done for e in events)
        assert all(0 <= e.files_done <= e.files_total for e in events)
        assert all(0 <= e.papers_done <= e.papers_total for e in events)
        assert committed_counts == [3]
        assert report["files_extracted"] == (2 if rebuild else 0)
        assert report["files_reused"] == (0 if rebuild else 2)
        assert hashes(originals) == before


@pytest.mark.parametrize("paper_count", [0, 2])
def test_progress_handles_libraries_without_attachments(tmp_path, paper_count):
    bib = tmp_path / "refs.bib"
    bib.write_text("".join(entry(f"Paper{i}") for i in range(paper_count)))
    config = Config(bib, tmp_path / "data/index.sqlite3")
    events = []

    index_library(config, progress=events.append)

    assert events[-1] == IndexProgress("done", paper_count, paper_count, 0, 0)
    assert all(e.files_done == e.files_total == 0 for e in events)


def test_failed_final_validation_rolls_back_without_completion(library, monkeypatch):
    import bibdesk_rag.indexer as module

    config, originals = library
    index_library(config)
    before_database = snapshot(config.database)
    config.bib.write_text(config.bib.read_text().replace("Synthetic reference First", "Changed title"))
    before_sources = hashes(originals)
    real_digest = module.digest
    bib_digest_calls = 0

    def changed_at_commit(path):
        nonlocal bib_digest_calls
        if path == config.bib:
            bib_digest_calls += 1
            if bib_digest_calls == 3:
                return "simulated change detected before commit"
        return real_digest(path)

    monkeypatch.setattr(module, "digest", changed_at_commit)
    events = []
    with pytest.raises(RuntimeError, match="transaction rolled back"):
        index_library(config, progress=events.append)

    assert events[-1].phase == "committing"
    assert not any(e.phase == "done" for e in events)
    assert snapshot(config.database) == before_database
    assert hashes(originals) == before_sources


def test_parsing_failure_has_no_completion_event(tmp_path):
    config = Config(tmp_path / "missing.bib", tmp_path / "data/index.sqlite3")
    events = []
    with pytest.raises(FileNotFoundError):
        index_library(config, progress=events.append)
    assert events == [IndexProgress("reading")]
    assert not config.database.exists()
