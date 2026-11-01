import base64
import ctypes
import hashlib
import plistlib
import sys

import pytest
from bibdeskparser import Library

from bibdesk_rag.attachments import resolve_native_reference
from bibdesk_rag.bibdesk import normalize_doi, read_library


def bdsk_value(path, **extra):
    return base64.b64encode(
        plistlib.dumps(
            {"relativePath": str(path), **extra},
            fmt=plistlib.FMT_BINARY,
        )
    ).decode("ascii")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_public_api_fields_macros_paths_groups_and_source_unchanged(tmp_path, monkeypatch):
    relative = tmp_path / "日本語 論文.pdf"
    relative.write_bytes(b"synthetic PDF content")
    absolute = tmp_path / "supplementary methods.pdf"
    absolute.write_bytes(b"synthetic supplementary content")
    shared = tmp_path / "shared.pdf"
    shared.write_bytes(b"shared")
    bib = tmp_path / "refs.bib"
    groups = plistlib.dumps(
        [
            {"group name": "Genetics", "keys": "Example2025"},
        ]
    ).decode()
    bib.write_text(
        r"""@string{journalname = {Genetics and {\'e}volution}}
@article{Example2025,
  title = {Histone {hH3-K4R} and $\Delta$set-1},
  author = {M{\"u}ller, Alice and Smith, Bob},
  editor = {Editor, Ed},
  journal = journalname,
  year = {2025}, volume = {3}, number = {4}, pages = {10--15},
  doi = {https://doi.org/10.1234/ABC},
  abstract = {DNA damage in {Neurospora}},
  keywords = {RecQ, mus-9},
  Bdsk-Url-1 = {https://example.org/paper},
"""
        + f"  Bdsk-File-1 = {{{bdsk_value(relative.name)}}},\n"
        + f"  Bdsk-File-2 = {{{bdsk_value(absolute)}}},\n"
        + f"  Bdsk-File-3 = {{{bdsk_value('missing.pdf')}}},\n"
        + f"  Bdsk-File-4 = {{{bdsk_value(shared.name)}}},\n"
        + "}\n@article{DuplicateDOI, title={Other}, doi={doi:10.1234/abc},\n"
        + f"  Bdsk-File-1 = {{{bdsk_value(shared.name)}}}}}\n"
        + "@comment{BibDesk Static Groups{\n"
        + groups
        + "\n}}\n"
    )
    before = {p: digest(p) for p in (bib, relative, absolute, shared)}

    def forbidden_save(*args, **kwargs):
        pytest.fail("read_library must never call Library.save")

    monkeypatch.setattr(Library, "save", forbidden_save)
    records = read_library(bib)
    assert len(records) == 2
    paper = records[0]
    assert paper.citekey == "Example2025"
    assert paper.title == "Histone hH3-K4R and Δset-1"
    assert paper.author == "Müller, Alice and Smith, Bob"
    assert paper.editor == "Editor, Ed"
    assert paper.journal == "Genetics and évolution"
    assert paper.year == "2025"
    assert paper.volume == "3" and paper.number == "4" and paper.pages == "10–15"
    assert paper.doi == records[1].doi == "10.1234/abc"
    assert paper.groups == ["Genetics"]
    assert paper.url == "https://example.org/paper"
    assert "journalname" not in paper.bibtex.lower()
    assert "Genetics" in paper.bibtex
    assert paper.files[0].path == str(relative)
    assert paper.files[1].path == str(absolute)
    assert paper.files[1].role == "supplementary"
    assert paper.files[2].error
    assert paper.files[3].path == records[1].files[0].path
    assert {p: digest(p) for p in before} == before


@pytest.mark.parametrize(
    "value, expected",
    [
        ("DOI: 10.1234/Example", "10.1234/example"),
        ("https://dx.doi.org/10.1234/ABC%2Fdef", "10.1234/abc/def"),
        ("10.1234/a(1).", "10.1234/a(1)."),
    ],
)
def test_doi_normalization(value, expected):
    assert normalize_doi(value) == expected


@pytest.mark.parametrize(
    "text",
    [
        "@article{X, title={Missing closing brace",
        "@article{X,title={One}}\n@article{X,title={Two}}",
    ],
)
def test_invalid_library_does_not_silently_drop_entries(tmp_path, text):
    bib = tmp_path / "invalid.bib"
    bib.write_text(text)
    with pytest.raises(ValueError):
        read_library(bib)


def test_empty_library_and_plain_export_attachment(tmp_path):
    bib = tmp_path / "empty.bib"
    bib.write_text("% empty library\n")
    assert read_library(bib) == []
    bib.write_text("@article{X,title={A},Bdsk-File-1={missing.pdf}}")
    reference = read_library(bib)[0].files[0]
    assert reference.path == str(tmp_path / "missing.pdf")
    assert reference.error


