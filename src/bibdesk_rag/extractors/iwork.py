"""Bounded iWork XML/IWA text reader. No apps, previews, media or generic string scraping.

Wire/field references: docs/file-formats.md. IWA extraction is deliberately partial:
object locations are retained; rendered page/slide order is not inferred.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext
import io
import math
from pathlib import Path
import stat
import struct
from typing import BinaryIO
import zipfile
import zlib

from defusedxml.ElementTree import fromstring

from .common import (
    ExpansionBudget, ExtractedChunk, ExtractionOptions, ExtractionResult,
    append_chunk, split_text, table_chunks,
)


def varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("Truncated IWA varint")
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("Oversized IWA varint")
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("Oversized IWA varint")


def fields(data: bytes) -> dict[int, list]:
    result = {}
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if number == 0 or number >= 1 << 29:
            raise ValueError("Invalid protobuf field number")
        if wire == 0:
            value, offset = varint(data, offset)
        else:
            if wire == 2:
                size, offset = varint(data, offset)
            elif wire in (1, 5):
                size = 8 if wire == 1 else 4
            else:
                raise ValueError("Unsupported protobuf wire type")
            if size > len(data) - offset:
                raise ValueError("Truncated IWA field")
            value = data[offset:offset + size]
            offset += size
        result.setdefault(number, []).append(value)
    return result


def one(message: dict, number: int, default=None):
    values = message.get(number, [])
    if len(values) > 1:
        raise ValueError("Ambiguous singular IWA field")
    return values[0] if values else default


def ref(data: bytes) -> int:
    return one(fields(data), 1)


def snappy(data: bytes, options: ExtractionOptions, budget: ExpansionBudget) -> bytes:
    expected, offset = varint(data)
    if expected > options.max_file_bytes:
        raise ValueError("IWA block exceeds max_file_bytes")
    if expected / max(1, len(data)) > options.max_compression_ratio:
        raise ValueError("IWA compression ratio exceeds limit")
    budget.charge(expected)
    output = bytearray()
    while offset < len(data):
        tag = data[offset]
        offset += 1
        kind = tag & 3
        if kind == 0:
            size = tag >> 2
            if size >= 60:
                width = size - 59
                if offset + width > len(data):
                    raise ValueError("Truncated Snappy literal length")
                size = int.from_bytes(data[offset:offset + width], 'little')
                offset += width
            size += 1
            if size > len(data) - offset or size > expected - len(output):
                raise ValueError("Invalid Snappy literal size")
            output.extend(data[offset:offset + size])
            offset += size
        else:
            width = (1, 2, 4)[kind - 1]
            if offset + width > len(data):
                raise ValueError("Truncated Snappy copy")
            distance = int.from_bytes(data[offset:offset + width], 'little')
            offset += width
            size = 4 + ((tag >> 2) & 7) if kind == 1 else 1 + (tag >> 2)
            if kind == 1:
                distance += (tag & 224) << 3
            if not 0 < distance <= len(output) or size > expected - len(output):
                raise ValueError("Invalid Snappy copy bounds")
            for _ in range(size):
                output.append(output[-distance])
    if len(output) != expected:
        raise ValueError("Snappy decoded length mismatch")
    return bytes(output)


def iwa_objects(data: bytes, options: ExtractionOptions, budget: ExpansionBudget):
    decoded = bytearray()
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data) or data[offset] != 0:
            raise ValueError("Invalid IWA frame")
        size = int.from_bytes(data[offset + 1:offset + 4], 'little')
        offset += 4
        if size > len(data) - offset:
            raise ValueError("Truncated IWA frame")
        decoded.extend(snappy(data[offset:offset + size], options, budget))
        offset += size
        if len(decoded) > options.max_file_bytes:
            raise ValueError("IWA stream exceeds max_file_bytes")
    offset = 0
    while offset < len(decoded):
        size, offset = varint(decoded, offset)
        if size > len(decoded) - offset:
            raise ValueError("Truncated IWA archive info")
        info = fields(bytes(decoded[offset:offset + size]))
        identifier = one(info, 1)
        offset += size
        for item in info.get(2, []):
            message = fields(item)
            length = one(message, 3)
            if not isinstance(length, int) or length > len(decoded) - offset:
                raise ValueError("Truncated IWA object payload")
            payload = bytes(decoded[offset:offset + length])
            offset += length
            yield identifier, one(message, 1), fields(payload)


def package_parts(source, options, budget, prefix=""):
    from .archive import inspect_archive

    if isinstance(source, Path):
        from .sources import package_members

        entries = package_members(source, options, include_directories=True)
        members = [(p, info) for p, info in entries if stat.S_ISREG(info.st_mode)]
        budget.charge(sum(info.st_size for _, info in members), len(entries))
        for path, _ in members:
            name = path.relative_to(source).as_posix()
            if (name.endswith('.iwa') or name in {'Index.zip', 'index.xml', 'index.apxl',
                                                 'index.xml.gz', 'index.apxl.gz'}):
                with path.open('rb') as handle:
                    data = handle.read(options.max_file_bytes + 1)
                if len(data) > options.max_file_bytes:
                    raise ValueError('iWork package member exceeds size limit')
                if name == 'Index.zip':
                    yield from package_parts(io.BytesIO(data), options, budget, 'Index.zip!/')
                else:
                    yield name, data
        return
    infos = inspect_archive(source, options, budget=budget)
    source.seek(0)
    with zipfile.ZipFile(source) as archive:
        for info in infos:
            name = info.filename
            if name.endswith(".iwa") or name in {"index.xml", "index.apxl", "index.xml.gz", "index.apxl.gz"}:
                yield prefix + name, archive.read(info)
            elif name == "Index.zip" and not prefix:
                yield from package_parts(io.BytesIO(archive.read(info)), options, budget,
                                         "Index.zip!/")


def _xml_text(data, name, suffix, options, budget, chunks):
    if name.endswith(".gz"):
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        expanded = inflater.decompress(data, min(budget.bytes, options.max_file_bytes) + 1)
        budget.charge(len(expanded))
        if not inflater.eof or inflater.unused_data or len(expanded) > options.max_file_bytes:
            raise ValueError("Invalid or oversized compressed iWork XML")
        data = expanded
    root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    for number, element in enumerate(root.iter(), 1):
        # iWork '09 SF paragraph elements, excluding metadata, media and URLs.
        if element.tag == "{http://developer.apple.com/namespaces/sf}p":
            for text in split_text("".join(element.itertext()), options):
                append_chunk(chunks, ExtractedChunk(text, suffix[1:],
                             member_path=f"{name}#element={number}"), options)


def _cell(data, strings):
    """Decode common V5 stored values. Refuse unknown layouts rather than guess."""
    if len(data) < 12 or data[0] != 5:
        raise ValueError("Numbers cell storage version is not supported")
    kind = data[1]
    flags = struct.unpack_from('<I', data, 8)[0]
    offset = 12
    values = {}
    for bit, size in ((1, 16), (2, 8), (4, 8), (8, 4), (16, 4)):
        if flags & bit:
            if offset + size > len(data):
                raise ValueError("Truncated Numbers cell")
            values[bit] = data[offset:offset + size]
            offset += size
    if kind == 0:
        return ""
    if kind == 3:
        return strings[struct.unpack('<I', values[8])[0]]
    if kind == 2 and 1 in values:
        # Apple's decimal128: 113-bit coefficient, 14-bit biased decimal exponent.
        bits = int.from_bytes(values[1], 'little')
        exponent = ((bits >> 113) & 0x3FFF) - 6176
        coefficient = bits & ((1 << 113) - 1)
        if abs(exponent) > 6144:
            raise ValueError("Unsupported Numbers decimal")
        if coefficient >= 10 ** 34:
            raise ValueError("Invalid Numbers decimal coefficient")
        with localcontext() as context:
            context.prec = 34
            return str(Decimal((-1 if bits >> 127 else 1) * coefficient).scaleb(exponent))
    if kind in {2, 6, 7} and 2 in values:
        value = struct.unpack('<d', values[2])[0]
        if not math.isfinite(value):
            raise ValueError("Non-finite Numbers cell value")
        if kind == 6:
            return 'TRUE' if value > 0 else 'FALSE'
        return str(value) + (' seconds' if kind == 7 else '')
    if kind == 5 and 4 in values:
        from datetime import datetime, timedelta

        return (datetime(2001, 1, 1) + timedelta(seconds=struct.unpack('<d', values[4])[0])).isoformat()
    raise ValueError("Numbers rich/formula/error cell needs a fuller decoder")


def _tables(objects, suffix, options, chunks):
    for (identifier, kind), (name, table) in objects.items():
        if kind != 6001:
            continue
        store = fields(one(table, 4))
        strings_id = ref(one(store, 4))
        strings = {}
        for entry in objects[(strings_id, 6005)][1].get(3, []):
            entry = fields(entry)
            if 3 in entry:
                strings[one(entry, 1)] = one(entry, 3).decode('utf-8')
        tiles = fields(one(store, 3))
        tile_size = one(tiles, 2, 256)
        if not isinstance(tile_size, int) or not 1 <= tile_size <= 65536:
            raise ValueError("Invalid Numbers tile size")
        row_count, column_count = one(table, 6), one(table, 7)
        if not isinstance(column_count, int) or not 0 <= column_count <= 10000:
            raise ValueError("Numbers table column limit exceeded")
        rows = {}
        grid_cells = 0
        for tile in tiles.get(1, []):
            tile = fields(tile)
            tile_index = one(tile, 1)
            tile_id = ref(one(tile, 2))
            tile_data = objects[(tile_id, 6002)][1]
            for row in tile_data.get(5, []):
                row = fields(row)
                number = tile_index * tile_size + one(row, 1)
                if not isinstance(row_count, int) or not 0 <= number < row_count or number in rows:
                    raise ValueError("Ambiguous Numbers row location")
                buffer, offsets = one(row, 6), one(row, 7)
                if not isinstance(buffer, bytes) or not isinstance(offsets, bytes) or len(offsets) % 2:
                    raise ValueError("Numbers pre-V5 storage is not supported")
                if len(offsets) // 2 > column_count:
                    raise ValueError("Numbers cell offsets exceed table width")
                grid_cells += len(offsets) // 2
                if grid_cells > options.max_archive_bytes // 16:
                    raise ValueError("Numbers cell grid exceeds expansion limit")
                cells = [''] * (len(offsets) // 2)
                locations = [value[0] * (4 if one(row, 8, 0) else 1)
                             for value in struct.iter_unpack('<h', offsets)]
                populated = [value for value in locations if value >= 0]
                if populated != sorted(set(populated)) or any(p >= len(buffer) for p in populated):
                    raise ValueError("Invalid Numbers cell offsets")
                ends = dict(zip(populated, populated[1:] + [len(buffer)]))
                for column, offset in enumerate(locations):
                    if offset < 0:
                        continue
                    cells[column] = _cell(buffer[offset:ends[offset]], strings)
                rows[number] = cells
        remaining = options.max_chunks - len(chunks)
        if remaining <= 0:
            raise ValueError("Chunk limit exceeded")
        title = one(table, 8, b'').decode('utf-8')
        if rows and 0 not in rows:
            rows[0] = []  # retain physical row 1 as the header, even if it is blank
        table_chunks_result = table_chunks(
            ((number + 1, values) for number, values in sorted(rows.items())),
            replace(options, max_chunks=remaining), suffix[1:], title,
        )
        chunks.extend(replace(c, member_path=f"{name}#object={identifier};table")
                      for c in table_chunks_result)


def extract_iwork(source: BinaryIO, suffix: str, options: ExtractionOptions,
                  *, budget=None) -> ExtractionResult:
    chunks = []
    problems = []
    try:
        budget = budget or ExpansionBudget(options)
        objects = {}
        found = False
        for name, data in package_parts(source, options, budget):
            found = True
            if not name.endswith('.iwa'):
                _xml_text(data, name, suffix, options, budget, chunks)
                continue
            for identifier, kind, message in iwa_objects(data, options, budget):
                if len(objects) >= options.max_chunks * 4:
                    raise ValueError("IWA object count exceeds extraction limit")
                key = identifier, kind
                if key in objects:
                    raise ValueError("Duplicate IWA object makes provenance ambiguous")
                objects[key] = name, message
                if kind == 2001:  # TSWP.StorageArchive.text; no style/URL/metadata strings.
                    for index, value in enumerate(message.get(3, []), 1):
                        for text in split_text(value.decode('utf-8'), options):
                            append_chunk(chunks, ExtractedChunk(text, suffix[1:],
                                member_path=f"{name}#object={identifier};text={index}"), options)
        if any(kind == 6001 for _, kind in objects):
            try:
                _tables(objects, suffix, options, chunks)
            except (ValueError, KeyError, TypeError, struct.error) as exc:
                problems.append(f"Table extraction incomplete: {exc}")
        if not found:
            raise ValueError("No readable iWork XML/IWA parts (possibly encrypted or unsupported layout)")
        note = "iWork partial extraction: object/XML locations only; rendered order, " \
               "page/slide numbers, formulas and complete table coverage are not guaranteed; " \
               "saved cell values may be stale"
        return ExtractionResult(chunks, 'partial' if chunks else 'no_text',
                                '; '.join([note, *problems]))
    except Exception as exc:
        return ExtractionResult(chunks, 'partial' if chunks else 'error',
                                f"{type(exc).__name__}: {exc}")
