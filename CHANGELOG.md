[日本語](#japanese) | [English](#english)

<a id="english"></a>

# Changelog

## [0.5.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.5.0) — 2026-11-14

- Show the version/author introduction and tagline before the no-argument usage overview; color usage/options on terminals, respecting NO_COLOR and TERM=dumb and keeping redirected output plain.
- Set the default per-file limit to 200 MiB, matching the container expansion budget; preserve existing explicit settings on upgrade.
- Add read-only DOCX, PPTX, Word 97–2003 DOC, BIFF XLS, literal TeX and iWork XML/IWA extraction, including linked iWork directory packages. Preserve document/slide/paragraph/object/table/line provenance and explicitly report partial coverage.
- Explicitly exclude images/videos, including ZIP members, without reading media bytes. Share container/IWA expansion budgets and preserve nested document locations.
- Retry newly supported formats and ZIPs on the first update of the extraction revision; retain incremental reuse for other formats. Add pinned olefile/xlrd dependencies and verified source locks.

## [0.4.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.4.1) — 2026-11-09

- Match the model-loading and indexing progress bars in width, characters and label
  alignment; retain the completed loading bar above the indexing bar.
- Keep dependency diagnostics off the bibliography-reading line and fit the displayed
  1,560-file/1,718-paper counts within an 80-column terminal.
- Suppress both bars for JSON, redirected output, `--no-progress` and `--verbose`;
  restore dependency progress settings on completion, failure and interruption.
- Keep runtime dependencies, the index schema and extraction limits unchanged.

## [0.4.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.4.0) — 2026-11-06

- Add optional CPU multilingual title/abstract semantic search with fixed-revision E5,
  explicit model download, offline inference, token-aware splitting and per-paper scores.
- Reuse the existing SQLite embedding tables with schema-1 migration, atomic bibliography/text/vector
  updates, unified `--index` actions, interactive semantic/model setup, `--paper search --mode semantic`, and the
  read-only MCP tool `semantic_search_papers`. Existing keyword/fulltext tools stay compatible.
- Keep pip semantic dependencies optional; include a checksum-locked offline inference wheel set
  in the existing Apple Silicon Homebrew environment. Development uses only Python 3.12.13 `.venv`.

## [0.3.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.3.1) — 2026-11-03

- Register MCP without arguments during ordinary setup so it follows the selected
  configuration, including later `--config use PATH` changes. Keep explicit
  configuration arguments for `--temp PATH --setup` only.
- Align manual registration instructions and bundled documentation in Japanese
  and English. Treat existing pinned registrations as different from following
  the selection; retain them and show manual migration guidance.

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

## [0.5.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.5.0) — 2026-11-14（日本語）

- 引数なしの案内に版番号・開発者名・説明を追加。端末ではusageとオプションを色分けし、NO_COLOR・TERM=dumb・リダイレクト時は色なしで表示。
- 1ファイルの既定上限を200 MiBに変更し、コンテナ展開後の合計上限と統一。アップグレード時は既存設定の明示値を保持。
- DOCX・PPTX・Word 97–2003 DOC・BIFF XLS・TeX原文・iWork XML/IWAを読み取り専用で抽出。リンクされたiWorkディレクトリパッケージ、詳細な出典位置、部分抽出の明示に対応。
- 画像・動画はZIP内部も明示的に対象外。コンテナ/IWAの展開予算を共有し、内部文書の出典を保持。
- 新規対応形式とZIPは最初のupdateで再抽出し、他形式の差分再利用は維持。olefile/xlrdのバージョンと検証済みソースを固定。

## [0.4.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.4.1) — 2026-11-09（日本語）

- モデル読み込みと索引処理のバーの幅・文字・ラベル位置を統一し、完了した読み込みバーの下に索引バーを表示します。
- 依存ライブラリの診断が書誌読み込みの行に重ならないよう改行し、80桁の端末でも1,560添付・1,718文献の件数を最後まで表示します。
- JSON・リダイレクト・`--no-progress`・`--verbose` では両方のバーを抑制。正常終了・失敗・中断時に依存ライブラリの進捗設定を復元します。
- 実行時依存・索引スキーマ・抽出上限の変更はありません。

## [0.4.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.4.0) — 2026-11-06（日本語）

- Title・Abstractだけを対象とするローカル多言語ベクトル検索を追加。固定revisionのE5モデルをCPUで使い、明示的な初回取得後はオフラインで動作します。長い入力はトークン数を確認して分割し、結果を論文単位に集約します。
- 既存SQLiteのembeddingテーブルを再利用し、schema 1から2へトランザクション移行。書誌・本文・ベクトルを `--index update/rebuild/status/check` で統合管理し、差分更新・既存データ保持に対応しました。移行後は旧schema-1専用アプリへ戻せません。
- `--setup` で意味検索の利用とモデル取得を選択できます。CLIの `--mode semantic` と読み取り専用MCPツール `semantic_search_papers` を追加し、従来のキーワード検索・全文検索と検索既定値を維持します。
- pipの推論依存は任意のextraとし、Apple SiliconのHomebrew版では固定済みオフラインwheelを既存環境へ同梱。開発環境はPython 3.12.13の `.venv` に統一しました。

## [0.3.1](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.3.1) — 2026-11-03（日本語）

- 通常のセットアップではMCPを引数なしで登録し、後からの `--config use PATH` を含め選択中の設定に追従させます。`--temp PATH --setup` の場合だけ設定を固定する引数を保持します。
- 日英の手動登録手順・同梱文書も統一。既存のパス固定登録は選択追従と区別し、変更せずに手動移行を案内します。

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
