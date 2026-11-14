# Compatibility and index upgrades

This contract describes v0.5.1. The first stable
v1.0 release remains subject to the release gates below.

## Public interfaces

- CLI operations use the option syntax introduced in v0.3.0. Former positional
  subcommands are rejected with migration guidance. Human text is for people;
  integrations should request JSON. Information/help operations need no user state.
- Configuration selection is explicit `--temp PATH`, then
  `BIBDESK_RAG_CONFIG`, then the saved selection, then the default config.
  An invalid explicit selection is an error, never a reason to silently fall back.
  `--config use/create` changes the saved selection; `--temp` does not.
- MCP is stdio JSON-RPC, tools only, read-only. Existing tool names and argument
  bounds remain supported. Protocols 2025-06-18, 2025-03-26 and 2024-11-05 are
  negotiated by initialization. The hidden server-only `--config PATH` spelling
  remains compatible; new registrations use no arguments or `--temp PATH`.
- JSON and MCP may gain fields. Consumers must ignore unknown result fields.
  Removed/renamed fields, changed meanings, tightened accepted inputs, or changed
  defaults that alter existing operations require migration documentation.
  Before v1.0 these changes require an explicit minor-version migration note;
  from v1.0 they require a major release, with deprecated interfaces documented
  for at least one stable minor release before removal.
- MCP tool failures keep `isError=true` and the existing textual `error`.
  Binding failures additionally provide `error_code`; CLI stderr includes the
  same bracketed code. Codes are `library_mismatch`,
  `library_identity_missing`, and `index_incomplete`. Other diagnostic text
  is descriptive and should not be parsed as a stable code.
- Context `truncated` includes both source truncation and budget truncation.
  `source_truncated` and `budget_truncated` identify the cause per result;
  `budget_exhausted` only reports insufficient total context space.

## Library identity and recovery

All production SQLite entry points compare the stored canonical bibliography
path with the selected configuration. Ordinary source edits keep that identity;
equal content at a different path does not. Read operations hold one SQLite
snapshot through identity checking and retrieval. Context assembly also holds a
snapshot when called directly with SQLiteSearch, without ending an existing
caller transaction.

Writers inspect existing databases read-only before opening for writes or
changing permissions, then recheck under a write transaction. A new/zero-byte
database or an initialized, empty index without settings can resume its first
build. A populated index missing its binding cannot be adopted automatically.
An empty bound index without a completed build can be updated, but cannot be
queried as if it were complete.

After moving or renaming a bibliography, retain the old database for inspection.
Explicitly create a new configuration with the moved bibliography and a fresh
data directory:

```sh
bibdesk-rag --config create /absolute/new-config.toml --bib /absolute/moved.bib --data-dir /absolute/new-index-directory
bibdesk-rag --temp /absolute/new-config.toml --index update
```

This is the supported explicit reassociation procedure: rebuild derived data in
a new database, then select the new configuration. Do not manually replace
`settings.bib_path`, reuse the old database path, or alter attachment references.
If a move invalidated relative attachment paths, resolve that separately in
BibDesk. This application never rewrites the bibliography.

## Processing versions

- Schema 1 remains readable; writes migrate schema 1 to 2 transactionally.
  Schema migration, metadata, chunks and vectors share one commit.
  A schema-1-only application cannot read the resulting schema-2 index.
  Keep a closed-database backup when a reversible downgrade is needed.
- `settings.extraction_versions` stores per-format parser/policy versions.
  Changes to parsing, chunking, provenance, or a dependency that changes output
  must bump affected entries in `extractors/formats.py`. ZIP is retried whenever
  any member parser version changes. Unchanged other formats are reused.
  Whole-extractor changes bump every affected format.
- `LEGACY_EXTRACTION_VERSIONS` is the frozen v0.5.0 baseline and must not be
  edited to match future parser versions. Pre-versioned indexes use this
  baseline; the prior office/iWork revision still controls first-time retries
  for newly supported formats and ZIPs.
