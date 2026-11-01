# Validation record

Date: 2026-11-01 (Asia/Tokyo). Machine: Apple Silicon macOS. Application version: 0.1.0.

Phases 1–3 below record the initial generated-fixture validation. The later
read-only real-library and Codex checks are recorded separately under
[Subsequent Codex desktop verification](mcp-validation.md#subsequent-codex-desktop-verification).
Publication statements in those phases describe the pre-release validation;
see the [v0.1.0 release](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0)
for the public distribution.

## Phase 1: ingestion, indexing and CLI

The full suite passed **115 tests** on the project-local pyenv Python **3.12.13** and on
an independent venv created from Homebrew Python **3.14.10**. The latter used the built
wheel, not an editable source installation. Ruff and `pip check` passed.

Coverage includes BibDesk fields, LaTeX, string macros and concatenation, groups,
multiple attachments, relative/absolute/Japanese paths, missing sources, DOI
normalization and duplicates, modern macOS bookmarks after a file rename, PDF pages,
supplementary PDFs, CSV/TSV/XLSX rows and cells, formula preservation, ZIP/XLSX safety,
BM25 ranking, per-paper limits and biological identifier normalization.

Incremental tests assert that unchanged attachments are neither rehashed nor
re-extracted; mtime-only changes hash without extraction; content changes re-extract;
source deletion removes stale hits; unambiguous DOI renames preserve internal IDs;
ambiguous DOI matches remain separate. Tests cover transaction rollback, cascade
removal, FTS integrity, read-only SQLite connections, output/source collisions,
hard links/SQLite sidecars, refusing failed attachment diagnostic paths, and refusing unrelated databases without changing their
bytes or permissions.

Synthetic source SHA-256 values were checked before and after indexing. A network-denial
test exercises library ingestion, extraction, search and context construction with
socket connection and DNS entry points blocked. No real BibDesk library was registered,
modified or used as a fixture. No home-directory scan was performed.

## Phase 2: context and MCP

Bounded contexts preserve citation/file/page/sheet/row/chunk fields and report omitted
or unverified evidence. Snippets retain literal source values, including `10-15` and
`Δset-1`; only the search index is normalized. Query text is escaped into literal FTS
terms rather than interpreted as query syntax.

The official MCP Python SDK **2.3.0** completed a real stdio initialize handshake and
calls to all six tools. Source and index hashes stayed unchanged. The Codex CLI
recognized an ephemeral stdio server configuration without altering user settings.
This is not a claim that an actual Codex model conversation invoked the tools.
Details and a reproducible client are in [mcp-validation.md](mcp-validation.md).

## Phase 3: packages and distribution

- `python -m build`: sdist and wheel generated with pinned setuptools/wheel.
- Editable installation with pip in the local pyenv venv: passed.
- Normal wheel installation into a clean Homebrew Python 3.14 venv: passed; full
  115-test suite, dependency consistency and installed CLI/MCP smoke passed.
- Normal sdist installation into a separate Python 3.12 venv: passed; installed CLI/MCP
  smoke and dependency consistency passed.
- Homebrew local-tap source installation, `brew style`, `brew audit --strict`, and
  substantive `brew test`: passed. CLI/MCP also passed with `PATH=/usr/bin:/bin`,
  where pyenv is unavailable. The real revision upgrade and exact user-data hash
  comparison are recorded in [homebrew-validation.md](homebrew-validation.md).
- Final sdist contents were checked for required source/docs and absence of user
  libraries/extracted data; all 17 final wheel modules byte-match the tested
  Python 3.14 installation.

The repository's Formula remains an explicitly disabled unpublished template. The
usable validation Formula refers only to real local archives and their SHA-256 values.
No GitHub push, release publication, remote tap creation, or PyPI upload was performed.

## Remaining validation boundaries

- The initial automated tests used generated data only. Later real-library access
  and actual Codex tool calls are documented separately in the MCP validation record.
- Old native alias records are supported through Apple's conversion API but have no
  authentic legacy fixture; modern bookmark moved-file resolution was exercised.
- Intel backend wheels are included, but an Intel Mac was not available for execution.
- Python 3.11/3.13 and Linux are configured in CI; those CI runs have not run locally.
- Public Release/tap URL availability, `brew audit --online`, and remote CI results
  depend on later authorized publication.
- OCR, embeddings, semantic/hybrid search and advanced figures/tables are future work.
  The interface and embedding model/version/dimension schema are present.
