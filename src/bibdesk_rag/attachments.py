"""Read-only resolution of BibDesk's attachment paths and native locators.

The ordinary path comes from ``Entry.files``. BibDeskParser 0.8.1 does not
publicly expose its bookmark bytes, so the missing-path fallback has one
isolated compatibility bridge to its decoded file objects. No plist parser,
file search, bookmark refresh, mount, or library mutation is performed here.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class AttachmentReference:
    path: str
    original: str
    error: str | None = None
    role: str = "attachment"


def attachment_role(path: str) -> str:
    """A descriptive filename heuristic, not a scientific classification."""
    return (
        "supplementary"
        if re.search(
            r"supplement|supporting|(?:^|[ _.-])suppl?(?:[ _.-]|$)",
            Path(path).name,
            re.IGNORECASE,
        )
        else "attachment"
    )


def _core_foundation():
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer = ctypes.c_void_p
    signatures = {
        "CFDataCreate": ([pointer, pointer, ctypes.c_long], pointer),
        "CFURLCreateBookmarkDataFromAliasRecord": ([pointer, pointer], pointer),
        "CFURLCreateByResolvingBookmarkData": (
            [
                pointer,
                pointer,
                ctypes.c_ulong,
                pointer,
                pointer,
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(pointer),
            ],
            pointer,
        ),
        "CFURLGetFileSystemRepresentation": (
            [pointer, ctypes.c_ubyte, pointer, ctypes.c_long],
            ctypes.c_ubyte,
        ),
        "CFRelease": ([pointer], None),
    }
    for name, (args, result) in signatures.items():
        function = getattr(cf, name)
        function.argtypes = args
        function.restype = result
    return cf


def resolve_native_reference(bookmark: bytes | None, alias_data: bytes | None) -> Path | None:
    """Resolve a native locator on macOS without UI or volume mounting.

    Stale bookmarks are deliberately not rewritten. Legacy alias records are
    converted to bookmarks in memory through Apple's API. Failure is reported
    by the caller as a missing attachment, rather than stopping an index run.
    """
    if sys.platform != "darwin" or not (bookmark or alias_data):
        return None
    payload = bookmark or alias_data
    if not isinstance(payload, bytes) or len(payload) > 4 * 1024 * 1024:
        return None
    cf = _core_foundation()
    buffer = ctypes.create_string_buffer(payload)
    data = cf.CFDataCreate(None, buffer, len(payload))
    if not data:
        return None
    converted = None
    url = None
    error = ctypes.c_void_p()
    try:
        if not bookmark:
            converted = cf.CFURLCreateBookmarkDataFromAliasRecord(None, data)
            if not converted:
                return None
        stale = ctypes.c_ubyte()
        # kCFURLBookmarkResolutionWithoutUIMask | WithoutMountingMask
        url = cf.CFURLCreateByResolvingBookmarkData(
            None,
            converted or data,
            (1 << 8) | (1 << 9),
            None,
            None,
            ctypes.byref(stale),
            ctypes.byref(error),
        )
        if not url:
            return None
        path_buffer = ctypes.create_string_buffer(32768)
        if not cf.CFURLGetFileSystemRepresentation(url, True, path_buffer, len(path_buffer)):
            return None
        return Path(os.fsdecode(path_buffer.value))
    finally:
        for reference in (url, error.value, converted, data):
            if reference:
                cf.CFRelease(reference)


def resolve_attachments(entry, bib_path: Path) -> list[AttachmentReference]:
    """Resolve precisely the linked files; never scan directories for matches."""
    base = bib_path.resolve().parent
    try:
        paths = entry.files
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        return [
            AttachmentReference(
                path=str(base / f".unresolved-{entry.key}"),
                original="Bdsk-File",
                error=f"invalid BibDesk attachment data: {exc}",
            )
        ]
    result = []
    native_objects = None
    for index, original in enumerate(paths):
        error = None
        try:
            if not isinstance(original, str) or not original or "\x00" in original:
                raise ValueError("empty or invalid attachment path")
            candidate = Path(original).expanduser()
            if not candidate.is_absolute():
                candidate = base / candidate
            candidate = candidate.resolve()
            if not candidate.is_file():
                # 0.8.1 compatibility bridge, limited to unavailable paths.
                if native_objects is None:
                    native_objects = entry._file_objects()
                native = native_objects[index]
                moved = resolve_native_reference(native.bookmark, native.alias_data)
                if moved is not None and moved.is_file():
                    candidate = moved.resolve()
                else:
                    error = "attachment does not exist or is not a regular file"
                    if native.bookmark or native.alias_data:
                        error += "; native bookmark/alias could not be resolved"
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            candidate = base / f".unresolved-{entry.key}-{index + 1}"
            error = f"attachment resolution failed: {exc}"
        result.append(
            AttachmentReference(
                str(candidate), str(original), error, attachment_role(str(original))
            )
        )
    return result
