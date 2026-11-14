"""ZIP member inspection and bounded in-memory extraction; never extract to disk."""

from __future__ import annotations

from dataclasses import replace
import io
from pathlib import PurePosixPath
import re
import stat
from typing import BinaryIO
import zipfile

from .common import ExpansionBudget, ExtractionLimitError, ExtractionOptions, ExtractionResult
from .formats import EXCLUDED_FORMATS, TEXT_FORMATS


def _validate_member(info: zipfile.ZipInfo, options: ExtractionOptions) -> None:
    name = info.filename
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if (
        not name
        or "\x00" in info.orig_filename
        or name.startswith(("/", "\\"))
        or ".." in parts
        or re.match(r"^[A-Za-z]:", name)
    ):
        raise ValueError(f"Unsafe ZIP member path: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
        raise ValueError(f"ZIP special file/symlink forbidden: {name!r}")
    if info.flag_bits & 1:
        raise ValueError(f"Encrypted ZIP member unsupported: {name!r}")
    if info.file_size > options.max_file_bytes:
        raise ExtractionLimitError(f"ZIP member exceeds max_file_bytes: {name!r}")
    if (
        info.file_size
        and info.file_size / max(1, info.compress_size) > options.max_compression_ratio
    ):
        raise ExtractionLimitError(f"ZIP compression ratio exceeds limit: {name!r}")


def inspect_archive(source: BinaryIO, options: ExtractionOptions, *, budget=None
                    ) -> list[zipfile.ZipInfo]:
    """Preflight ZIP and XLSX containers before opening any member data."""
    source.seek(0)
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > options.max_archive_members:
            raise ExtractionLimitError(f"ZIP member count exceeds {options.max_archive_members}")
        total = 0
        names = set()
        for info in members:
            _validate_member(info, options)
            if info.filename in names:
                raise ValueError(
                    f"Duplicate ZIP member path makes provenance ambiguous: {info.filename!r}"
                )
            names.add(info.filename)
            total += info.file_size
            if total > options.max_archive_bytes:
                raise ExtractionLimitError(f"ZIP expanded size exceeds {options.max_archive_bytes}")
        if budget is not None:
            budget.charge(total, len(members))
        return members


def extract_archive(source: BinaryIO, options: ExtractionOptions, *, budget=None) -> ExtractionResult:
    from . import extract_stream

    result = ExtractionResult()
    try:
        budget = budget or ExpansionBudget(options)
        members = inspect_archive(source, options, budget=budget)
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            actual_total = 0
            for info in members:
                if info.is_dir():
                    result.members.append(
                        {"path": info.filename, "file_type": "directory", "status": "directory"}
                    )
                    continue
                suffix = PurePosixPath(info.filename).suffix.lower()
                record = {
                    "path": info.filename,
                    "file_type": suffix.lstrip(".") or "unknown",
                    "size": info.file_size,
                }
                result.members.append(record)
                if suffix in EXCLUDED_FORMATS:
                    record.update(status="excluded", error="Images and videos are explicitly excluded")
                    continue
                if suffix not in TEXT_FORMATS:
                    record.update(
                        status="unsupported",
                        error="Nested ZIP archives are not parsed"
                        if suffix == ".zip"
                        else "Unsupported file format",
                    )
                    continue
                remaining = options.max_chunks - len(result.chunks)
                if remaining <= 0:
                    raise ExtractionLimitError(f"Chunk limit exceeded ({options.max_chunks})")
                # Read limit + 1 and compare actual bytes, independently of declared sizes.
                with archive.open(info, "r") as member:
                    payload = member.read(
                        min(options.max_file_bytes, options.max_archive_bytes - actual_total) + 1
                    )
                actual_total += len(payload)
                if (
                    len(payload) > options.max_file_bytes
                    or actual_total > options.max_archive_bytes
                ):
                    raise ExtractionLimitError("ZIP actual expanded size exceeds limit")
                child = extract_stream(
                    io.BytesIO(payload),
                    suffix,
                    replace(options, max_chunks=remaining),
                    allow_archive=False,
                    budget=budget,
                )
                record.update(status=child.status, error=child.error)
                result.chunks.extend(
                    replace(chunk, member_path=info.filename + (
                        "!/" + chunk.member_path if chunk.member_path else ""
                    )) for chunk in child.chunks
                )
        errors = [
            f"{m['path']}: {m.get('error')}"
            for m in result.members
            if m["status"] not in {"ok", "directory", "excluded"}
        ]
        if errors:
            result.status = "partial" if result.chunks else (
                "error" if any(m["status"] == "error" for m in result.members) else "no_text"
            )
            result.error = "; ".join(errors)
        elif not result.chunks:
            result.status = "no_text"
            result.error = "Archive contains no extractable text"
    except Exception as exc:
        result.status = "partial" if result.chunks else "error"
        result.error = f"{type(exc).__name__}: {exc}"
    return result
