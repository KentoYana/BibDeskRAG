from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import stat
import zipfile

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from bibdesk_rag.extractors import ExtractionOptions, extract_file


def make_pdf(path: Path, pages: list[str], *, password: str | None = None) -> None:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        stream = DecodedStreamObject()
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 12 Tf 50 700 Td ({safe}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    with path.open("wb") as handle:
        writer.write(handle)


def test_pdf_pages_overlap_and_source_unchanged(tmp_path):
    source = tmp_path / "supplement 日本語.pdf"
    make_pdf(source, ["RecQ helicase " * 30, "Supplementary UV mutagenesis"])
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    options = ExtractionOptions(chunk_size=70, chunk_overlap=10)
    result = extract_file(source, options)
    assert result.status == "ok"
    assert {c.page_start for c in result.chunks} == {1, 2}
    assert all(c.page_start == c.page_end and len(c.text) <= 70 for c in result.chunks)
    assert result.chunks[0].text[-10:] == result.chunks[1].text[:10]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_pdf_unextractable_states(tmp_path):
    source = tmp_path / "locked.pdf"
    make_pdf(source, ["private text"], password="secret")
    assert extract_file(source).status == "encrypted"
    blank = tmp_path / "image.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(blank)
    assert extract_file(blank).status == "no_text"
    corrupt = tmp_path / "broken.pdf"
    corrupt.write_bytes(b"not a pdf")
    assert extract_file(corrupt).status == "error"


@pytest.mark.parametrize("suffix,delimiter", [("csv", ","), ("tsv", "\t")])
def test_table_provenance(tmp_path, suffix, delimiter):
    source = tmp_path / f"supplement.{suffix}"
    source.write_text(
        delimiter.join(["gene", "measurement"])
        + "\n"
        + delimiter.join(["hH3-K4R", "0.123"])
        + "\n"
        + delimiter.join(["Δset-1", "NA"])
        + "\n",
        encoding="utf-8-sig",
    )
    result = extract_file(source)
    assert result.status == "ok"
    assert result.chunks[0].row_start == 2 and result.chunks[0].row_end == 3
    assert "Columns: gene | measurement" in result.chunks[0].text
    assert "0.123" in result.chunks[0].text and "NA" in result.chunks[0].text


def test_csv_streaming_chunk_rows_and_multiline_record(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text('gene,note\nRecQ,"first\nsecond"\nmus-9,third\n' + "x,123456789\n" * 100)
    result = extract_file(source, ExtractionOptions(chunk_size=80, chunk_overlap=5))
    assert len(result.chunks) > 10
    assert result.chunks[0].row_start == 2
    assert "first\nsecond" in result.chunks[0].text
    assert result.chunks[-1].row_end == 103
    assert all(len(c.text) <= 80 for c in result.chunks)


def test_xlsx_sheet_row_column_and_formula(tmp_path):
    source = tmp_path / "Supplement.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "遺伝子"
    sheet.append(["gene", "count", "formula"])
    sheet.append(["RecQ", 42, "=B2*2"])
    sheet.append(["mus-9", None, None])
    second = workbook.create_sheet("Control")
    second.append(["name", "value"])
    second.append(["wild type", 0])
    workbook.save(source)
    before = source.read_bytes()
    result = extract_file(source)
    assert result.status == "ok"
    assert {c.sheet_name for c in result.chunks} == {"遺伝子", "Control"}
    assert result.chunks[0].row_start == 2 and result.chunks[0].row_end == 3
    assert "=B2*2" in result.chunks[0].text  # never evaluate formulas
    assert "gene | count | formula" in result.chunks[0].text
    assert source.read_bytes() == before


def test_safe_zip_members_and_unsupported_records(tmp_path):
    source = tmp_path / "supplement.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("data/日本語 data.csv", "gene,value\nRecQ,7\n")
        archive.writestr("readme.txt", "unsupported text")
        archive.writestr("nested.zip", b"not expanded")
    before = source.read_bytes()
    result = extract_file(source)
    assert result.status == "partial"
    assert result.chunks[0].member_path == "data/日本語 data.csv"
    assert result.members[1]["status"] == "unsupported"
    assert result.members[2]["status"] == "unsupported"
    assert source.read_bytes() == before
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("name", ["../evil.csv", "/absolute.csv", r"..\evil.csv", r"C:\evil.csv"])
def test_zip_slip_rejected_before_any_extraction(tmp_path, name):
    source = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("safe.csv", "a,b\n1,2\n")
        archive.writestr(name, "bad")
    result = extract_file(source)
    assert result.status == "error" and not result.chunks
    assert "Unsafe ZIP member" in result.error


def test_zip_symlink_rejected(tmp_path):
    source = tmp_path / "links.zip"
    info = zipfile.ZipInfo("link.csv")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(info, "/etc/passwd")
    result = extract_file(source)
    assert result.status == "error" and "symlink" in result.error


def test_zip_duplicate_paths_rejected_for_unambiguous_citations(tmp_path):
    source = tmp_path / "duplicates.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("data.csv", "a,b\n1,2\n")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("data.csv", "a,b\n3,4\n")
    result = extract_file(source)
    assert result.status == "error" and "provenance ambiguous" in result.error


def test_archive_limits_and_xlsx_preflight(tmp_path):
    source = tmp_path / "bomb.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large.csv", "a" * 10000)
        archive.writestr("second.csv", "a,b\n1,2\n")
    assert "compression ratio" in extract_file(source).error
    options = ExtractionOptions(max_compression_ratio=10000)
    assert "member count" in extract_file(source, replace(options, max_archive_members=1)).error
    assert "expanded size" in extract_file(source, replace(options, max_archive_bytes=100)).error
    xlsx = tmp_path / "fake.xlsx"
    xlsx.write_bytes(source.read_bytes())
    assert "compression ratio" in extract_file(xlsx).error


def test_xlsx_rejects_xml_entities_and_nested_expansion_budget(tmp_path):
    source = tmp_path / "entities.xlsx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "xl/workbook.xml", '<!DOCTYPE x [<!ENTITY attack "value">]><x>&attack;</x>'
        )
    result = extract_file(source)
    assert result.status == "error" and "DTDForbidden" in result.error

    workbook = Workbook()
    workbook.active.append(["gene", "val"])
    workbook.active.append(["RecQ", 42])
    normal = tmp_path / "normal.xlsx"
    workbook.save(normal)
    with zipfile.ZipFile(normal) as archive:
        inner_size = sum(info.file_size for info in archive.infolist())
    outer = tmp_path / "nested.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.write(normal, "normal.xlsx")
    budget = max(inner_size, normal.stat().st_size) + 1
    result = extract_file(outer, ExtractionOptions(max_archive_bytes=budget))
    assert result.status == "error" and "nested XLSX expanded size" in result.error
    result = extract_file(outer)
    assert result.status == "ok" and result.chunks[0].member_path == "normal.xlsx"


