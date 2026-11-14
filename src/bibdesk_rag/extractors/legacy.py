"""Read Word 97–2003 main-story text and BIFF Excel cached cell values."""

from __future__ import annotations

from dataclasses import replace
import io
import struct
from typing import BinaryIO

from .common import (
    ExtractedChunk, ExtractionOptions, ExtractionResult, append_chunk, split_text, table_chunks,
)


def _read(source: BinaryIO, options: ExtractionOptions) -> bytes:
    data = source.read(options.max_file_bytes + 1)
    if len(data) > options.max_file_bytes:
        raise ValueError("Legacy document exceeds max_file_bytes")
    return data


def extract_xls(source: BinaryIO, options: ExtractionOptions) -> ExtractionResult:
    import xlrd

    chunks = []
    book = None
    try:
        book = xlrd.open_workbook(file_contents=_read(source, options), on_demand=True,
                                  ragged_rows=True, logfile=io.StringIO())
        for index in range(book.nsheets):
            sheet = book.sheet_by_index(index)

            def rows():
                for number in range(sheet.nrows):
                    values = []
                    for cell in sheet.row(number):
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate_as_datetime(cell.value, book.datemode).isoformat()
                        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                            value = "TRUE" if cell.value else "FALSE"
                        elif cell.ctype == xlrd.XL_CELL_ERROR:
                            value = xlrd.error_text_from_code.get(cell.value, "#ERROR")
                        else:
                            value = str(cell.value) if cell.value is not None else ""
                        values.append(value)
                    yield number + 1, values

            remaining = options.max_chunks - len(chunks)
            if remaining <= 0:
                raise ValueError("Chunk limit exceeded")
            chunks.extend(table_chunks(rows(), replace(options, max_chunks=remaining),
                                       "xls", sheet.name))
            book.unload_sheet(index)
        return ExtractionResult(chunks, "partial" if chunks else "no_text",
                                "XLS cached values only; formula expressions are unavailable "
                                "and cached results may be stale" if chunks else "Empty workbook")
    except Exception as exc:
        return ExtractionResult(chunks, "partial" if chunks else "error",
                                f"{type(exc).__name__}: {exc}")
    finally:
        if book is not None:
            book.release_resources()


def _word_text(ole) -> str:
    word = ole.openstream("WordDocument").read()
    if len(word) < 34 or struct.unpack_from("<H", word)[0] != 0xA5EC:
        raise ValueError("Invalid Word document header")
    if struct.unpack_from("<H", word, 2)[0] < 0xC1:
        raise ValueError("Only Word 97–2003 binary DOC is supported")
    flags = struct.unpack_from("<H", word, 10)[0]
    if flags & 0x8100:
        raise ValueError("Encrypted/obfuscated Word document")
    # The FIB's variable-length sections locate fcClx/lcbClx (pair 33).
    offset = 34 + 2 * struct.unpack_from("<H", word, 32)[0]
    count = struct.unpack_from("<H", word, offset)[0]
    if count < 4:
        raise ValueError("Missing Word story lengths")
    main_length = struct.unpack_from("<I", word, offset + 2 + 3 * 4)[0]
    offset += 2 + 4 * count
    if struct.unpack_from("<H", word, offset)[0] < 34:
        raise ValueError("Missing Word piece table")
    start, length = struct.unpack_from("<II", word, offset + 2 + 33 * 8)
    table = ole.openstream("1Table" if flags & 0x200 else "0Table").read()
    if start + length > len(table):
        raise ValueError("Truncated Word CLX")
    clx = table[start:start + length]
    offset = 0
    while offset < len(clx) and clx[offset] == 1:
        offset += 3 + struct.unpack_from("<H", clx, offset + 1)[0]
    if offset >= len(clx) or clx[offset] != 2:
        raise ValueError("Missing Word PlcPcd")
    size = struct.unpack_from("<I", clx, offset + 1)[0]
    pieces = clx[offset + 5:offset + 5 + size]
    if len(pieces) != size or size < 4 or (size - 4) % 12:
        raise ValueError("Invalid Word piece table size")
    count = (size - 4) // 12
    positions = struct.unpack_from(f"<{count + 1}I", pieces)
    if positions[0] != 0 or any(a > b for a, b in zip(positions, positions[1:])):
        raise ValueError("Invalid Word character positions")
    if positions[-1] < main_length:
        raise ValueError("Truncated Word main story")
    parts = []
    for index in range(count):
        if positions[index] >= main_length:
            break
        chars = min(positions[index + 1], main_length) - positions[index]
        address = struct.unpack_from("<I", pieces, 4 * (count + 1) + 8 * index + 2)[0]
        compressed = bool(address & 0x40000000)
        address &= 0x3FFFFFFF
        if compressed:
            address //= 2
        size = chars * (1 if compressed else 2)
        if address + size > len(word):
            raise ValueError("Truncated Word text piece")
        parts.append(word[address:address + size].decode("cp1252" if compressed else "utf-16le"))
    return "".join(parts)


def extract_doc(source: BinaryIO, options: ExtractionOptions) -> ExtractionResult:
    import olefile

    chunks = []
    try:
        with olefile.OleFileIO(io.BytesIO(_read(source, options)),
                               raise_defects=olefile.DEFECT_INCORRECT) as ole:
            text = _word_text(ole)
        # Field instructions are not displayed document text. Retain their cached
        # display result only; no field, link or macro is evaluated.
        output = []
        fields = []
        for char in text:
            if char == "\x13":
                if len(fields) >= 64:
                    raise ValueError("Word field nesting exceeds limit")
                fields.append(False)
            elif char == "\x14" and fields:
                fields[-1] = True
            elif char == "\x15" and fields:
                fields.pop()
            elif all(fields):
                output.append(char)
        text = "".join(output).replace("\x07", "\t").replace("\x0b", "\n")
        for number, paragraph in enumerate(text.split("\r"), 1):
            for part in split_text(paragraph, options):
                append_chunk(chunks, ExtractedChunk(
                    part, "doc", member_path=f"WordDocument#main-paragraph={number}",
                ), options)
        return ExtractionResult(chunks, "partial" if chunks else "no_text",
                                "DOC main story only; auxiliary stories and layout are not extracted"
                                if chunks else "No main-story text")
    except Exception as exc:
        return ExtractionResult(chunks, "partial" if chunks else "error",
                                f"{type(exc).__name__}: {exc}")