- `settings.normalization_revision` versions lexical normalization. Bump
  `normalization.NORMALIZATION_REVISION` for changes to matching normalization.
  Missing/changed versions refresh paper search fields, chunk search fields and
  their FTS entries in the transaction, retaining raw evidence and chunk IDs.
  They do not force unchanged attachment parsing or semantic model downloads.
  Semantic preprocessing has its separate model signature/content hashes.
- `rebuild` refreshes metadata search fields even when source fingerprints are
  equal. Unsupported future schemas and unrelated databases are refused.
  Unexpected failures/interruptions roll back; ordinary per-attachment extraction
  failures retain the existing documented error/partial handling.

## Release gates and evidence

The package workflow runs on PRs and tags. It builds/installs wheel and sdist,
executes package smoke, and runs the pinned validation-only MCP SDK against both
installed packages. All seven tools are exercised; semantic search is tested
through its disabled error without downloading a model. Fake-backend semantic
success and model-unavailable cases remain in the unit tests. This is not a
claim of real-model SDK interoperability in hosted CI.

`check_release.py` compares pyproject, archive metadata and literal runtime
versions without executing archive code; tag builds additionally require an exact
`v<version>` tag. SDK validation compares installed metadata, runtime, CLI and
MCP serverInfo versions and checks response bounds, argument errors and hashes.

`requirements-upgrade-baseline.txt` pins the actual v0.5.0 wheel URL and SHA-256.
The workflow installs that release in a separate environment and validates its
generated index with the installed candidate wheel and sdist. It checks reads
before update, legacy MCP arguments/protocol, logical-data retention, unchanged
attachment reuse, source/configuration/selection hashes, and a subsequent actual
attachment change. Advance the baseline only after the next release exists.
Synthetic schema-1 migration and rollback tests cover schema upgrades separately.

Before publishing v1.0, require successful hosted CI for the candidate commit,
review migration notes and changed dependencies/licenses, and compare the
published artifacts with the tested SHA256SUMS. Those publication-time gates
cannot be marked complete solely by a local run.

| Environment / interface | Evidence / status |
| --- | --- |
| macOS arm64 / pyenv Python 3.14.10 | Sole local development/validation interpreter; see [current validation](python314-validation.md) and [earlier P0 tests](p0-validation.md) |
| Linux/macOS × Python 3.11–3.14 | [Test workflow](../.github/workflows/test.yml); current hosted run still required |
| macOS Homebrew / pinned Python | [Existing validation](homebrew-validation.md); P0 changes still need a new Homebrew/hosted run |
| Intel Mac hardware | Not locally verified; no hardware claim follows from the CI OS name |
| Official MCP SDK 2.3.0 | [Validation tool](../tools/validate_mcp_sdk.py), separate pinned environment |
| Actual Codex client | [Earlier connection evidence](mcp-validation.md), [seven-tool evidence](semantic-validation.md); current P0 build not retested in a live user session |
| BibDesk references / attachment formats | [Format support and partial-coverage limits](file-formats.md), generated fixtures only for this change |
| OCR / remote APIs / automatic model downloads | Outside the ingestion/retrieval contract |

## 日本語

ライブラリ照合・contextの読み取りスナップショット・抽出/正規化の版管理と
正式版間の更新検証を追加しました。原本BibTeX、添付、既存の添付参照は変更しません。
通常の編集は同じライブラリとして扱い、移動・改名や内容が同じ別パスは自動採用しません。
移動時は上記の手順で新しい設定と別の索引ディレクトリを明示的に作り、
派生索引だけを再作成します。識別情報を失った既存索引も保持して調査します。

既存のCLI・7つのMCPツール・設定優先順位を維持し、JSONの追加フィールドは
読み飛ばせる契約とします。contextは原文抜粋の短縮と全体の文字数不足を区別します。
方式変更は対象形式の版または正規化版を更新し、必要な派生データだけを
トランザクション内で更新します。元の抽出文・出典・正常な差分再利用を保持します。

SDKは検証専用環境に固定し、意味検索は無効時の応答を確認します。
実モデルの品質・性能や現行候補の実Codex接続を検証済みとはしません。
v1.0公開前には現行コミットのホストCI、Homebrew検証、実配布物のSHA照合が必要です。
