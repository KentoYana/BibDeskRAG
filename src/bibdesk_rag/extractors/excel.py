"""Read XLSX cell values/formulas locally, preserving sheet and row coordinates."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import BinaryIO
import zipfile

from defusedxml.ElementTree import iterparse
from openpyxl import load_workbook

from .common import ExtractionOptions, ExtractionResult, table_chunks


def cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def extract_excel(source: BinaryIO, options: ExtractionOptions) -> ExtractionResult:
    from .archive import inspect_archive

    chunks = []
    workbook = None
    try:
        inspect_archive(source, options)
        source.seek(0)
        # Validate every XML part before openpyxl sees it. This remains safe even
        # when an optional XML backend or environment setting differs locally.
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if not info.is_dir() and info.filename.lower().endswith((".xml", ".rels")):
                    with archive.open(info) as member:
                        for _, element in iterparse(
                            member,
                            events=("end",),
                            forbid_dtd=True,
                            forbid_entities=True,
                            forbid_external=True,
                        ):
                            element.clear()
        source.seek(0)
        # Formula text is indexed literally; no calculation or external links.
        workbook = load_workbook(source, read_only=True, data_only=False, keep_links=False)
        for sheet in workbook.worksheets:
            # Ignore incorrect advertised dimensions; visit actual XML rows.
            sheet.reset_dimensions()
            rows = (
                (number, [cell_text(v) for v in row])
                for number, row in enumerate(sheet.iter_rows(values_only=True), 1)
            )
            from dataclasses import replace

            remaining = options.max_chunks - len(chunks)
            if remaining <= 0:
                raise ValueError(f"Chunk limit exceeded ({options.max_chunks})")
            chunks.extend(
                table_chunks(rows, replace(options, max_chunks=remaining), "xlsx", sheet.title)
            )
        return ExtractionResult(
            chunks, "ok" if chunks else "no_text", None if chunks else "Empty workbook"
        )
    except Exception as exc:
        return ExtractionResult(
            chunks, "partial" if chunks else "error", f"{type(exc).__name__}: {exc}"
        )
    finally:
        if workbook is not None:
            workbook.close()
