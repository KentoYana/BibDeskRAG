"""Shared extraction records and limits; extracted text is untrusted data."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable, Iterator
import math
import json


@dataclass(frozen=True)
class ExtractionOptions:
    chunk_size: int = 1500
    chunk_overlap: int = 200
    max_file_bytes: int = 200 * 1024 * 1024
    max_archive_members: int = 1000
    max_archive_bytes: int = 200 * 1024 * 1024
    max_compression_ratio: float = 100
    max_chunks: int = 50000
    table_header_start: int = 1
    table_header_rows: int = 1

    def __post_init__(self) -> None:
        integer_fields = (
            "table_header_start",
            "table_header_rows",
            "chunk_size",
            "chunk_overlap",
            "max_file_bytes",
            "max_archive_members",
            "max_archive_bytes",
            "max_chunks",
        )
        for name in integer_fields:
            # bool is an int subclass, but TOML booleans are never valid limits.
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.table_header_start <= 1000000 or not 0 <= self.table_header_rows <= 100:
            raise ValueError("Require table_header_start=1..1000000 and table_header_rows=0..100")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Require 0 <= chunk_overlap < chunk_size")
        for name in ("max_file_bytes", "max_archive_members", "max_archive_bytes", "max_chunks"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if (
            type(self.max_compression_ratio) not in (int, float)
            or (
                type(self.max_compression_ratio) is float
                and not math.isfinite(self.max_compression_ratio)
            )
            or self.max_compression_ratio < 1
        ):
            raise ValueError("max_compression_ratio must be a finite number >= 1")


@dataclass(frozen=True)
class ExtractedChunk:
    text: str
    source_type: str
    page_start: int | None = None
    page_end: int | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    member_path: str | None = None
    table_json: str = "{}"


@dataclass
class ExtractionResult:
    chunks: list[ExtractedChunk] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None
    members: list[dict] = field(default_factory=list)


class ExtractionLimitError(ValueError):
    """An input exceeds an explicitly configured local resource limit."""


class ExpansionBudget:
    """A shared budget across an archive, document packages and IWA blocks."""

    def __init__(self, options: ExtractionOptions):
        self.bytes = options.max_archive_bytes
        self.members = options.max_archive_members

    def charge(self, size: int, members: int = 0) -> None:
        if size < 0 or size > self.bytes:
            raise ExtractionLimitError("Container expanded size exceeds shared limit")
        if members > self.members:
            raise ExtractionLimitError("Container member count exceeds shared limit")
        self.bytes -= size
        self.members -= members


def split_text(text: str, options: ExtractionOptions) -> Iterator[str]:
    """Split within a provenance unit, retaining a configurable character overlap."""
    text = text.strip()
    start = 0
    while start < len(text):
        end = min(start + options.chunk_size, len(text))
        yield text[start:end]
        if end == len(text):
            return
        start = end - options.chunk_overlap


def append_chunk(
    chunks: list[ExtractedChunk], chunk: ExtractedChunk, options: ExtractionOptions
) -> None:
    if len(chunks) >= options.max_chunks:
        raise ExtractionLimitError(f"Chunk limit exceeded ({options.max_chunks})")
    chunks.append(chunk)


def clip_table_provenance(table: dict, start: int, end: int) -> dict:
    """Map a source-text slice to cell offsets; never infer a value from a fragment."""
    if not table:
        return {}
    cells = []
    for cell in table["cells"]:
        left, right = max(start, cell["text_start"]), min(end, cell["text_end"])
        empty = cell["cell_length"] == 0 and start <= left == right <= end
        if left >= right and not empty:
            continue
        first = cell["cell_start"] + left - cell["text_start"]
        last = cell["cell_end"] - (cell["text_end"] - right)
        cells.append({**cell, "text_start": left - start, "text_end": right - start,
                      "cell_start": first, "cell_end": last,
                      "complete": first == 0 and last == cell["cell_length"]})
    return {**table, "cells": cells}


def table_chunks(
    rows: Iterable[tuple[int, list[str]]],
    options: ExtractionOptions,
    source_type: str,
    sheet_name: str | None = None,
) -> list[ExtractedChunk]:
    """Bounded text plus exact row/column and half-open character spans per cell.

    Header rows are explicitly configured physical rows/CSV records, never inferred.
    Small headers repeat for readability; large headers are indexed once with their
    own coordinates. Structured coordinates survive every continuation, including
    overlap and whitespace. At most 32 cell spans are stored in a chunk.
    """
    chunks: list[ExtractedChunk] = []
    header_end = options.table_header_start + options.table_header_rows
    headers = []
    iterator = iter(rows)
    # Buffer only the configured header window, not all rows before a late header.
    # Early rows are emitted normally; header coordinates are known in advance.
    header_text, header_cells = "", []
    pending_text, pending_cells = "", []
    repeated_header = False

    def units(number, values, kind):
        for column in range(0, len(values), 16):
            text = "Columns: " if kind == "header" else f"Row {number}: "
            spans = []
            for index, value in enumerate(values[column:column + 16], column + 1):
                if spans:
                    text += " | "
                offset = len(text)
                text += value
                spans.append(dict(row=number, column=index, kind=kind, text_start=offset,
                                  text_end=len(text), cell_start=0, cell_end=len(value),
                                  cell_length=len(value), complete=True))
            yield text, spans

    def emit(text, cells, readable):
        start = 0
        table = {"version": 1, "header_start": options.table_header_start,
                 "header_rows": options.table_header_rows,
                 "header_status": "assumed" if options.table_header_rows else "none",
                 "labels_in_text": readable, "cells": cells}
        while start < len(text):
            end = min(start + options.chunk_size, len(text))
            provenance = clip_table_provenance(table, start, end)
            if provenance["cells"]:
                data = [c for c in provenance["cells"] if c["kind"] == "data"]
                locations = data or provenance["cells"]
                provenance["labels_in_text"] = readable and start == 0 and end == len(text)
                append_chunk(chunks, ExtractedChunk(
                    text[start:end], source_type, sheet_name=sheet_name,
                    row_start=min(c["row"] for c in locations),
                    row_end=max(c["row"] for c in locations),
                    table_json=json.dumps(provenance, ensure_ascii=False, separators=(",", ":")),
                ), options)
            if end == len(text):
                break
            start = end - options.chunk_overlap

    def join(text, cells, other, spans):
        offset = len(text) + (1 if text else 0)
        return (text + ("\n" if text else "") + other,
                cells + [{**c, "text_start": c["text_start"] + offset,
                          "text_end": c["text_end"] + offset} for c in spans])

    def flush():
        nonlocal pending_text, pending_cells
        if pending_cells:
            emit(pending_text, pending_cells, repeated_header)
        pending_text, pending_cells = "", []

    def add_data(number, values):
        nonlocal pending_text, pending_cells
        for text, cells in units(number, values, "data"):
            # Header spans also count toward the per-chunk provenance bound.
            if pending_cells and (len(pending_text) + 1 + len(text) > options.chunk_size
                                  or len(pending_cells) + len(cells) > 32):
                flush()
            if not pending_cells and repeated_header:
                pending_text, pending_cells = header_text, list(header_cells)
            pending_text, pending_cells = join(pending_text, pending_cells, text, cells)
            if len(pending_text) >= options.chunk_size:
                flush()

    for number, values in iterator:
        is_header = options.table_header_rows and options.table_header_start <= number < header_end
        if is_header:
            headers.extend(units(number, values, "header"))
        else:
            # Finish header preparation when leaving the configured window.
            if headers:
                flush()
                repeated_header = (
                    sum(len(text) for text, _ in headers) + len(headers) - 1 <= options.chunk_size // 2
                    and sum(len(cells) for _, cells in headers) <= 16)
                if repeated_header:
                    for text, cells in headers:
                        header_text, header_cells = join(header_text, header_cells, text, cells)
                else:
                    for text, cells in headers:
                        emit(text, cells, False)
                    header_text, header_cells = "", []
                headers = []
            add_data(number, values)
    flush()
    # Header-only tables still expose all names and their original coordinates.
    if headers:
        for text, cells in headers:
            emit(text, cells, False)
    return chunks