def test_global_chunk_file_limits_missing_and_unsupported(tmp_path):
    source = tmp_path / "many.csv"
    source.write_text("gene,val\n" + "mus-9,12345\n" * 100)
    result = extract_file(source, ExtractionOptions(chunk_size=30, chunk_overlap=2, max_chunks=2))
    assert result.status == "error" and "Chunk limit" in result.error
    assert extract_file(source, ExtractionOptions(max_file_bytes=2)).status == "error"
    assert extract_file(tmp_path / "missing.pdf").status == "missing"
    old = tmp_path / "old.xls"
    old.write_bytes(b"legacy workbook")
    assert extract_file(old).status == "unsupported"


def test_invalid_configuration():
    with pytest.raises(ValueError):
        ExtractionOptions(chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValueError):
        ExtractionOptions(max_chunks=0)


@pytest.mark.parametrize(
    "name",
    [
        "chunk_size",
        "chunk_overlap",
        "max_file_bytes",
        "max_archive_members",
        "max_archive_bytes",
        "max_chunks",
    ],
)
@pytest.mark.parametrize("value", [True, False, 5.5, "1500", None])
def test_invalid_limit_types_are_clear_value_errors(name, value):
    with pytest.raises(ValueError, match=f"{name} must be an integer"):
        ExtractionOptions(**{name: value})


@pytest.mark.parametrize(
    "value", [True, False, "100", None, float("nan"), float("inf"), float("-inf"), -1]
)
def test_invalid_ratio_is_clear_value_error(value):
    with pytest.raises(ValueError, match="finite number"):
        ExtractionOptions(max_compression_ratio=value)