def test_bad_native_locator_does_not_abort(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{X,title={A},Bdsk-File-1={"
        + bdsk_value(
            "missing.pdf",
            bookmark=b"not a native bookmark",
        )
        + "}}"
    )
    assert read_library(bib)[0].files[0].error


def test_corrupt_library_payload_is_a_clear_error(tmp_path):
    bib = tmp_path / "refs.bib"
    invalid = base64.b64encode(plistlib.dumps(["not a dictionary"])).decode()
    bib.write_text("@article{X,title={Still indexable},Bdsk-File-1={" + invalid + "}}")
    with pytest.raises(ValueError, match="BibDesk parsing failed"):
        read_library(bib)


def test_macro_concatenation_chaining_and_literal_hash(tmp_path):
    bib = tmp_path / "macros.bib"
    bib.write_text(r"""@string{prefix = {Gen}}
@string{middle = prefix # "et"}
@string{whole = middle # {ics}}
@string{alias = whole}
@article{X, title = alias # { and $\Delta$set-1},
  journal = whole, note = {literal # symbol}, year=20 # 25}
""")
    paper = read_library(bib)[0]
    assert paper.title == "Genetics and Δset-1"
    assert paper.journal == "Genetics"
    assert paper.year == "2025"
    assert paper.fields["note"] == "literal # symbol"
    assert "prefix" not in paper.bibtex
    # The export is a self-contained BibTeX record that can be imported alone.
    exported = tmp_path / "exported.bib"
    exported.write_text(paper.bibtex)
    exported_paper = read_library(exported)[0]
    assert exported_paper.title == paper.title
    assert exported_paper.journal == paper.journal


@pytest.mark.parametrize(
    "text",
    [
        "@string{x=y}\n@string{y=x}\n@article{X,title=x # {suffix}}",
        "@article{X,title=unknown # {suffix}}",
    ],
)
def test_invalid_macro_concatenation_is_not_silently_literal(tmp_path, text):
    bib = tmp_path / "macros.bib"
    bib.write_text(text)
    with pytest.raises(ValueError, match="BibTeX macro"):
        read_library(bib)


def test_latex_input_does_not_read_other_files(tmp_path):
    unrelated = tmp_path / "unrelated.tex"
    unrelated.write_text("PRIVATE_SENTINEL")
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{X,title={Evidence},abstract={before \\input{" + str(unrelated) + "} after}}"
    )
    paper = read_library(bib)[0]
    assert "PRIVATE_SENTINEL" not in paper.abstract


def _bookmark(path):
    """Create a native bookmark for a synthetic fixture, never a real library."""
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
        pointer,
        pointer,
        ctypes.c_long,
        ctypes.c_ubyte,
    ]
    cf.CFURLCreateFromFileSystemRepresentation.restype = pointer
    cf.CFURLCreateBookmarkData.argtypes = [
        pointer,
        pointer,
        ctypes.c_ulong,
        pointer,
        pointer,
        pointer,
    ]
    cf.CFURLCreateBookmarkData.restype = pointer
    cf.CFDataGetLength.argtypes = [pointer]
    cf.CFDataGetLength.restype = ctypes.c_long
    cf.CFDataGetBytePtr.argtypes = [pointer]
    cf.CFDataGetBytePtr.restype = pointer
    cf.CFRelease.argtypes = [pointer]
    path_bytes = str(path).encode()
    url = cf.CFURLCreateFromFileSystemRepresentation(None, path_bytes, len(path_bytes), False)
    data = cf.CFURLCreateBookmarkData(None, url, 0, None, None, None)
    try:
        assert data
        return ctypes.string_at(cf.CFDataGetBytePtr(data), cf.CFDataGetLength(data))
    finally:
        if data:
            cf.CFRelease(data)
        cf.CFRelease(url)


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple CoreFoundation only")
def test_macos_bookmark_tracks_moved_file_without_rewriting_library(tmp_path):
    original = tmp_path / "before.pdf"
    original.write_bytes(b"synthetic")
    bookmark = _bookmark(original)
    assert resolve_native_reference(bookmark, None) == original
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{X,title={A},Bdsk-File-1={"
        + bdsk_value(
            original.name,
            bookmark=bookmark,
        )
        + "}}"
    )
    before = digest(bib)
    moved = tmp_path / "renamed 日本語.pdf"
    original.rename(moved)
    reference = read_library(bib)[0].files[0]
    assert reference.path == str(moved)
    assert reference.error is None
    assert digest(bib) == before
