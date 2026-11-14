"""Exercise real optional pypdf code paths with generated PDFs only."""
from contextlib import closing
import hashlib
import io
import zipfile

import pytest
from pypdf import PdfReader, PdfWriter

from bibdesk_rag import indexer
from bibdesk_rag.config import Config
from bibdesk_rag.database import connect
from bibdesk_rag.extractors import ExtractionResult, extract_file
from bibdesk_rag.search import SQLiteSearch
from tools.pdf_fixtures import aes_pdf, cff_pdf


def test_cff_embedded_encoding_requires_fonttools_and_preserves_source(tmp_path, caplog, monkeypatch):
    source = tmp_path / "generated-cff.pdf"
    source.write_bytes(cff_pdf())
    before = source.read_bytes()
    result = extract_file(source)
    assert result.status == "ok" and result.chunks[0].text == "CFF"
    assert result.chunks[0].page_start == result.chunks[0].page_end == 1
    assert "fontTools is required" not in caplog.text
    assert source.read_bytes() == before
    monkeypatch.setattr("pypdf.generic._font.HAS_FONTTOOLS", False)
    unavailable = extract_file(source)
    assert unavailable.chunks[0].text == "ABB"
    assert "fontTools is required" in caplog.text


@pytest.mark.parametrize("algorithm", ["AES-128", "AES-256"])
@pytest.mark.parametrize("password", ["", "generated-password"])
def test_aes_pdf_keeps_password_requirement_and_source_hash(tmp_path, algorithm, password):
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(aes_pdf())))
    writer.encrypt(password, owner_password="generated-owner", algorithm=algorithm)
    source = tmp_path / "generated-encrypted.pdf"
    writer.write(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = extract_file(source)
    if password:
        assert result.status == "encrypted" and not result.chunks
    else:
        assert result.status == "ok" and result.chunks[0].text == "AESProof"
        assert result.chunks[0].page_start == result.chunks[0].page_end == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_pdf_dependency_upgrade_retries_failed_pdf_and_zip_only(tmp_path, monkeypatch):
    pdf = tmp_path / "encrypted.pdf"
    pdf.write_bytes(aes_pdf())
    archive = tmp_path / "supplement.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("encrypted.pdf", aes_pdf())
    csv = tmp_path / "unchanged.csv"
    csv.write_text("gene,value\ncontrol,1\n")
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{A,title={Generated},Bdsk-File-1={encrypted.pdf},"
                   "Bdsk-File-2={supplement.zip},Bdsk-File-3={unchanged.csv}}")
    config = Config(bib, tmp_path / "index.sqlite3")
    versions = dict(indexer.EXTRACTION_VERSIONS)
    original = indexer.extract_file
    monkeypatch.setattr(indexer, "EXTRACTION_VERSIONS", {**versions, ".pdf": "1"})

    def previous(path, options):
        if path.suffix in {".pdf", ".zip"}:
            return ExtractionResult(status="error", error="generated missing AES dependency")
        return original(path, options)

    monkeypatch.setattr(indexer, "extract_file", previous)
    indexer.index_library(config)
    before = {p: p.read_bytes() for p in (pdf, archive, csv, bib)}
    monkeypatch.setattr(indexer, "EXTRACTION_VERSIONS", versions)
    monkeypatch.setattr(indexer, "extract_file", original)
    report = indexer.index_library(config)
    assert report["files_extracted"] == 2 and report["files_reused"] == 1
    with closing(connect(config.database, readonly=True)) as db:
        matches = SQLiteSearch(db).search_fulltext("AESProof")
        assert len(matches) == 2 and any(m["member_path"] == "encrypted.pdf" for m in matches)
        assert all(m["page_start"] == m["page_end"] == 1 for m in matches)
    assert before == {p: p.read_bytes() for p in before}
    assert indexer.index_library(config)["files_extracted"] == 0
