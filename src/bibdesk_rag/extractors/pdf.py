"""Page-bounded text extraction using pypdf, without OCR or remote services."""

from __future__ import annotations

from typing import BinaryIO

from pypdf import PdfReader

from .common import ExtractionOptions, ExtractionResult, ExtractedChunk, append_chunk, split_text


def extract_pdf(source: BinaryIO, options: ExtractionOptions) -> ExtractionResult:
    chunks: list[ExtractedChunk] = []
    problems: list[str] = []
    try:
        reader = PdfReader(source, strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            return ExtractionResult(
                status="encrypted", error="PDF requires a password; no text extracted"
            )
        for number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                problems.append(f"Page {number}: {type(exc).__name__}: {exc}")
                continue
            if not text.strip():
                problems.append(
                    f"Page {number}: no extractable text (possibly image-only; OCR not enabled)"
                )
            for part in split_text(text, options):
                append_chunk(
                    chunks, ExtractedChunk(part, "pdf", page_start=number, page_end=number), options
                )
        if problems:
            return ExtractionResult(chunks, "partial" if chunks else "no_text", "; ".join(problems))
        if not chunks:
            return ExtractionResult(status="no_text", error="PDF has no extractable text pages")
        return ExtractionResult(chunks)
    except Exception as exc:
        return ExtractionResult(
            chunks, "partial" if chunks else "error", f"{type(exc).__name__}: {exc}"
        )
