"""Shared extraction records and limits; extracted text is untrusted data."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable, Iterator
import math


@dataclass(frozen=True)
class ExtractionOptions:
    chunk_size: int = 1500
    chunk_overlap: int = 200
    max_file_bytes: int = 100 * 1024 * 1024
    max_archive_members: int = 1000
    max_archive_bytes: int = 200 * 1024 * 1024
    max_compression_ratio: float = 100
    max_chunks: int = 50000

    def __post_init__(self) -> None:
        integer_fields = (
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


@dataclass
class ExtractionResult:
    chunks: list[ExtractedChunk] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None
    members: list[dict] = field(default_factory=list)


class ExtractionLimitError(ValueError):
    """An input exceeds an explicitly configured local resource limit."""


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


def table_chunks(
    rows: Iterable[tuple[int, list[str]]],
    options: ExtractionOptions,
    source_type: str,
    sheet_name: str | None = None,
) -> list[ExtractedChunk]:
    """Retain physical record/worksheet row numbers and repeat the column names.

    A CSV record spanning several physical lines is numbered by its record index,
    including the header as record 1. XLSX uses worksheet row coordinates.
    Values are represented without evaluating formulas or inferring missing data.
    """
    iterator = iter(rows)
    header_row = next(iterator, None)
    if header_row is None:
        return []
    header_number, headers = header_row
    header = "Columns: " + " | ".join(headers)
    chunks: list[ExtractedChunk] = []
    pending: list[str] = []
    first = last = header_number

    def flush() -> None:
        nonlocal pending
        if pending:
            for text in split_text(header + "\n" + "\n".join(pending), options):
                append_chunk(
                    chunks,
                    ExtractedChunk(
                        text, source_type, sheet_name=sheet_name, row_start=first, row_end=last
                    ),
                    options,
                )
            pending = []

    for number, values in iterator:
        line = f"Row {number}: " + " | ".join(values)
        if (
            pending
            and len(header) + sum(map(len, pending)) + len(pending) + len(line) + 1
            > options.chunk_size
        ):
            flush()
        if not pending:
            first = number
        last = number
        pending.append(line)
        if len(header) + len(line) + 1 >= options.chunk_size:
            flush()
    flush()
    if not chunks:
        for text in split_text(header, options):
            append_chunk(
                chunks,
                ExtractedChunk(
                    text,
                    source_type,
                    sheet_name=sheet_name,
                    row_start=header_number,
                    row_end=header_number,
                ),
                options,
            )
    return chunks
