"""Read OOXML text without Office, relationship fetching, macros or rendering."""

from __future__ import annotations

from pathlib import PurePosixPath
import posixpath
import re
from typing import BinaryIO
import zipfile

from defusedxml.ElementTree import fromstring

from .common import (
    ExpansionBudget, ExtractedChunk, ExtractionOptions, ExtractionResult, append_chunk, split_text,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def xml_part(archive: zipfile.ZipFile, name: str):
    root = fromstring(archive.read(name), forbid_dtd=True, forbid_entities=True,
                      forbid_external=True)
    # ISO Strict uses a different namespace URI for the same text structures.
    replacements = {
        "{http://purl.oclc.org/ooxml/wordprocessingml/main}": W,
        "{http://purl.oclc.org/ooxml/drawingml/main}": A,
        "{http://purl.oclc.org/ooxml/presentationml/main}": P,
        "{http://purl.oclc.org/ooxml/officeDocument/relationships}": R,
    }
    for element in root.iter():
        for original, normalized in replacements.items():
            if element.tag.startswith(original):
                element.tag = normalized + element.tag[len(original):]
            for key in list(element.attrib):
                if key.startswith(original):
                    element.attrib[normalized + key[len(original):]] = element.attrib.pop(key)
    return root


def local_relationships(archive: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    """Resolve only in-container targets. Never interpret a target as a URL."""
    parent, base = posixpath.split(part)
    rels = posixpath.join(parent, "_rels", base + ".rels")
    if rels not in archive.namelist():
        return {}
    result = {}
    for rel in xml_part(archive, rels):
        if rel.get("TargetMode", "Internal") != "Internal":
            continue
        target = rel.get("Target", "")
        if not target or "\\" in target or ":" in target or "\x00" in target:
            raise ValueError("Invalid internal OOXML relationship")
        # A leading slash is an OPC package-root target, never a filesystem path.
        target = posixpath.normpath(target[1:] if target.startswith("/")
                                   else posixpath.join(parent, target))
        if target.startswith("/") or ".." in PurePosixPath(target).parts:
            raise ValueError("OOXML relationship escapes the package")
        identifier = rel.get("Id")
        if not identifier or identifier in result:
            raise ValueError("Ambiguous OOXML relationship identifier")
        result[identifier] = (target, rel.get("Type", "").rsplit("/", 1)[-1])
    return result


def paragraph_text(paragraph, namespace: str) -> str:
    parts = []

    def visit(element):
        if element.tag == namespace + "t":
            parts.append(element.text or "")
        elif element.tag == namespace + "tab":
            parts.append("\t")
        elif element.tag in {namespace + "br", namespace + "cr"}:
            parts.append("\n")
        for child in element:
            if child.tag != namespace + "p":
                visit(child)

    visit(paragraph)
    return "".join(parts)


def extract_office(source: BinaryIO, suffix: str, options: ExtractionOptions,
                   *, budget=None) -> ExtractionResult:
    from .archive import inspect_archive

    chunks = []
    incomplete = False
    try:
        inspect_archive(source, options, budget=budget or ExpansionBudget(options))
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            if suffix == ".docx":
                # Main body first, followed by clearly identified auxiliary stories.
                names = ["word/document.xml"] + sorted(
                    n for n in archive.namelist()
                    if re.fullmatch(r"word/(?:header\d+|footer\d+|footnotes|endnotes|comments)\.xml", n)
                )
                units = [(name, None, W) for name in names]
            else:
                presentation = xml_part(archive, "ppt/presentation.xml")
                rels = local_relationships(archive, "ppt/presentation.xml")
                units = []
                for number, slide in enumerate(presentation.findall(f"{P}sldIdLst/{P}sldId"), 1):
                    target, kind = rels[slide.get(R + "id")]
                    if kind != "slide":
                        raise ValueError("Presentation relationship is not a slide")
                    units.append((target, number, A))
                    for note, note_kind in local_relationships(archive, target).values():
                        if note_kind == "notesSlide":
                            units.append((note, number, A))
            for name, slide_number, namespace in units:
                root = xml_part(archive, name)
                if any(e.tag == W + "altChunk" for e in root.iter()):
                    incomplete = True
                for number, paragraph in enumerate(root.iter(namespace + "p"), 1):
                    # A parent paragraph can contain a text box with its own paragraphs.
                    # Exclude nested paragraphs here to avoid duplicated text.
                    text = paragraph_text(paragraph, namespace)
                    for part in split_text(text, options):
                        append_chunk(chunks, ExtractedChunk(
                            part, suffix[1:], page_start=slide_number, page_end=slide_number,
                            member_path=f"{name}#paragraph={number}",
                        ), options)
        return ExtractionResult(chunks, ("partial" if incomplete else "ok") if chunks else "no_text",
                                "Embedded altChunk content is not parsed" if incomplete
                                else (None if chunks else "No document text"))
    except Exception as exc:
        return ExtractionResult(chunks, "partial" if chunks else "error",
                                f"{type(exc).__name__}: {exc}")
