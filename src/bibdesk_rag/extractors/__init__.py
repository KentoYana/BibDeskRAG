"""Bounded, read-only attachment extraction. No network calls or shell execution."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from .common import ExtractionOptions, ExtractionResult, ExtractedChunk
from .formats import EXCLUDED_FORMATS

__all__ = ["extract_file", "ExtractionOptions", "ExtractionResult", "ExtractedChunk"]


def extract_stream(
    source: BinaryIO, suffix: str, options: ExtractionOptions, *, allow_archive: bool = True,
    budget=None,
) -> ExtractionResult:
    if suffix in EXCLUDED_FORMATS:
        return ExtractionResult(status="excluded", error="Images and videos are explicitly excluded")
    if suffix == ".pdf":
        from .pdf import extract_pdf

        return extract_pdf(source, options)
    if suffix in {".csv", ".tsv"}:
        from .csv import extract_delimited

        return extract_delimited(source, options, "\t" if suffix == ".tsv" else ",")
    if suffix == ".xlsx":
        from .excel import extract_excel

        return extract_excel(source, options, budget=budget)
    if suffix in {".docx", ".pptx"}:
        from .office import extract_office

        return extract_office(source, suffix, options, budget=budget)
    if suffix in {".doc", ".xls"}:
        from .legacy import extract_doc, extract_xls

        return (extract_doc if suffix == ".doc" else extract_xls)(source, options)
    if suffix == ".tex":
        from .tex import extract_tex

        return extract_tex(source, options)
    if suffix in {".key", ".pages", ".numbers"}:
        from .iwork import extract_iwork

        return extract_iwork(source, suffix, options, budget=budget)
    if suffix == ".zip" and allow_archive:
        from .archive import extract_archive

        return extract_archive(source, options, budget=budget)
    return ExtractionResult(
        status="unsupported", error=f"Unsupported file format: {suffix or '(none)'}"
    )


def extract_file(path: Path, options: ExtractionOptions | None = None) -> ExtractionResult:
    options = options or ExtractionOptions()
    path = Path(path)
    try:
        from .sources import is_iwork_directory, source_stat

        if is_iwork_directory(path):
            from .iwork import extract_iwork

            source_stat(path, options)
            return extract_iwork(path, path.suffix.lower(), options)
        if not path.is_file():
            return ExtractionResult(
                status="missing", error=f"File does not exist or is not a regular file: {path}"
            )
        if path.suffix.lower() in EXCLUDED_FORMATS:
            return ExtractionResult(status="excluded", error="Images and videos are explicitly excluded")
        if path.stat().st_size > options.max_file_bytes:
            return ExtractionResult(
                status="error", error=f"File exceeds max_file_bytes ({options.max_file_bytes})"
            )
        with path.open("rb") as source:
            return extract_stream(source, path.suffix.lower(), options)
    except (OSError, ValueError) as exc:
        return ExtractionResult(status="error", error=f"{type(exc).__name__}: {exc}")
