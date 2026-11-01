"""Streaming CSV/TSV decoding with explicit row provenance."""

from __future__ import annotations

import csv
import io
from typing import BinaryIO

from .common import ExtractionOptions, ExtractionResult, table_chunks


def extract_delimited(
    source: BinaryIO, options: ExtractionOptions, delimiter: str = ","
) -> ExtractionResult:
    # detach prevents TextIOWrapper from closing a ZIP member/caller-owned stream.
    wrapper = io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
    try:
        reader = csv.reader(wrapper, delimiter=delimiter, strict=True)
        rows = ((number, list(row)) for number, row in enumerate(reader, 1))
        chunks = table_chunks(rows, options, "tsv" if delimiter == "\t" else "csv")
        return ExtractionResult(
            chunks, "ok" if chunks else "no_text", None if chunks else "Empty table"
        )
    except (UnicodeError, csv.Error, ValueError) as exc:
        return ExtractionResult(status="error", error=f"{type(exc).__name__}: {exc}")
    finally:
        wrapper.detach()
