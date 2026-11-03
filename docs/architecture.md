# Architecture

The only authoritative data is the user-selected BibDesk library and its explicitly linked attachments. The application never saves a `bibdeskparser.Library`, resolves online metadata, evaluates spreadsheet formulas, executes document instructions, or downloads an embedding model.

## Data flow

`Library / Entry.files → normalized PaperRecord → transactional indexer → SQLite → SQLiteSearch → CLI / bounded context / read-only MCP`

The read adapter uses BibDeskParser's public interfaces for bibliography, groups and attachments. The one isolated compatibility bridge obtains native bookmark/alias bytes from an already parsed entry when its public path is missing. Apple's native resolution disables UI and volume mounting. It never updates the library.

## Storage

- `papers`: stable internal integer primary key; exact case-sensitive unique citekey; normalized DOI (not unique); normalized metadata; original exported BibTeX; a fingerprint; normalized FTS fields.
- `attachments`: one resolved path per record; type, size, nanosecond mtime, SHA-256, extraction status, error and ZIP member manifest.
- `paper_attachments`: many-to-many association with original locator and per-paper role. Shared source paths share chunks.
- `chunks`: stable ID until re-extraction; attachment ID; source type; page start/end, sheet and row range, archive member; original extracted text; separate normalized search text; chunk order.
- `papers_fts`, `chunks_fts`: independent FTS5 external-content indexes updated by insert/delete/update triggers in the same transaction as their source rows.
- `settings`: schema-independent library hash, path, extraction options and last successful index timestamp.
- `embedding_models`, `embeddings`: optional model name/version/dimensions/config, chunk ID and source hash. A future backend must key vectors by model and source content, and must never auto-send text externally. No current code writes these tables.

`PRAGMA application_id` (`0x42524147`, ASCII `BRAG`) identifies an application-owned index, and `PRAGMA user_version` guards schema compatibility. Existing unrelated databases are inspected read-only and refused before opening for writes or changing permissions. Schema initialization is transactional. Foreign keys cascade deletions into links/chunks/embedding rows. The indexer holds one immediate write transaction per update, so readers see the last committed state. Search/MCP use `mode=ro` and `query_only`. Doctor performs the FTS integrity INSERT only on an in-memory backup.

## Incremental semantics

The bibliography is re-read on update (usually small relative to attachments). Metadata fingerprints avoid unnecessary writes. Identical size/mtime skips opening attachments; changed stat triggers SHA-256; identical content reuses chunks. `--verify-hashes` overrides the stat shortcut, and `--index rebuild` or extraction-option changes force re-extraction. Index errors for individual sources clear stale chunks and remain visible; unexpected transaction errors roll back the snapshot. Source changes detected during parse/extraction abort the update.

An unambiguous old/new DOI allows a citation-key rename to preserve the paper ID. Duplicate DOI entries are never merged. Distinct path copies of identical content remain distinct attachments; the required common-path many-to-many sharing is deduplicated.

## Retrieval semantics

FTS expressions consist only of quoted AND terms. Unicode NFKC/case folding, dash normalization and compact identifier tokens handle `hH3-K4R`, `Δset-1`, `mus-9` and `RecQ`. Normalized text is used only for matching, while evidence is verbatim extracted text. Exact DOI/citekey queries do not depend on FTS ranking.

Metadata uses weighted BM25. Search summaries bound text fields (including 4,000-character abstracts) and explicitly report shortened fields; exact citekeys, DOIs and source paths are preserved. Full text uses BM25 and streams ranked candidates while enforcing a per-paper limit, avoiding a fixed candidate window monopolized by one paper. Snippets retain verbatim source characters, including numerical ranges and Greek identifiers. Default all-scope retrieval selects metadata candidates then searches their attachments. Explicit `metadata_query` is a strict first-stage constraint; no candidate means no evidence. Fulltext scope searches all indexed attachments unless citekeys restrict it.

The context builder counts citation headers and delimiters in the character budget. It returns evidence and unverified limitations separately. These labels are an instruction boundary, not a claim that prompt injection can be made impossible in an external LLM. The program itself never executes any retrieved content.

## Resource and format limits

PDF pages never cross chunk boundaries. CSV/TSV use logical record numbers, XLSX uses sheet coordinates, and ZIP preserves member paths without extracting to disk. ZIP and XLSX preflight rejects absolute/traversal paths, symlinks, ambiguous duplicate member paths, encrypted entries and excessive member counts/expanded bytes/ratios. An outer ZIP and its XLSX members share an aggregate expansion budget. XLSX XML is checked with defusedxml. Nested ZIP extraction is intentionally disabled.

The configured byte and chunk limits bound ordinary ingestion. pypdf still parses individual page content in-process; this is not an OS sandbox for adversarial parser CPU/memory consumption. A future worker-process resource limiter is a separate hardening improvement, as is OCR.

## Packaging

PEP 621 metadata, setuptools, sdist and wheel are independent from pyenv. Development uses the local pinned interpreter and pip. Homebrew uses its own Python virtualenv and checksum-pinned resources. Data paths are user-owned, outside the installation. The checked-in Formula cannot represent a release until actual immutable source/bundle URLs and hashes are supplied.
