"""Shared index/query normalization; user text is never FTS query syntax."""

import re
import unicodedata

# Bump whenever matching normalization changes; refresh derived fields, not sources.
NORMALIZATION_REVISION = "1"

_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—−﹣－"})


def normalize_search(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).casefold()
    text = text.replace("δ", "delta")
    # Join biological identifiers so hh3-k4r and hh3k4r have the same token.
    return re.sub(r"(?<=\w)-(?=\w)", "", text)


def match_query(text: str) -> str:
    if len(text) > 2000:
        raise ValueError("Query exceeds 2000 characters")
    tokens = list(dict.fromkeys(re.findall(r"\w+", normalize_search(text), re.UNICODE)))
    if len(tokens) > 64:
        raise ValueError("Query exceeds 64 terms")
    return " AND ".join('"' + token + '"' for token in tokens)
