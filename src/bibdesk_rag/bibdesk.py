"""Read BibDesk through its public API, without ever saving a library."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote
import warnings

from bibdeskparser import Library
import bibtexparser
from pylatexenc.latex2text import LatexNodes2Text

from .attachments import AttachmentReference, resolve_attachments


@dataclass
class PaperRecord:
    citekey: str
    entry_type: str = ""
    title: str = ""
    author: str = ""
    editor: str = ""
    year: str = ""
    journal: str = ""
    booktitle: str = ""
    volume: str = ""
    number: str = ""
    pages: str = ""
    doi: str = ""
    abstract: str = ""
    keywords: str = ""
    groups: list[str] = field(default_factory=list)
    url: str = ""
    bibtex: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    files: list[AttachmentReference] = field(default_factory=list)


def normalize_doi(value: str) -> str:
    """Normalize a DOI identifier, preserving significant suffix punctuation."""
    value = unicodedata.normalize("NFKC", str(value)).strip()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value, flags=re.I)
    return unquote(value).strip().casefold()


def _unicode_text(value: str) -> str:
    # Entry already handles BibDesk accent escapes. This also handles math
    # commands (e.g. $\Delta$), font commands and case-protection braces.
    text = LatexNodes2Text().latex_to_text(str(value))
    return unicodedata.normalize("NFKC", text).strip()


def _expression_parts(expression: str) -> list[str]:
    """Split BibTeX concatenation only outside literal strings and braces."""
    parts, start, depth, quoted, escaped = [], 0, 0, False, False
    for index, character in enumerate(expression):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
        elif character == '"' and depth == 0:
            quoted = not quoted
        elif not quoted and character == "{":
            depth += 1
        elif not quoted and character == "}":
            depth -= 1
        elif character == "#" and not quoted and depth == 0:
            parts.append(expression[start:index].strip())
            start = index + 1
    parts.append(expression[start:].strip())
    return parts


def _macro_extensions(path: Path) -> dict[str, dict[str, str]]:
    """Fill the upstream 0.8.1 gap for concatenated/chained @string values.

    The public BibDesk API supplies all normal values. A second, raw *public*
    bibtexparser view is used solely for expressions that upstream exports as
    literal text. This evaluator never executes TeX or writes either library.
    """
    raw = bibtexparser.parse_string(path.read_text(encoding="utf-8"), parse_stack=[])
    macros = {item.key.casefold(): item.value for item in raw.strings}
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    for month in months:
        macros.setdefault(month[:3].casefold(), "{" + month + "}")

    def enclosed(term):
        return len(term) >= 2 and (term[0], term[-1]) in {("{", "}"), ('"', '"')}

    def needs_extension(expression, seen=()):
        parts = _expression_parts(expression)
        if len(parts) > 1:
            return True
        term = parts[0]
        if enclosed(term) or term.isdecimal():
            return False
        key = term.casefold()
        if key in seen:
            raise ValueError(f"Cyclic BibTeX macro: {key}")
        if len(seen) >= 32:
            raise ValueError("BibTeX macro nesting exceeds 32 levels")
        if key not in macros:
            return False
        definition = str(macros[key]).strip()
        return not enclosed(definition) or needs_extension(definition, (*seen, key))

    def expand(expression, seen=()):
        values = []
        for term in _expression_parts(expression):
            if enclosed(term):
                value = term[1:-1]
            elif term.isdecimal():
                value = term
            else:
                key = term.casefold()
                if key in seen or len(seen) >= 32:
                    raise ValueError(f"Cyclic or excessively nested BibTeX macro: {key}")
                if key not in macros:
                    raise ValueError(f"Undefined BibTeX macro in concatenation: {term}")
                value = expand(str(macros[key]), (*seen, key))
            values.append(value)
            if sum(map(len, values)) > 1_000_000:
                raise ValueError("Expanded BibTeX field exceeds 1000000 characters")
        return "".join(values)

    overrides = {}
    for entry in raw.entries:
        fields = {}
        for item in entry.fields:
            if item.key.lower().startswith("bdsk-"):
                continue
            if needs_extension(str(item.value)):
                fields[item.key.lower()] = expand(str(item.value))
        if fields:
            overrides[entry.key] = fields
    return overrides


def read_library(path: Path) -> list[PaperRecord]:
    """Return normalized records and read-only attachment references.

    Duplicate keys or parse failures abort before the index can delete records.
    Duplicate DOIs remain separate records. Export is to a string only, with
    macros expanded and the stored entry type preserved.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"BibDesk library does not exist: {path}")
    # The underlying parser otherwise recovers malformed entries with warnings.
    # Silent recovery is unsuitable for a snapshot that drives deletions.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            library = Library(path)
        except (ValueError, TypeError, AttributeError, IndexError) as exc:
            raise ValueError(f"BibDesk parsing failed: {exc}") from exc
    if library.duplicate_keys:
        raise ValueError(f"duplicate citation keys: {library.duplicate_keys}")
    for warning in caught:
        message = str(warning.message)
        if any(
            part in message.lower()
            for part in (
                "unparseable",
                "failed to parse",
                "could not be parsed",
            )
        ):
            raise ValueError(f"BibDesk parsing failed: {message}")
        warnings.warn(message, warning.category, stacklevel=2)
    macro_extensions = _macro_extensions(path)
    records = []
    for citekey in library:
        entry = library[citekey]
        exported = library.export(
            citekey,
            unicode=True,
            expand_strings=True,
            fields=list(entry),
            preprint="stored",
            marker=False,
        )
        parsed = bibtexparser.parse_string(exported)
        if parsed.failed_blocks or len(parsed.entries) != 1:
            raise ValueError(f"could not normalize BibDesk entry {citekey!r}")
        fields = {
            name.lower(): (
                str(item.value).strip()
                if name.lower() in {"doi", "url", "eprint"}
                else _unicode_text(item.value)
            )
            for name, item in parsed.entries[0].fields_dict.items()
            if not name.lower().startswith("bdsk-")
        }
        extensions = macro_extensions.get(citekey, {})
        for name, value in extensions.items():
            fields[name] = (
                value.strip() if name in {"doi", "url", "eprint"} else _unicode_text(value)
            )
        bibtex = library.export(
            citekey,
            unicode=False,
            expand_strings=True,
            fields=list(entry),
            preprint="stored",
            marker=False,
        )
        if extensions:
            export_library = bibtexparser.parse_string(bibtex)
            for item in export_library.entries[0].fields:
                if item.key.lower() in extensions:
                    item.value = extensions[item.key.lower()]
            bibtex = bibtexparser.write_string(export_library)
        record = PaperRecord(
            citekey=citekey,
            entry_type=entry.entry_type,
            **{
                name: fields.get(name, "")
                for name in (
                    "title",
                    "author",
                    "editor",
                    "year",
                    "journal",
                    "booktitle",
                    "volume",
                    "number",
                    "abstract",
                    "keywords",
                )
            },
            pages=fields.get("pages", "")
            or fields.get("eid", "")
            or fields.get("article-number", ""),
            doi=normalize_doi(fields.get("doi", "")),
            groups=[_unicode_text(name) for name in entry.groups],
            url=fields.get("url", "") or next(iter(entry.urls), ""),
            bibtex=bibtex,
            fields=fields,
            files=resolve_attachments(entry, path),
        )
        records.append(record)
    return records
