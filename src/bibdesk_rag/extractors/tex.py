"""Index literal TeX source lines; never expand macros, include files or run TeX."""

from typing import BinaryIO

from .common import ExtractedChunk, ExtractionOptions, ExtractionResult, append_chunk, split_text


def extract_tex(source: BinaryIO, options: ExtractionOptions) -> ExtractionResult:
    chunks = []
    try:
        data = source.read(options.max_file_bytes + 1)
        if len(data) > options.max_file_bytes:
            raise ValueError("TeX exceeds max_file_bytes")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Common in older Japanese manuscripts; do not silently replace bytes.
            text = data.decode("cp932")
        for number, line in enumerate(text.splitlines(), 1):
            for part in split_text(line, options):
                append_chunk(chunks, ExtractedChunk(
                    part, "tex", row_start=number, row_end=number,
                ), options)
        return ExtractionResult(chunks, "ok" if chunks else "no_text")
    except Exception as exc:
        return ExtractionResult(chunks, "partial" if chunks else "error",
                                f"{type(exc).__name__}: {exc}")
