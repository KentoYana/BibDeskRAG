# Changelog

## [0.3.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.3.0) — 2026-11-03

- Organize CLI operations under `--setup`, `-c/--config`, `-i/--index`, and
  `-p/--paper`. Reject legacy subcommands with migration guidance, conflicting
  operations, and options unrelated to the requested operation.
- Add SpotScanner-style `-h/--help`, `-v/--version`, `-e/--example`,
  `-r/--readme`, and `-o/--output` guidance and bundled manual/configuration
  template/software citation resources. Information works without user state.
- Show brief help when invoked without arguments; retain the complete reference
  under `-h/--help`. Attribute the BibTeX citation to Kento Yanagisawa using
  the `@manual` entry type.
- Use `--format text|json|bibtex` for results, with text as the default even
  through pipes and BibTeX limited to paper records. Replace `--json` with
  `--format json`; keep diagnostics and progress on standard error.
- Add read-only `--config show/path`, and remember selections made by
  `--config use/create` or ordinary `--setup`. `--temp PATH` selects a
  configuration for one invocation and cannot be combined with use/create.
- Keep existing MCP registrations compatible with the hidden server-only
  `--config PATH` spelling; new registrations use `--temp PATH`. Retrieval tool
  names and schemas are unchanged.
- Use `~/.config/bibdesk-rag/config.toml` and
  `~/.local/share/bibdesk-rag/index.sqlite3` as new-install defaults on macOS too;
  retire automatic discovery of the previous macOS Application Support location.
  Existing files stay in place; custom configurations can be selected explicitly.

## [0.2.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.2.0) — 2026-11-02

- Add `bibdesk-rag setup`: an interactive, resumable onboarding wizard using the
  existing configuration, indexing, status and terminal progress functions.
- Preserve existing configuration and indexes; require explicit selection for a
  rebuild and confirmation for optional Codex MCP registration. Detect conflicting
  registrations without replacing them, and show manual connection details when
  the Codex CLI is unavailable.
- Check local MCP initialization and tool discovery separately from registration
  and actual Codex searches; handle interruptions and non-interactive execution.
- Recommend setup in the onboarding guides while retaining manual CLI instructions;
  extend installed-package smoke checks with setup help and non-TTY safety.
- Keep the existing CLI arguments and JSON output, database schema, and runtime
  dependencies unchanged. BibDesk libraries and attachments remain read-only.

## [0.1.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.1) — 2026-11-02

- Single-line terminal progress for indexing and incremental updates, with concise
  completion summaries and bounded parser/attachment diagnostics.
- Preserve complete JSON reports with `--json` or redirected stdout; add
  `--no-progress` and `--verbose` display options without new dependencies.
- Clarify the desktop MCP setup fields and use explicit, separate configuration
  and index paths throughout the onboarding instructions.

## [0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0) — 2026-11-01

- Read-only BibDesk ingestion with native macOS attachment resolution.
- Bounded PDF, CSV/TSV, XLSX and safe ZIP extraction with source provenance.
- SQLite FTS5 metadata/full-text retrieval and transactional incremental updates.
- CLI, staged context retrieval and six read-only stdio MCP tools.
- Setuptools sdist/wheel, local pyenv/pip development, Homebrew Formula generation,
  pinned resources and offline build bundle, CI and release documentation.
- Homebrew installation through `KentoYana/tap/bibdesk-rag` and a step-by-step
  local Codex MCP connection guide.
- Release archive checks for package/version identity, license notices, private
  data exclusion and backend bundle hashes; generated `SHA256SUMS`.
- Installed-package smoke checks for PDF page citations, selected-paper retrieval,
  supplementary CSVs and unchanged source/configuration/index data.
