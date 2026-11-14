"""One format policy for direct attachments and archive members."""

NEW_FORMATS = frozenset({".key", ".docx", ".xls", ".pptx", ".doc", ".tex", ".pages", ".numbers"})
PACKAGE_FORMATS = frozenset({".xlsx", ".docx", ".pptx", ".key", ".pages", ".numbers"})
TEXT_FORMATS = frozenset({".pdf", ".csv", ".tsv"}) | NEW_FORMATS | {".xlsx"}
IMAGE_FORMATS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp", ".heic",
    ".heif", ".avif", ".svg", ".ico", ".eps", ".psd", ".raw", ".cr2", ".nef",
})
VIDEO_FORMATS = frozenset({
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mpg", ".mpeg", ".wmv",
    ".flv", ".3gp", ".mts", ".m2ts", ".ogv",
})
EXCLUDED_FORMATS = IMAGE_FORMATS | VIDEO_FORMATS
# Changing extraction policy must also invalidate cached unsupported records.
EXTRACTION_REVISION = "office-iwork-1"

# Frozen baseline for pre-versioned indexes; never edit these historical values.
LEGACY_EXTRACTION_VERSIONS = dict.fromkeys(
    (".pdf", ".csv", ".tsv", ".xlsx", ".zip", ".key", ".docx",
     ".xls", ".pptx", ".doc", ".tex", ".pages", ".numbers"), "1")
# Bump affected formats on parser/policy/dependency changes. ZIP also depends on
# every member parser's version, computed by the indexer.
EXTRACTION_VERSIONS = dict(LEGACY_EXTRACTION_VERSIONS)
# fontTools enables CFF decoding and cryptography enables empty-password AES PDFs.
EXTRACTION_VERSIONS[".pdf"] = "2"
