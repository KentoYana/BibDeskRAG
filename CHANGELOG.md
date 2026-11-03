[日本語](#japanese) | [English](#english)

<a id="english"></a>

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

---

<a id="japanese"></a>

# 変更履歴

## [0.3.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.3.0) — 2026-11-03（日本語）

- CLI操作を `--setup`、`-c/--config`、`-i/--index`、`-p/--paper` に整理。旧サブコマンドには移行案内を返し、競合操作と無関係なオプションを拒否します。
- SpotScanner形式の `-h/--help`、`-v/--version`、`-e/--example`、`-r/--readme`、`-o/--output` と、同梱マニュアル・設定テンプレート・ソフトウェア引用情報を追加。利用者データなしで案内を利用できます。
- 引数なしでは短縮ヘルプ、`-h/--help` では全オプションを表示。BibTeX引用はKento Yanagisawa著の `@manual` 形式です。
- 結果形式を `--format text|json|bibtex` に整理し、パイプでも既定はtext、bibtexは文献レコード専用としました。`--json` を `--format json` に置き換え、診断・進捗は標準エラー出力に保持します。
- 読み取り専用の `--config show/path` を追加し、`--config use/create` と通常の `--setup` の選択を記憶します。`--temp PATH` は1回だけの設定選択で、use/createと併用できません。
- 既存MCP登録向けにサーバー専用の非表示 `--config PATH` 互換引数を保持。新規登録は `--temp PATH` を使い、検索ツール名・スキーマは維持します。
- macOSも新規既定を `~/.config/bibdesk-rag/config.toml` と `~/.local/share/bibdesk-rag/index.sqlite3` に統一。旧Application Supportの自動検出を廃止し、既存ファイルは保持、カスタム設定は明示選択します。

## [0.2.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.2.0) — 2026-11-02（日本語）

- 既存の設定・索引・状態・端末進捗処理を使う、中断再開可能な対話型 `bibdesk-rag setup` を追加。
- 既存設定・索引を保持し、再構築は明示選択、任意のCodex MCP登録は確認を要求。競合登録を置換せず検出し、Codex CLIがなければ手動接続情報を表示します。
- ローカルMCP初期化・ツール一覧を、登録・Codex実検索と分けて確認し、中断と非対話実行に対応。
- 手動CLI手順を残して導入ガイドではsetupを推奨。導入済みパッケージのsmokeにsetupヘルプと非TTY安全性を追加。
- 既存CLI引数・JSON出力・DBスキーマ・実行時依存を維持。ライブラリと添付は読み取り専用です。

## [0.1.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.1) — 2026-11-02（日本語）

- 索引作成・差分更新に端末1行進捗、短い完了要約、件数制限付きパーサー・添付診断を追加。
- `--json` または標準出力リダイレクトによる完全なJSON報告を保持し、依存追加なしで `--no-progress` と `--verbose` を追加。
- デスクトップMCP入力欄を明確化し、導入手順全体で設定・索引に別の明示パスを使用。

## [0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0) — 2026-11-01（日本語）

- macOSネイティブ添付解決付きの読み取り専用BibDesk取込。
- 出典付きで上限を設けたPDF、CSV/TSV、XLSX、安全なZIP抽出。
- SQLite FTS5の書誌・本文検索とトランザクション型差分更新。
- CLI、段階的context取得、6つの読み取り専用stdio MCPツール。
- setuptools sdist/wheel、ローカルpyenv/pip開発、Homebrew Formula生成、固定resourceとオフラインビルドbundle、CIと配布文書。
- `KentoYana/tap/bibdesk-rag` からのHomebrew導入と、ローカルCodex MCPの接続手順。
- パッケージ・版の一致、ライセンス、個人データ除外、backendハッシュの配布アーカイブ検査と `SHA256SUMS` 生成。
- PDFページ引用、選択文献取得、補足CSV、原本・設定・索引不変の導入済みパッケージsmoke検査。
