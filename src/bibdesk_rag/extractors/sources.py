"""Bounded inspection of one explicitly linked iWork directory package."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat

from .common import ExtractionOptions

IWORK_FORMATS = frozenset({'.key', '.pages', '.numbers'})


def is_iwork_directory(path: Path) -> bool:
    return path.suffix.lower() in IWORK_FORMATS and path.is_dir()


def package_members(path: Path, options: ExtractionOptions, *, include_directories=False):
    """Inspect only this package, never search for attachments or follow symlinks."""
    pending = [path]
    members = []
    total = count = 0
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                count += 1
                if count > options.max_archive_members:
                    raise ValueError('iWork package member count exceeds limit')
                info = entry.stat(follow_symlinks=False)
                child = Path(entry.path)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(child)
                    if include_directories:
                        members.append((child, info))
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                    if total > options.max_file_bytes or total > options.max_archive_bytes:
                        raise ValueError('iWork package size exceeds limit')
                    members.append((child, info))
                else:
                    raise ValueError('iWork package symlink/special file forbidden')
    return sorted(members, key=lambda item: item[0].relative_to(path).as_posix())


@dataclass(frozen=True)
class SourceStat:
    st_size: int
    st_mtime_ns: int
    st_ino: int


def source_stat(path: Path, options: ExtractionOptions):
    if not is_iwork_directory(path):
        return path.stat()
    signature = hashlib.sha256()
    total = 0
    for child, info in package_members(path, options):
        signature.update(repr((child.relative_to(path).as_posix(), info.st_size,
                               info.st_mtime_ns, info.st_ino)).encode('utf-8'))
        total += info.st_size
    # A stable signed-64-bit signature fits the existing SQLite stat column.
    stamp = int.from_bytes(signature.digest()[:8], 'big') & ((1 << 63) - 1)
    return SourceStat(total, stamp, path.stat().st_ino)


def source_digest(path: Path, options: ExtractionOptions) -> str:
    result = hashlib.sha256()
    members = package_members(path, options)
    total = 0
    for child, _ in members:
        relative = child.relative_to(path).as_posix().encode('utf-8')
        result.update(len(relative).to_bytes(8, 'big') + relative)
        with child.open('rb') as handle:
            digest = hashlib.sha256()
            size = 0
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                size += len(block)
                total += len(block)
                if total > options.max_file_bytes or total > options.max_archive_bytes:
                    raise ValueError('iWork package member exceeds size limit')
                digest.update(block)
        result.update(size.to_bytes(8, 'big') + digest.digest())
    return result.hexdigest()
