[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# CLI・設定・抽出仕様

初回導入とCodexへの登録は [README](../README.md) を参照してください。このページはv0.3.0以降の対象別オプション体系を説明します。v0.2.x以前から更新する場合は、[旧コマンドからの移行](#旧コマンドからの移行) を確認してください。

## 操作体系と案内

```sh
bibdesk-rag
bibdesk-rag -h
bibdesk-rag -v
bibdesk-rag -e
bibdesk-rag -r
```

引数なしでは版番号・開発者名・説明と主な操作を表示します。端末ではusage・オプションを色分けし、`NO_COLOR`設定時、`TERM=dumb`、パイプやファイル出力では色を付けません。`-h/--help` ではすべてのオプションを含む詳細ヘルプを表示します。`-v/--version` は版番号とソフトウェア引用情報、`-e/--example` は操作例を表示します。`-r/--readme` は同梱マニュアルを端末のページャーで表示し、非TTYまたはページャーがない場合は標準出力へ出します。設定・索引がなくても利用でき、ネットワークへ接続しません。

| 主操作 | 引数 | 用途 |
| --- | --- | --- |
| `--setup` | なし | 対話型初期設定 |
| `-c/--config` | `show`、`path`、`use PATH`、`create [PATH]` | 設定管理 |
| `-i/--index` | `update`、`rebuild`、`status`、`check` | 索引管理 |
| `-p/--paper` | `search QUERY`、`show KEY`、`attachments KEY`、`context QUERY` | 文献情報の取得 |

主操作は1回につき1つです。操作に不要なオプション、操作の併用、引数の過不足は処理を開始する前にエラーにします。検索語やパスに空白を含む場合は引用符で囲みます。

```sh
bibdesk-rag --output manual
bibdesk-rag --output config-template > example.toml
bibdesk-rag --output citation > bibdesk-rag.bib
```

`-o/--output` は同梱資料の出力用です。`citation` は著者をKento Yanagisawa、文献タイプを `@manual` としたBibDeskRAG自体のBibTeX引用情報です。文献のBibTeXは `--paper show KEY --format bibtex` で取得します。ファイルの作成は利用者が指定するシェルのリダイレクトによるもので、出力操作自体はファイルを書きません。

## 対話型セットアップ

```sh
bibdesk-rag --setup
```

別の場所にある既存設定を継続して使う場合は、一度選択します。

```sh
bibdesk-rag --config use "/absolute/path/to/config.toml"
bibdesk-rag --setup
```

標準入力・標準エラー出力が両方とも端末の場合に動作します。新規の既定保存先は設定が `~/.config/bibdesk-rag/config.toml`、索引が `~/.local/share/bibdesk-rag/index.sqlite3` です。

1. 実行環境・保存先を確認し、新規の場合は `.bib` のパスを入力します。`~`、相対パス、引用符やドラッグ＆ドロップ時のシェルエスケープに対応します。入力をシェルで実行せず、文献数・添付数を確認してから設定を作ります。
2. 既存設定では継続・詳細表示・終了を選びます。不正な設定を自動修復せず、強制上書きもしません。
3. 索引がなければ初回作成を提案します。既存索引はそのまま使用するのが既定で、差分更新・全件再構築を明示的に選べます。進捗と文献数・添付数・チャンク数・抽出状態を表示します。
4. Codex CLIがあれば、承認した場合だけMCPを引数なしで登録し、選択中の設定に追従させます。`--temp PATH --setup` の場合だけその設定を固定します。同じ登録を重複追加せず、異なる登録を置き換えません。CLIがない場合は手動接続方法を表示します。
5. 設定とSQLiteの読み取り、MCPサーバーの初期化とツール一覧を確認します。Codexからの実検索は別途必要です。

Ctrl+Cは終了コード130、EOFは終了コード1で中断します。中断した工程と完了した工程を表示し、設定・索引を保持します。通常のセットアップで選択を保存した後は `--setup` で再開できます。`--temp` を付けた場合は同じ `--temp PATH --setup` で再開します。索引書き込みはトランザクションを使います。

非TTYでは入力を読まず、手動操作を標準エラー出力に表示して終了コード1で終了します。自動処理には次の設定作成・索引操作を使ってください。

## ライブラリ登録と索引化

```sh
bibdesk-rag --config create --bib "/absolute/path/to/references.bib"
bibdesk-rag --index update
bibdesk-rag --index status --format json
bibdesk-rag --index check --format json
```

`--config create` は設定を新規作成して次回から使う設定として保存します。既存設定は上書きしません。`--index update` は索引がなければ初回作成、あれば差分更新を行います。

| 用途 | 新規作成時の既定保存先 |
| --- | --- |
| 設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

`.bib` は絶対パスで登録され、添付の相対パスは `.bib` の親ディレクトリが基準です。設定と索引は原本やHomebrewのインストール先から分離します。カスタム設定の作成例です。

```sh
bibdesk-rag --config create "/absolute/path/to/project-settings/config.toml" \
  --bib "/absolute/path/to/project/references.bib" \
  --data-dir "/absolute/path/to/project-data"
bibdesk-rag --index update
```

保存先の `PATH` が最優先で、省略時は `BIBDESK_RAG_CONFIG`、なければ設定用ディレクトリの `config.toml` を使います。保存済みのカスタム選択は、新規作成先の既定値には使いません。`database` は絶対パスで保存されます。複数ライブラリにはそれぞれ別の設定とDBを使用してください。

## 設定の確認と選択

```sh
bibdesk-rag --config show
bibdesk-rag --config show --format json
bibdesk-rag --config path
bibdesk-rag --config use "/absolute/path/to/config.toml"
```

`show` は選択中の設定ファイル、選択理由、解決済みの `bib`・`database`、省略時の既定値を含む全抽出設定を表示します。ライブラリや索引を開かず、ファイルを書きません。`path` は絶対パスだけを表示し、設定がまだない場合も既定の作成先を確認できます。`--format json` ではパスと選択理由を取得できます。

`use PATH` は既存設定を検証し、絶対パスを `active-config.json` に保存します。設定・索引・原本は移動・書き換えせず、索引も作成しません。通常の `--setup` と `--config create` も選択を保存します。保存済み設定が見つからない場合はエラーにし、別ライブラリへ自動的に切り替えません。`--config use PATH` で選び直してください。

設定ファイルの選択順は、`--temp PATH`、`BIBDESK_RAG_CONFIG`、保存済みの選択、設定用ディレクトリの `config.toml` です。従来のmacOS保存先は自動検出しません。設定用ディレクトリは `BIBDESK_RAG_HOME`、`XDG_CONFIG_HOME/bibdesk-rag`、`~/.config/bibdesk-rag` の順です。

```sh
bibdesk-rag --temp "/absolute/path/to/other.toml" --config show
bibdesk-rag --temp "/absolute/path/to/other.toml" --index update
```

`--temp` は今回だけ別の設定を使い、保存済みの選択を変更しません。選択を保存する `--config use/create` とは併用できません。`--temp PATH --setup` で作った設定・索引や、承認したCodex登録は保持されます。一時的なのは設定の選択だけです。

新しい索引の保存先は、`--config create` の `--data-dir`、`BIBDESK_RAG_HOME`、`XDG_DATA_HOME/bibdesk-rag` の順です。それらがなければ既定設定には `~/.local/share/bibdesk-rag`、カスタム設定にはその親ディレクトリを使います。同じディレクトリに複数設定を置く場合は `--data-dir` も分けてください。既存設定の `database` は保持されます。設定ファイル内の相対パスは設定ファイルの親が基準です。

[config.example.toml](../config.example.toml) に抽出値を記載しています。値を変える場合はTOMLを編集します。`BIBDESK_RAG_CONFIG` は保存した選択より優先されます。通常の引数なしMCPは選択に追従します。設定パス付きで登録したMCPはその設定に固定され、CLIの選択では登録を書き換えません。

## 進捗と結果の表示

結果の既定形式は `text` です。ファイル・パイプへ渡す場合も同じ形式です。機械処理には `--format json` を明示してください。`--format bibtex` は `--paper show` 専用です。

`--index update/rebuild` の進捗は標準エラー出力、結果は標準出力です。両方が端末につながり、`TERM=dumb` でない場合に進捗バーを表示します。保存が完了してから100%を表示します。抽出試行数は本文の抽出成功数ではなく、未対応形式や本文なしも含みます。

意味検索が有効な場合、モデル読み込みと索引処理のバーは同じ書式で別々の行に表示します。完了したモデル読み込みの行を残し、その下で索引処理を更新します。

```text
Loading weights [####################] 100% | 199/199
Indexed         [####################] 100% | files 1560/1560, papers 1718/1718
```

| オプション | 表示 |
| --- | --- |
| 指定なし | テキスト結果。索引処理では端末に進捗と短い要約、要確認事項は最大3例 |
| `--format json` | 全件の集計・要確認事項をJSON出力。進捗バーなし |
| `--no-progress` | 索引処理・モデル読み込みの進捗バーを無効化 |
| `--verbose` | 索引処理の警告・要確認事項を標準エラー出力へすべて表示 |

`--verbose` と `--no-progress` は索引の更新・再構築用です。`--format json --verbose` の併用も可能で、警告はJSONに混ざりません。再抽出せずに状態を調べるには `--index status` や `--paper attachments KEY` を使います。

## 検索と出典の取得

```sh
bibdesk-rag --paper search "histone H3K4 UV damage" --top 10 --format json
bibdesk-rag --paper search "RecQ helicase" --scope fulltext
bibdesk-rag --paper search "Neurospora" --scope metadata
bibdesk-rag --paper search "Example2025" --scope metadata
bibdesk-rag --paper search "" --scope metadata --doi "https://doi.org/10.1234/example"
bibdesk-rag --paper search "histone" --scope metadata --year 2025 --author Muller
bibdesk-rag --paper show Example2025 --format bibtex
bibdesk-rag --paper attachments Example2025 --format json
bibdesk-rag --paper search "RecQ" --metadata-query "Neurospora" --top 10
bibdesk-rag --paper search "UV" --scope fulltext --citekey Example2025 --citekey Other2024
bibdesk-rag --paper context "UV-induced mutagenesis" --top 5 --max-chars 10000
```

DOI・citekeyは完全一致を優先します。同じDOIの複数エントリを保持し、FTS入力をSQLやFTS構文として実行しません。意味検索・同義語推論は行いません。既定の `--scope all` は書誌候補で最大100文献を選んで本文を検索し、書誌候補がない場合は本文全体へフォールバックします。本文未取得の書誌情報も返すため `source_type` を確認してください。

`--doi/--author/--year` はmetadata検索専用です。`--metadata-query` は `--scope all` の検索とcontextで本文候補を絞り込み、`--citekey` とは併用できません。本文の `--citekey` は複数指定できます。metadataで完全一致を指定する場合は1件です。操作に適用できない組み合わせはエラーになります。

`--top` は1..100（searchは既定10、contextは5）、`--per-paper` は1..10（既定2）、contextの `--max-chars` は256..100000（既定10000）です。文字数は引用ヘッダと本文を含むcontext全体に適用し、JSONの構造情報は含めません。`unverified`、`truncated`、`budget_exhausted` に不足を示します。少数・0件の結果だけでは関連資料の不在を示せません。

出典はcitekey、DOI、ファイルパス、chunk ID、PDFページ範囲または補足資料のシート・行・ZIPメンバーです。PDFはファイル先頭を1ページとし、1チャンクはページを跨ぎません。CSV/TSVはヘッダを1行目とするレコード番号、XLSXはシート上の行番号です。科学的な主張は原本と照合してください。

## 差分更新

```sh
bibdesk-rag --index update
bibdesk-rag --index update --verify-hashes
bibdesk-rag --index rebuild
```

差分更新はエントリ・添付リンクを同期し、サイズとナノ秒mtimeが同じ添付の再読込を省略します。変更候補だけSHA-256を計算し、内容が同じなら既存chunk IDを再利用します。`--verify-hashes` はサイズ・mtimeが同じファイルも検査します。抽出設定の変更や `rebuild` は再抽出します。文献キー変更は旧・新両方で一意なDOIの場合だけ内部IDを維持します。

同じ正規化済みパスを複数文献が参照しても抽出は1回です。書き込みはトランザクションで行い、致命的エラーでは以前の索引を保持します。個別の欠損・抽出不能ファイルはエラーとして記録し、消えた資料の古い本文は検索対象から除去します。

## 旧コマンドからの移行

| 以前の構文 | 新しい構文 |
| --- | --- |
| `setup` | `--setup` |
| `init` | `--config create` |
| `config show/path/use` | `--config show/path/use` |
| `index` | `--index rebuild` |
| `update` | `--index update` |
| `status` / `doctor` | `--index status` / `--index check` |
| `search` / `context` | `--paper search` / `--paper context` |
| `get KEY` / `attachments KEY` | `--paper show KEY` / `--paper attachments KEY` |
| `--config PATH`（CLIの一時指定） | `--temp PATH` |
| `--json` | `--format json` |

旧構文は移行先を案内するエラーになります。MCPサーバーには既存登録向けの非表示 `--config PATH` 互換引数があり、通常の新規登録は引数なしで選択中の設定に追従し、設定を固定する場合だけ `--temp PATH` を使います。MCPの6ツール名・スキーマは変わりません。

macOSの旧保存先 `~/Library/Application Support/bibdesk-rag/config.toml` は自動検出しません。その場所の設定を引き続き使う場合は、一度選択してください。索引の移動や再作成は不要です。

```sh
bibdesk-rag --config use "$HOME/Library/Application Support/bibdesk-rag/config.toml"
bibdesk-rag --index status
```

新しい既定の設定は `~/.config/bibdesk-rag/config.toml`、索引は `~/.local/share/bibdesk-rag/index.sqlite3` です。新しい既定の場所にある設定は、そのまま使用できます。結果はパイプ出力でも既定でテキストになるため、JSONを読む既存スクリプトには `--format json` を追加してください。

## 抽出と検索の制約

- `--index check`：SQLite/外部キー/FTS整合性と添付エラーを確認。FTS検査のためDBをメモリにコピーします。大規模DBではメモリが必要です。
- 欠損・移動ファイル：まずBibDesk上でリンクを確認してください。公開 `Entry.files` を優先し、既存パスがない場合のみmacOS bookmark/aliasをUI・マウントなしで解決します。現代のbookmark移動追跡は合成データで検証済み。古い実機alias形式は未検証です。
- 画像のみPDF：`no_text` として記録。OCRはありません。暗号化PDF・壊れたPDFは理由を記録し、処理を継続します。
- ZIP：内部一覧を記録し、対応形式のみメモリ内で解析。パス逸脱、symlink、暗号化、サイズ・件数・圧縮率超過を拒否。入れ子ZIPは本文未解析です。XLSX・OOXML・iWorkもコンテナ/XMLの安全性を検査し、展開予算を共有します。iWork内部のIndex.zipは文書形式として解析します。
- DOCX・PPTX・DOC・XLS・TeX・Keynote・Pages・Numbersも対象です。旧DOC/XLSとApple形式は制約を示して部分抽出します。画像・動画は明示的に`excluded`です。[形式別の範囲・出典位置](file-formats.md)を参照してください。
- PDFの読み順・段組・表の再構成精度はpypdfの抽出に依存します。抽出テキストは原本を代替しません。
- 索引は平文のローカルSQLiteです。アプリはファイルを0600で作成します。バックアップやOSのアクセス権は利用者側で管理します。
- 生物学的表記の正規化は検索補助であり、異なる実験条件や変異体が同一であるとは推論しません。

---

<a id="english"></a>

# CLI, configuration and extraction reference

For initial installation and Codex registration, see the [README](../README.md#english). This page describes the operation-based options in v0.3.0 and later. When upgrading from v0.2.x or earlier, see [Migration](#migrating-from-older-commands).

## Operations and guidance

```sh
bibdesk-rag
bibdesk-rag -h
bibdesk-rag -v
bibdesk-rag -e
bibdesk-rag -r
```

No arguments shows the version, author, tagline and operation overview. Usage/options are colored on terminals; `NO_COLOR`, `TERM=dumb` or redirected output disables colors; `-h/--help` shows every option. `-v/--version` prints the version and software citation, and `-e/--example` prints examples. `-r/--readme` displays the bundled manual in a terminal pager, or on standard output without a TTY/pager. These work without configuration, an index or network access.

| Main operation | Arguments | Purpose |
| --- | --- | --- |
| `--setup` | None | Interactive initial setup |
| `-c/--config` | `show`, `path`, `use PATH`, `create [PATH]` | Configuration management |
| `-i/--index` | `update`, `rebuild`, `status`, `check` | Index management |
| `-p/--paper` | `search QUERY`, `show KEY`, `attachments KEY`, `context QUERY` | Paper retrieval |

Use one main operation per invocation. Unrelated options, conflicting operations and missing/extra arguments are rejected before processing. Quote queries and paths containing spaces.

```sh
bibdesk-rag --output manual
bibdesk-rag --output config-template > example.toml
bibdesk-rag --output citation > bibdesk-rag.bib
```

`-o/--output` prints bundled resources. `citation` is the software's BibTeX `@manual` entry attributed to Kento Yanagisawa. For a paper's BibTeX, use `--paper show KEY --format bibtex`. Output itself does not write files; shell redirection is the caller's choice.

## Interactive setup

```sh
bibdesk-rag --setup
```

To keep using an existing configuration elsewhere, select it once:

```sh
bibdesk-rag --config use "/absolute/path/to/config.toml"
bibdesk-rag --setup
```

Both standard input and standard error must be terminals. New defaults are `~/.config/bibdesk-rag/config.toml` for configuration and `~/.local/share/bibdesk-rag/index.sqlite3` for the index.

1. Check the environment and paths; for a new configuration, enter the `.bib` path. `~`, relative paths, quotes and drag-and-drop shell escapes are supported. Input is never executed in a shell. Confirm paper/attachment counts before creating configuration.
2. With existing configuration, choose to continue, inspect details or exit. Invalid configurations are not automatically repaired or forcibly overwritten.
3. Setup offers an initial build if no index exists. Existing indexes default to reuse, with explicit incremental-update/rebuild choices. Progress, paper/attachment/chunk counts and extraction states are shown.
4. If Codex CLI is available, MCP is registered only after approval, normally without arguments to follow the selected configuration. Only `--temp PATH --setup` pins that configuration. Matching registrations are not duplicated; conflicting ones are not replaced. Without the CLI, manual connection details are shown.
5. Check configuration/SQLite readability, MCP initialization and tool discovery. Actual searches from Codex require a separate check.

Ctrl+C exits with code 130; EOF exits with code 1. Setup reports completed/interrupted stages and retains configuration/index data. After ordinary setup saves the selection, resume with `--setup`. When using `--temp`, resume with the same `--temp PATH --setup`. Index writes are transactional.

Without a TTY, setup does not read input; it prints manual operations to standard error and exits with code 1. For automation, use the following configuration/index operations.

## Registering and indexing a library

```sh
bibdesk-rag --config create --bib "/absolute/path/to/references.bib"
bibdesk-rag --index update
bibdesk-rag --index status --format json
bibdesk-rag --index check --format json
```

`--config create` creates a configuration and remembers it for future commands. It never overwrites existing configuration. `--index update` builds an absent index or updates an existing one incrementally.

| Data | New-install default |
| --- | --- |
| Configuration | `~/.config/bibdesk-rag/config.toml` |
| Search index | `~/.local/share/bibdesk-rag/index.sqlite3` |

The `.bib` path is stored as an absolute path. Relative attachment paths resolve from the `.bib` parent directory. Keep configuration/index paths separate from original sources and the Homebrew installation. For a custom configuration:

```sh
bibdesk-rag --config create "/absolute/path/to/project-settings/config.toml" \
  --bib "/absolute/path/to/project/references.bib" \
  --data-dir "/absolute/path/to/project-data"
bibdesk-rag --index update
```

An explicit destination `PATH` takes priority; otherwise use `BIBDESK_RAG_CONFIG`, then `config.toml` in the configuration directory. A saved custom selection does not change the default creation destination. `database` is stored as an absolute path. Use a separate configuration and database per library.

## Inspecting and selecting configuration

```sh
bibdesk-rag --config show
bibdesk-rag --config show --format json
bibdesk-rag --config path
bibdesk-rag --config use "/absolute/path/to/config.toml"
```

`show` displays the selected configuration, selection reason, resolved `bib`/`database` and all extraction options, including defaults for omitted settings. It opens neither the library nor the index and writes nothing. `path` prints only the absolute path, including the default creation destination before a configuration exists. `--format json` also returns the selection reason.

`use PATH` validates existing configuration and saves its absolute path in `active-config.json`. It does not move or rewrite configuration, index or sources, or build an index. Ordinary `--setup` and `--config create` also save the selection. A missing saved configuration produces an error rather than silently switching libraries. Select again with `--config use PATH`.

Selection priority: `--temp PATH`, `BIBDESK_RAG_CONFIG`, saved selection, then the configuration directory's `config.toml`. The former macOS location is not auto-detected. Configuration-directory priority: `BIBDESK_RAG_HOME`, `XDG_CONFIG_HOME/bibdesk-rag`, then `~/.config/bibdesk-rag`.

```sh
bibdesk-rag --temp "/absolute/path/to/other.toml" --config show
bibdesk-rag --temp "/absolute/path/to/other.toml" --index update
```

`--temp` overrides configuration for one invocation without changing the saved selection. It cannot be combined with `--config use/create`, which save a selection. Configuration/index files created by `--temp PATH --setup`, and any approved Codex registration, remain; only selection is temporary.

New index placement uses `--config create --data-dir`, then `BIBDESK_RAG_HOME`, then `XDG_DATA_HOME/bibdesk-rag`. Without these, default configurations use `~/.local/share/bibdesk-rag`; custom configurations use their parent directory. When placing multiple configurations together, give them different `--data-dir` locations. Existing `database` values are retained. Relative TOML paths resolve from the configuration file's parent.

Extraction values are listed in [config.example.toml](../config.example.toml); edit TOML to change them. `BIBDESK_RAG_CONFIG` overrides saved selections. Normal MCP registrations without arguments follow the selection. Registrations with explicit configuration paths remain pinned; CLI selections do not rewrite them.

## Progress and result output

Results default to `text`, including in files/pipes. Specify `--format json` for machine processing. `--format bibtex` is only valid for `--paper show`.

For `--index update/rebuild`, progress goes to standard error and results to standard output. A bar appears when both streams are terminals and `TERM` is not `dumb`. It reaches 100% only after commit. Extraction attempts include unsupported/no-text files and do not equal successful extractions.

When semantic search is enabled, model loading and indexing use matching bars on separate lines. The completed model-loading line remains above the updating index line. JSON, redirected output, `--no-progress` and `--verbose` suppress both bars.

| Option | Output |
| --- | --- |
| None | Text results; terminal indexing shows progress, a short summary and at most three issue examples |
| `--format json` | Complete aggregate/issue report as JSON; no progress bar |
| `--no-progress` | Disable the indexing and model-loading progress bars |
| `--verbose` | All indexing warnings/issues on standard error |

`--verbose` and `--no-progress` apply to update/rebuild. `--format json --verbose` is supported; warnings do not contaminate JSON. Inspect states without re-extraction using `--index status` or `--paper attachments KEY`.

## Searching and retrieving citations

```sh
bibdesk-rag --paper search "histone H3K4 UV damage" --top 10 --format json
bibdesk-rag --paper search "RecQ helicase" --scope fulltext
bibdesk-rag --paper search "Neurospora" --scope metadata
bibdesk-rag --paper search "Example2025" --scope metadata
bibdesk-rag --paper search "" --scope metadata --doi "https://doi.org/10.1234/example"
bibdesk-rag --paper search "histone" --scope metadata --year 2025 --author Muller
bibdesk-rag --paper show Example2025 --format bibtex
bibdesk-rag --paper attachments Example2025 --format json
bibdesk-rag --paper search "RecQ" --metadata-query "Neurospora" --top 10
bibdesk-rag --paper search "UV" --scope fulltext --citekey Example2025 --citekey Other2024
bibdesk-rag --paper context "UV-induced mutagenesis" --top 5 --max-chars 10000
```

Exact DOI/citekey matches take priority. Duplicate DOI entries are retained; FTS input is not executed as SQL or FTS syntax. This keyword mode does not perform semantic inference; optional semantic mode is documented separately. Default `--scope all` selects up to 100 metadata candidates and searches their text; without metadata matches, it falls back to all indexed text. Metadata-only records can also be returned; inspect `source_type`.

`--doi/--author/--year` apply only to metadata search. `--metadata-query` restricts text candidates for all-scope search/context and cannot be combined with `--citekey`. Full-text retrieval accepts repeated citekeys; exact metadata lookup accepts one. Inapplicable combinations fail.

`--top` accepts 1..100 (search default 10, context default 5); `--per-paper` accepts 1..10 (default 2); context `--max-chars` accepts 256..100000 (default 10000). The character budget covers citation headers and text, excluding JSON structure. `unverified`, `truncated` and `budget_exhausted` describe gaps. Few or zero results do not prove relevant literature is absent.

Citations include citekey, DOI, file path, chunk ID, and PDF page range or supplementary sheet/row/ZIP member. PDF pages count from 1 at the file's start; chunks never cross pages. CSV/TSV use record numbers with the header as row 1; XLSX uses worksheet row numbers. Verify scientific claims against original sources.

## Incremental updates

```sh
bibdesk-rag --index update
bibdesk-rag --index update --verify-hashes
bibdesk-rag --index rebuild
```

Updates synchronize entries and attachment links, skipping attachment reads when size and nanosecond mtime match. Only possible changes are SHA-256 hashed; identical content reuses chunk IDs. `--verify-hashes` also checks stat-identical files. Extraction-setting changes and rebuilds force re-extraction. Citekey changes preserve internal IDs only when the DOI is unique in both old and new data.

A normalized path shared by several papers is extracted once. Writes are transactional; fatal errors retain the previous index. Individual missing/unextractable files are recorded as errors, and stale text from disappeared sources is removed from search.

## Migrating from older commands

| Old syntax | New syntax |
| --- | --- |
| `setup` | `--setup` |
| `init` | `--config create` |
| `config show/path/use` | `--config show/path/use` |
| `index` | `--index rebuild` |
| `update` | `--index update` |
| `status` / `doctor` | `--index status` / `--index check` |
| `search` / `context` | `--paper search` / `--paper context` |
| `get KEY` / `attachments KEY` | `--paper show KEY` / `--paper attachments KEY` |
| `--config PATH` (one-time CLI override) | `--temp PATH` |
| `--json` | `--format json` |

Old syntax fails with migration guidance. The MCP server retains a hidden `--config PATH` compatibility argument for existing registrations; normal new registrations omit arguments to follow the selected configuration; use `--temp PATH` only to pin a configuration. The six existing MCP tool names/schemas are unchanged; semantic_search_papers is additive.

The old macOS configuration `~/Library/Application Support/bibdesk-rag/config.toml` is not auto-detected. Select it once to keep using it. No index move or rebuild is needed.

```sh
bibdesk-rag --config use "$HOME/Library/Application Support/bibdesk-rag/config.toml"
bibdesk-rag --index status
```

New defaults are `~/.config/bibdesk-rag/config.toml` and `~/.local/share/bibdesk-rag/index.sqlite3`. Existing configuration at the new default works directly. Since piped results now default to text too, add `--format json` to existing JSON-consuming scripts.

## Extraction and search limitations

- `--index check` checks SQLite, foreign keys, FTS consistency and attachment errors. It copies the database into memory for FTS validation; large databases need memory.
- Missing/moved files: inspect BibDesk links first. Public `Entry.files` paths take priority; only missing paths trigger macOS bookmark/alias resolution without UI or mounting. Modern bookmark move tracking has synthetic-fixture coverage; authentic old alias formats remain unverified.
- Image-only PDFs are recorded as `no_text`; no OCR is performed. Encrypted/damaged PDFs record their reason while processing continues.
- ZIP member lists are recorded; supported members are parsed in memory. Traversal, symlinks, encryption and size/count/ratio excesses are rejected. Nested ZIP text is not parsed. XLSX, OOXML and iWork receive container/XML safety checks and share expansion budgets. Internal iWork Index.zip is parsed as part of the document format.
- DOCX, PPTX, DOC, XLS, TeX, Keynote, Pages and Numbers are also supported. Legacy DOC/XLS and iWork return partial extraction with explicit limitations. Images/videos are explicitly `excluded`. See [format scope and provenance](file-formats.md).
- PDF reading order, columns and table reconstruction depend on pypdf. Extracted text does not replace original sources.
- The index is plaintext local SQLite; files are created with mode 0600. Users manage backups and OS permissions.
- Biological-identifier normalization assists matching; it does not imply different experimental conditions or mutants are equivalent.

## Optional semantic search / 任意の意味検索

Use `--setup` for the semantic/model choice, `--semantic download` for explicit noninteractive acquisition, unified `--index update|rebuild|status|check`, and `--paper search QUERY --mode semantic --top N`. Keyword is still the default; `--mode keyword` makes it explicit. See the [Japanese/English semantic search guide](semantic-search.md) for optional dependencies, single-file SQLite, Homebrew, configuration, offline operation and MCP examples. Embeddings compare title/abstract only and do not generate text.
