[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# BibDesk RAG

BibDeskで管理する文献を、Codexから検索・参照するためのローカルツールです。書誌情報で候補を絞り、PDFや補足資料の短い抜粋を、citekey・DOI・ファイルの場所・PDFページ番号とともに取得できます。

BibDeskの `.bib` と添付ファイルを読み取り専用で扱い、検索用の索引を別の場所に作ります。対象は登録した1つのライブラリと、そのライブラリにリンクされたファイルです。ライブラリの書き換えや添付ファイルの移動は行いません。

本体は [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG)、Homebrew Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap) で管理しています。[v0.5.1のRelease](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.5.1) にはソース配布・wheel・Homebrew用ビルド依存bundleと `SHA256SUMS` を掲載しています。ソースから利用する場合は [開発とソースからの利用](#開発とソースからの利用) を参照してください。

以下はv0.3.0以降の使い方です。v0.2.x以前から更新する場合は、CLIの構文変更（例：`update` → `--index update`、`--json` → `--format json`）と旧macOS保存先の自動検出廃止を確認してください。既存の設定・索引は移動・削除せず、必要に応じて `--config use PATH` で選択できます。[旧コマンドからの移行](docs/usage.md#旧コマンドからの移行)

## CLIの入口

```sh
bibdesk-rag                     # 短縮ヘルプ
bibdesk-rag -h                  # 詳細ヘルプ
bibdesk-rag -v                  # バージョンとソフトウェア引用情報
bibdesk-rag -e                  # よく使う操作例
bibdesk-rag -r                  # 同梱マニュアル
bibdesk-rag --config show       # 設定の確認
bibdesk-rag --index update      # 索引の初回作成・差分更新
bibdesk-rag --paper search "RecQ helicase"
```

設定は `-c/--config`、索引は `-i/--index`、文献情報は `-p/--paper` の引数で操作を選びます。主操作は1回につき1つです。結果は既定でテキスト、機械処理には `--format json` を指定します。引数なしなら版番号・開発者名・説明と主な操作を表示し、端末ではusage・オプションを色分けします。`NO_COLOR`設定時、`TERM=dumb`、パイプやファイル出力では色を付けません。`-h/--help` なら詳細ヘルプを表示します。

`-o/--output` は `manual`・`config-template`・`citation` のいずれかを標準出力へ出します。例えば `bibdesk-rag --output config-template > example.toml` で設定テンプレートを保存できます。案内と資料出力は設定・索引がなくても利用できます。[操作体系と移行先](docs/usage.md)

## Homebrewで導入してCodexから使う

必要なものは、Mac、Homebrew、手元のBibDeskライブラリと添付ファイル、ローカルMCPを利用できるCodexです。Homebrew版にはPython環境が付属するため、利用者によるpyenv・pipの設定は不要です。MCPは下記のアプリ設定画面から登録できます。Codex CLIはコマンドで登録する場合だけ使う任意のツールで、本体の依存関係として自動インストールされません。

この手順は**同じMac上のCodexとの接続**を対象にします。ChatGPTの通常Chatへの接続は、この配布の対応範囲に含めません。別途ローカルプラグインを登録する必要もありません。

### 1. インストールし、対話型セットアップを実行する

```sh
brew install KentoYana/tap/bibdesk-rag
bibdesk-rag --setup
```

対話型セットアップは `--setup` で開始します。既存の設定・索引はそのまま使用できます。個別の操作で設定する場合は、下の [Manual Setup](#manual-setup) を使えます。

ターミナルの案内に沿って `.bib` のパスを入力し、表示された文献数・添付数を確認します。Finderからドラッグしたパス、空白や日本語を含むパス、`~`、相対パスも使えます。確認後に設定を作成し、初回索引の作成を提案します。BibDeskアプリ自体が未インストールでも、有効なライブラリがあれば利用できます。

Codex CLIが見つかれば、承認した場合だけMCPを引数なしで登録し、選択中の設定に追従させます。`--temp PATH --setup` の場合だけ設定を固定して登録します。同名の登録が一致する場合は再登録せず、異なる場合は変更しません。CLIがなくても索引は作成でき、アプリに手動登録するための実行ファイルの絶対パスと、通常は引数なしの手動接続方法を表示します。Codex CLIを自動インストールすることはありません。

保存先の指定や環境変数がない場合、macOSでも設定と索引を次の場所に作ります。Homebrewのアップグレードや再インストールでこれらを削除しません。

| 保存するもの | 既定の保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

すでに別の場所に設定がある場合は、一度選択してからセットアップします。設定・索引の自動移動や上書きはしません。

```sh
bibdesk-rag --config use "/absolute/path/to/config.toml"
bibdesk-rag --setup
```

再実行時は既存設定を確認し、索引の「そのまま使用」「差分更新」「明示的な全件再構築」を選べます。Ctrl+C・EOFで中断でき、作成済み設定は保持するので、同じコマンドで再開できます。入力と標準エラー出力が端末でない場合は入力待ちせず終了します。自動処理には [既存のCLI](docs/usage.md#ライブラリ登録と索引化) を使ってください。

最後に設定・索引の読み取りとローカルMCPの初期化・ツール一覧を確認します。「MCP登録済み」「MCPサーバー疎通確認済み」「Codexからの実検索は未検証」を区別して表示するため、完了後は次の検索も試してください。[詳しい動作と再開方法](docs/usage.md#対話型セットアップ)

### 2. Codexで検索する

次の依頼をCodexに送ります。「調べたいテーマ」を、自分が調べたい研究テーマやキーワードに置き換えてください。

```text
bibdesk-rag MCPを使って、私の文献ライブラリから
「調べたいテーマ」に関連する文献を最大5件探してください。

まず書誌情報から候補を選び、取得できる本文で内容を確認してください。

タイトル、著者、発表年、citekey、DOIを一覧にし、
それぞれがテーマとどう関係するかを短く説明してください。
本文に基づく説明には、短い抜粋とPDFページ番号を添えてください。

本文を確認できなかった文献や、検索機能を利用できない場合は、
その旨を明記してください。
```

CodexがMCPの `search_papers` と `search_fulltext` を呼び、所蔵資料の出典を伴う結果を返すことが接続確認になります。結果が0件でも接続失敗とは限りません。PDFページ番号はファイル先頭を1とする番号で、論文に印刷されたページ番号とは異なる場合があります。

## Manual Setup

個別の処理を実行したい場合の手順です。対話型セットアップと同じ既定保存先を使います。

### 1. 自分のライブラリを登録し、索引を作る

以下を順に実行します。`/absolute/path/to/references.bib` を自分の `.bib` の絶対パスに置き換えてください。空白を含むパスも引用符で囲んで指定できます。

```sh
bibdesk-rag --config create --bib "/absolute/path/to/references.bib"
bibdesk-rag --index update
bibdesk-rag --index status --format json
```

`--config create` は設定を作成し、`--index update` は書誌情報と対応する添付ファイルの本文を索引化します。初回はファイル数・サイズに応じて時間がかかります。`--index status` で文献数と抽出状態を確認してください。本文を抽出できない添付があっても、書誌情報は検索できます。

`--index update` / `--index rebuild` をターミナルで実行すると、文献・添付ファイルの処理件数を進捗バーで表示します。意味検索モデルの読み込みも同じ書式で表示し、完了した読み込みバーの下に索引バーを並べます。終了時には短い結果要約を表示し、PDF読み取り時の警告は件数と少数の例にまとめます。`--format json` で集計結果と要確認事項の全件をJSON出力、`--verbose` で警告・要確認事項をすべて表示、`--no-progress` で両方の進捗バーを無効にできます。ファイル・パイプへ渡す場合も既定形式はテキストです。[表示オプション](docs/usage.md#進捗と結果の表示)

この手順では、設定と索引を次の場所に保存します。`--config create` と `--index update` が必要なフォルダを作成するため、手でフォルダを作る必要はありません。

| 保存するもの | 保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

既存の設定は上書きしません。登録済みなら `--config create` を繰り返さず、`--index update` を使ってください。別の場所で登録済みなら、一度 `bibdesk-rag --config use "/absolute/path/to/config.toml"` を実行します。その後は保存先を指定せずに利用でき、設定・索引は元の場所に保持されます。

以前のmacOS保存先 `~/Library/Application Support/bibdesk-rag/` の自動検出は廃止しました。既存ファイルの移動・削除は行いません。任意の場所にある設定は、通常のカスタム設定として `--config use PATH` で選択できます。[保存先と設定の選択](docs/usage.md#設定の確認と選択)

### 2. Codexに読み取り専用MCPを登録する

アプリの設定画面かCLIの、どちらか一方で登録します。

#### アプリの設定画面から登録する（Codex CLIは不要）

Macアプリで **設定 → 左側の「連携」にある「プラグイン」→ 右上の「追加」→「MCP サーバーを追加」** と進みます。2026年11月2日に確認した日本語画面の配置です。

次の表に沿って、1つずつ入力・選択します。通常は引数を追加せず、CLIで選択中の設定に追従させます。

| 入力欄 | 入力・選択する値 |
| --- | --- |
| 名前 / Name | `bibdesk-rag` |
| 接続方式 / Transport | `STDIO` |
| コマンド / Command | 下のコマンドで表示された1行 |
| 引数 / Arguments | 空欄（追加しない） |

ターミナルで次を実行し、**出力されたパスだけ**を「コマンド」欄へコピーします。

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

`bibdesk-rag --config path` で選択中の設定を確認できます。別の設定を使う場合は `bibdesk-rag --config use PATH` で選びます。引数なしのMCPもその選択に追従します。GUIにはコマンドそのものや `$HOME`、`$(brew --prefix)`、パスを囲む引用符を貼り付けません。環境変数や作業ディレクトリの欄も通常は空欄で構いません。

既存登録に `--config PATH` や `--temp PATH` があれば、選択への追従には引数を2つとも削除します。特定の設定へ固定したい場合だけ、`--temp` と設定ファイルの絶対パスを2つの引数として指定します。[設定の固定と環境変数](docs/codex.md#設定ファイルを使う方法)

保存後、「プラグイン」画面の **MCP** タブで `bibdesk-rag` の登録を確認します。接続を再起動し、[Codexで検索する](#2-codexで検索する) へ進みます。[詳しい接続ガイド](docs/codex.md#codex-cliがない場合)

#### CLIから登録する場合

まず次を実行し、Codex CLIが使えるか確認します。

```sh
codex --version
```

未導入なら、[HomebrewのCodex CLI](https://formulae.brew.sh/cask/codex)をインストールしてください。すでに使えるCLIがあれば、追加インストールは不要です。

```sh
brew install --cask codex
codex --version
```

CLIが使えることを確認できたら、次を実行します。

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp"
codex mcp get bibdesk-rag
```

この操作でCodexのMCP設定に `bibdesk-rag` を追加します。同名の登録がある場合は、先に `codex mcp get bibdesk-rag` で内容を確認してください。Homebrewの版番号を含まない実行パスを使うため、通常のアップグレード後も登録を使えます。索引を作る操作はCLIで行い、Codexへ公開するのは検索・参照の7ツールだけです。

GUI・CLIのどちらで登録した場合も、登録内容の表示だけでは接続成功の確認にはなりません。MCP接続を再起動し、新しいチャットで次の検索を試してください。接続できない場合はCodexのアプリまたはCLIセッションも再起動します。MCPサーバーはCodexが起動するため、ターミナルで常時起動したり `brew services` に登録したりする必要はありません。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

## 日常の使い方

BibDeskで文献や添付ファイルを追加・変更した後は、索引を更新します。自動監視・自動更新は行いません。

```sh
bibdesk-rag --index update
```

通常の `--setup`・`--config create`・`--config use` で選んだ設定を自動的に使うため、カスタム設定でも毎回保存先を指定する必要はありません。現在の設定は、索引を開かずに確認できます。

```sh
bibdesk-rag --config show
bibdesk-rag --config show --format json
bibdesk-rag --config path
```

一度だけ別の設定を使う場合は `bibdesk-rag --temp "/absolute/path/to/config.toml" --index update` と指定します。`--temp --setup` でも保存済みの選択は変更しません。`--config use/create` とは併用できません。今後も使う設定には `--config use PATH` を使います。通常の引数なしMCP登録も選択に追従します。既存のMCPを設定パス付きで登録している場合は、その登録先を使い続けます。`--config use` はCodexの登録を変更しません。[設定の選択と優先順位](docs/usage.md#設定の確認と選択)

ファイルのサイズと更新日時だけでは変更を判断できない場合は `--index update --verify-hashes` を使います。`--index rebuild` は索引全体を作り直す操作です。どちらもBibDeskの原本は変更しません。

アプリを更新する場合は、次を実行します。

```sh
brew update
brew upgrade KentoYana/tap/bibdesk-rag
```

更新後はCodexのMCP接続を再起動します。Homebrewのupgrade・reinstall・uninstall時に設定や索引を削除するフックはありません。

## アンインストール

まずCodexから `bibdesk-rag` の接続登録を外します。CLIを使う場合は次を実行し、CodexのアプリやCLIセッションを終了して、動作中のMCPサーバーを停止します。CLIがない場合の解除方法は [接続解除ガイド](docs/codex.md#接続解除とアンインストール) にあります。

```sh
codex mcp remove bibdesk-rag
```

その後、本体と専用のPython環境を削除します。

```sh
brew uninstall KentoYana/tap/bibdesk-rag
```

**元の `.bib` と添付ファイル、保存済みの設定・索引は残ります。** 設定・索引も不要なら、実際に使用している設定の `database` の値を確認し、Finderの「移動 → フォルダへ移動」で次の場所をそれぞれ開き、中身を確認して対象ファイルをゴミ箱へ移動してください。

| 開くフォルダ | 削除対象 |
| --- | --- |
| `~/.config/bibdesk-rag/`（既定） | `config.toml`、設定選択を記録する `active-config.json` |
| `~/.local/share/bibdesk-rag/`（既定） | `index.sqlite3` |

索引の補助ファイル、以前の保存先や独自の保存先、Codex CLIも削除する場合については、[詳しい削除手順](docs/codex.md#接続解除とアンインストール) に従ってください。

## Title・Abstractの意味検索（任意）

日本語・英語の自然文から関連する文献候補を検索できます。Embeddingは数値による比較で、LLMによる文章生成ではありません。既定のキーワード検索は変わりません。PDF本文・添付・著者などは埋め込みません。

`--setup` で利用するかを選び、モデル未取得の場合だけ明示的にダウンロードします。Apple SiliconのHomebrew版は推論依存を同じ環境に含みます。ソース開発では既存の `.venv` に `.[semantic]` を導入します。

```sh
bibdesk-rag --setup
bibdesk-rag --index update
bibdesk-rag --paper search "相同組換え修復" --mode semantic --top 5
bibdesk-rag --index status --format json
```

索引は従来のSQLiteに統合し、`--index update/rebuild/status/check` で両検索方式を管理します。モデル取得だけが明示的にネットワークを使い、その後はCPUでオフライン実行します。MCPには `semantic_search_papers(query, limit=5)` を追加しました。対話型setup・統合SQLite・Homebrew・モデル変更・制約は [意味検索ガイド](docs/semantic-search.md) を参照してください。

## 検索できるものとデータの扱い

- 対応形式はPDF・CSV・TSV・XLSX・DOCX・PPTX・DOC・XLS・TeX・Keynote・Pages・Numbers・ZIPです。画像・動画は明示的に対象外です。[抽出範囲と制約](docs/file-formats.md)を参照してください。書誌情報と抽出できた本文をSQLite FTS5で検索します。オプションの意味検索はTitle・Abstractだけを対象とします。OCRは行いません。
- PDFはページ番号、PPTXはスライド番号、表計算はシート/表と行、文書は内部パート/段落・オブジェクト、TeXは原文行、ZIPは内部ファイル名を出典として返します。本文の検索結果にはchunk IDがあります。
- 本文なし・部分抽出・未対応形式を区別します。画像だけのPDF、暗号化や破損のある資料、段組・表などは本文を十分取得できない場合があります。研究上の主張は原本で確認してください。
- BibDesk RAGの索引作成・検索はローカルで完結し、外部API送信やモデルの自動ダウンロードはしません。**Codexへ返した書誌情報・抜粋は、Codex側のモデル処理に渡ります。** その扱いはCodexの契約・設定に従います。
- 索引は平文のSQLiteです。アプリは設定・索引を0600で作成します。バックアップやMacのアクセス権は利用者が管理してください。

検索の絞り込み、独自の保存先、複数ライブラリ、抽出制約の詳細は [CLI・設定ガイド](docs/usage.md) を参照してください。

## 困ったとき

| 状態 | 確認すること |
| --- | --- |
| `brew install` で配布先が見つからない | `brew update` の後、`brew install KentoYana/tap/bibdesk-rag` と完全な名前で指定します。[tap](https://github.com/KentoYana/homebrew-tap) とGitHubへの接続も確認してください。 |
| `bibdesk-rag: command not found` | Homebrewのインストール完了とPATHを確認します。`"$(brew --prefix)/bin/bibdesk-rag" --version` で切り分けできます。 |
| `codex: command not found` | 既存CLIの導入先とPATHを確認します。未導入なら `brew install --cask codex` で導入するか、[アプリから登録](docs/codex.md#codex-cliがない場合)します。 |
| `config.toml` が見つからない | `--config path` で選択先を確認します。既存設定を選び直すには `--config use PATH`、初回作成には `--setup` または `--config create` を使います。CLI・Codexが同じ設定を使うことも確認します。 |
| `unable to open database file` | 同じ設定を指定して `--index update` が完了したか、索引の保存先にアクセスできるかを確認します。 |
| Codexに登録済みだがツールを使えない | 新しいセッションで接続し、実行ファイルと選択中の設定を確認します。詳細は [接続の切り分け](docs/codex.md#接続の切り分け)。 |
| 文献は見つかるが本文が返らない | `bibdesk-rag --paper attachments CITEKEY --format json` で添付リンク・抽出状態を確認します。索引全体の状態は `--paper attachments CITEKEY` を `--index status` に置き換えて確認できます。 |

DBの整合性は `bibdesk-rag --index check --format json` で検査できます。`--config show` で選択先を確認でき、`--paper attachments`・`--index status`・`--index check` もその設定を使います。大きなDBでは検査用のメモリが必要です。問い合わせや不具合報告には、バージョン、実行コマンド、エラー文を添えてください。パス・書誌情報・本文などの私的な情報は必要に応じて伏せてください。

## 開発とソースからの利用

Python 3.11以上を対象とし、開発・ローカル検証はpyenvのPython 3.14.10だけを使います。`.python-version` も3.14.10です。Homebrew版は `python@3.14` と独立したvirtualenvを使用します。Homebrew利用者に以下の作業は不要です。

ソースのルートで、pyenvのローカル設定と標準venv・pipを使います。

```sh
pyenv install -s 3.14.10
pyenv local 3.14.10
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
```

ソース版のコマンドは `.venv/bin/bibdesk-rag` と `.venv/bin/bibdesk-rag-mcp` です。Codexへ登録するときは後者の絶対パスを指定します。pyenvのglobal設定は変更しません。依存元BibDeskParserのビルドバックエンド名は `uv_build` ですが、uvコマンドやuvによる環境管理は使いません。

## 配布・検証・設計

```sh
.venv/bin/python -m build
```

sdistとwheelを `dist/` に生成します。公開用Formulaには、実際に公開した固定URLと確認済みSHA-256が必要です。このリポジトリのFormulaは生成用テンプレートであり、インストール用のFormulaは外部tapにあります。ローカル検証と公開手順は [Homebrew配布手順](packaging/homebrew/README.md) にまとめています。

- [検証記録](docs/validation.md) / [Homebrew検証](docs/homebrew-validation.md) / [MCP検証](docs/mcp-validation.md)
- [互換性・索引更新の契約](docs/compatibility.md) / [P0対応の検証](docs/p0-validation.md)
- [Codex接続の詳細](docs/codex.md) / [CLI・設定・抽出仕様](docs/usage.md)
- [設計と拡張](docs/architecture.md)：Title・Abstractのローカル意味検索を追加しました。ハイブリッド検索、OCR、図表解析は未実装です。
- [MIT License](LICENSE) / [第三者ライセンスと依存一覧](THIRD_PARTY_NOTICES.md)

---

<a id="english"></a>

# BibDesk RAG — English

A local tool for searching and consulting literature managed in BibDesk from Codex. Narrow candidates using bibliography metadata, then retrieve short excerpts from PDFs and supplementary files with citekeys, DOIs, file locations and PDF page numbers.

The `.bib` library and its attachments are read-only. A separate derived index covers one explicitly registered library and its linked files. The tool does not rewrite the library or move attachments.

The application is maintained at [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG) and the Homebrew Formula at [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap). The [v0.5.1 release](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.5.1) provides an sdist, wheel, Homebrew build-dependency bundle and `SHA256SUMS`. For source installation, see [Development and source installation](#development-and-source-installation).

These instructions apply to v0.3.0 and later. When upgrading from v0.2.x or earlier, review the CLI changes (for example, `update` → `--index update`, `--json` → `--format json`) and removal of automatic discovery of the old macOS storage location. Existing configuration and indexes are neither moved nor deleted; select them with `--config use PATH` as needed. See [Migration](docs/usage.md#migrating-from-older-commands).

## CLI entry points

```sh
bibdesk-rag                     # Brief help
bibdesk-rag -h                  # Full help
bibdesk-rag -v                  # Version and software citation
bibdesk-rag -e                  # Common examples
bibdesk-rag -r                  # Bundled manual
bibdesk-rag --config show       # Inspect configuration
bibdesk-rag --index update      # Create or incrementally update the index
bibdesk-rag --paper search "RecQ helicase"
```

Choose configuration operations with `-c/--config`, index operations with `-i/--index`, and paper operations with `-p/--paper`. Use one main operation per invocation. Results default to text; use `--format json` for machine processing. No arguments shows the version, author, tagline and operation overview. Usage/options are colored on terminals; `NO_COLOR`, `TERM=dumb` or redirected output disables colors; `-h/--help` shows the full option reference.

`-o/--output` prints `manual`, `config-template` or `citation` to standard output. For example, `bibdesk-rag --output config-template > example.toml` saves a configuration template. Information and resource output work without a configuration or index. See the [CLI guide](docs/usage.md#operations-and-guidance).

## Install with Homebrew and connect to Codex

You need a Mac, Homebrew, a local BibDesk library and attachments, and Codex with local MCP support. The Homebrew package includes its Python environment; users do not need to configure pyenv or pip. Register MCP through the application settings below. Codex CLI is optional, used only for command-line registration, and is not installed automatically as an application dependency.

These instructions cover **Codex on the same Mac**. Ordinary Chat in ChatGPT is outside this distribution's supported setup. A separate local plugin is not required.

### 1. Install and run interactive setup

```sh
brew install KentoYana/tap/bibdesk-rag
bibdesk-rag --setup
```

Start interactive setup with `--setup`. Existing configuration and indexes remain usable. To run the individual operations yourself, use [Manual setup](#manual-setup-1) below.

Follow the terminal prompts to enter your `.bib` path and check the displayed paper and attachment counts. Finder-dragged paths, spaces, Japanese characters, `~` and relative paths are accepted. After confirmation, setup creates the configuration and offers to build the initial index. The BibDesk application itself need not be installed if a valid library is available.

If Codex CLI is found, setup registers MCP only after approval, without arguments to follow the selected configuration. Only `--temp PATH --setup` pins a configuration in the registration. It leaves matching registrations alone and does not change conflicting registrations. Without the CLI, indexing still works and setup displays the absolute executable path and manual registration details, normally without arguments. It never installs Codex CLI automatically.

Without custom paths or environment variables, configuration and index use these locations, including on macOS. Homebrew upgrades and reinstalls do not delete them.

| Data | Default location |
| --- | --- |
| BibDesk RAG configuration | `~/.config/bibdesk-rag/config.toml` |
| Search index | `~/.local/share/bibdesk-rag/index.sqlite3` |

If you already have a configuration elsewhere, select it before setup. Configuration and indexes are not automatically moved or overwritten.

```sh
bibdesk-rag --config use "/absolute/path/to/config.toml"
bibdesk-rag --setup
```

On subsequent runs, inspect the existing configuration and choose to reuse the index, update it incrementally or explicitly rebuild it. Ctrl+C or EOF interrupts setup while retaining completed configuration, so the same command can resume it. If input and standard error are not terminals, setup exits without waiting for input. For automation, use the [CLI operations](docs/usage.md#registering-and-indexing-a-library).

Finally, setup checks configuration/index readability and local MCP initialization/tool discovery. It distinguishes “MCP registered,” “local MCP server verified,” and “actual Codex search unverified.” Try the search below after completion. See [Setup behavior and resuming](docs/usage.md#interactive-setup).

### 2. Search from Codex

Send this request to Codex, replacing “research topic” with your topic or keywords:

```text
Use the bibdesk-rag MCP to find up to five papers in my library
related to “research topic”.

Select candidates using bibliography metadata first, then check their
contents using the available full text.

List the title, authors, year, citekey and DOI, and briefly explain how
each paper relates to the topic. For explanations based on full text,
include a short excerpt and PDF page number.

Clearly state when full text could not be checked or the search tools
are unavailable.
```

A successful connection is demonstrated when Codex calls MCP `search_papers` and `search_fulltext` and returns results with local source citations. Zero results do not necessarily mean connection failure. PDF pages count from 1 at the start of the file and may differ from printed article page numbers.

## Manual setup

Use these steps to perform individual operations. They use the same default locations as interactive setup.

### 1. Register your library and build its index

Run these commands in order, replacing `/absolute/path/to/references.bib` with your `.bib` file's absolute path. Quote paths containing spaces.

```sh
bibdesk-rag --config create --bib "/absolute/path/to/references.bib"
bibdesk-rag --index update
bibdesk-rag --index status --format json
```

`--config create` creates the configuration; `--index update` indexes metadata and the text of linked attachments. The first run can take time depending on file count and size. Check counts and extraction states with `--index status`. Metadata remains searchable even when some attachments cannot be extracted.

In a terminal, `--index update` / `--index rebuild` display a progress bar for papers and attachments, then a concise summary. Semantic model loading uses the same format, with its completed bar above the indexing bar. PDF parser warnings are summarized as counts and a few examples. Use `--format json` for the complete aggregate report and all issues, `--verbose` for all warnings/issues, or `--no-progress` to hide both bars. Redirected or piped output also defaults to text. See [Output options](docs/usage.md#progress-and-result-output).

The commands create the required directories automatically:

| Data | Location |
| --- | --- |
| BibDesk RAG configuration | `~/.config/bibdesk-rag/config.toml` |
| Search index | `~/.local/share/bibdesk-rag/index.sqlite3` |

Existing configuration is never overwritten. If already registered, use `--index update` instead of repeating `--config create`. To reuse a configuration elsewhere, run `bibdesk-rag --config use "/absolute/path/to/config.toml"` once. Subsequent commands use it without repeating the path, and existing files stay in place.

Automatic discovery of the former macOS location `~/Library/Application Support/bibdesk-rag/` has been removed. Existing files are not moved or deleted. Select any existing configuration with `--config use PATH`. See [Configuration selection](docs/usage.md#inspecting-and-selecting-configuration).

### 2. Register read-only MCP with Codex

Choose either application settings or CLI registration.

#### Register in the application settings (no Codex CLI needed)

In the Mac application, go to **Settings → Plugins under “Integrations” on the left → Add at the upper right → Add MCP server**. This describes the Japanese UI observed on November 2, 2026.

Enter/select each field below. Normally leave arguments empty so MCP follows the configuration selected by the CLI.

| Field | Value |
| --- | --- |
| Name | `bibdesk-rag` |
| Transport | `STDIO` |
| Command | The single path printed below |
| Arguments | Leave empty |

Run this in a terminal and copy **only the printed path** into Command:

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

`bibdesk-rag --config path` shows the selected configuration. Choose another with `bibdesk-rag --config use PATH`; MCP without arguments follows that selection too. Do not paste shell commands, `$HOME`, `$(brew --prefix)` or surrounding quotes into GUI fields. Environment-variable and working-directory fields can normally stay empty.

For an existing registration with `--config PATH` or `--temp PATH`, remove both arguments to follow the selection. Only when pinning a particular configuration, supply `--temp` and its absolute path as two arguments. See [Pinned configurations and environment variables](docs/codex.md#using-the-configuration-file).

After saving, check `bibdesk-rag` in the Plugins **MCP** tab, restart the connection and proceed to [Search from Codex](#2-search-from-codex). See the [detailed connection guide](docs/codex.md#without-codex-cli).

#### Register using the CLI

Check whether Codex CLI is available:

```sh
codex --version
```

If absent, install [Codex CLI with Homebrew](https://formulae.brew.sh/cask/codex). An existing working CLI does not need another installation.

```sh
brew install --cask codex
codex --version
```

Then register:

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp"
codex mcp get bibdesk-rag
```

This adds `bibdesk-rag` to Codex's MCP settings. If that name is already registered, inspect it with `codex mcp get bibdesk-rag` first. The executable path does not include a Homebrew version number and normally survives upgrades. Index maintenance uses the CLI; Codex receives seven read-only retrieval tools.

With either registration method, a displayed entry alone does not verify connectivity. Restart the MCP connection and try the search in a new chat. If needed, restart the Codex application or CLI session too. Codex launches the server; it does not need a persistent terminal process or `brew services` registration. See the [official MCP setup guide](https://learn.chatgpt.com/docs/extend/mcp).

## Everyday use

Update the index after adding or changing papers or attachments in BibDesk. There is no automatic watching or updating.

```sh
bibdesk-rag --index update
```

Commands automatically use the configuration selected by ordinary `--setup`, `--config create` or `--config use`, including custom locations. Inspect it without opening the index:

```sh
bibdesk-rag --config show
bibdesk-rag --config show --format json
bibdesk-rag --config path
```

For a one-time override, use `bibdesk-rag --temp "/absolute/path/to/config.toml" --index update`. `--temp --setup` also leaves the saved selection unchanged. `--temp` cannot be combined with `--config use/create`. Use `--config use PATH` for a persistent selection. Normal MCP registrations without arguments follow the selection too. Existing MCP registrations with explicit paths keep using those paths; `--config use` does not change Codex registrations. See [Configuration priority](docs/usage.md#inspecting-and-selecting-configuration).

Use `--index update --verify-hashes` when size and modification time alone may miss changes. `--index rebuild` rebuilds the entire index. Both preserve the original BibDesk sources.

To update the application:

```sh
brew update
brew upgrade KentoYana/tap/bibdesk-rag
```

Restart Codex's MCP connection afterwards. There are no configuration/index deletion hooks on Homebrew upgrade, reinstall or uninstall.

## Uninstall

First remove the Codex MCP registration. With the CLI, run the following, then close Codex application/CLI sessions to stop running MCP servers. Without the CLI, see [Disconnecting](docs/codex.md#disconnecting-and-uninstalling).

```sh
codex mcp remove bibdesk-rag
```

Remove the application and its dedicated Python environment:

```sh
brew uninstall KentoYana/tap/bibdesk-rag
```

**Your original `.bib`, attachments, saved configuration and index remain.** If you also want to remove application data, inspect the actual configuration's `database` value. Use Finder's Go → Go to Folder to open each directory, inspect its contents and move only the intended files to Trash.

| Folder | Files to remove |
| --- | --- |
| `~/.config/bibdesk-rag/` (default) | `config.toml`, `active-config.json` (saved selection) |
| `~/.local/share/bibdesk-rag/` (default) | `index.sqlite3` |

For index sidecars, old/custom locations and optional Codex CLI removal, follow the [detailed removal instructions](docs/codex.md#disconnecting-and-uninstalling).

## Optional title/abstract semantic search

Find English papers using Japanese or English natural-language queries with a local multilingual model. Embeddings are numerical representations, not LLM text generation. Only title/abstract are embedded; keyword search remains the default.

Run `bibdesk-rag --setup` to choose semantic search and explicitly acquire its model. For source development, install the semantic extra into the existing `.venv`:

```sh
bibdesk-rag --setup
bibdesk-rag --index update
bibdesk-rag --paper search "DNA repair mechanisms" --mode semantic --top 5
bibdesk-rag --index status --format json
```

Bibliography/text and vectors share the same SQLite and `--index` actions. Only explicit model download needs network. Indexing and search run offline on CPU. MCP adds `semantic_search_papers(query, limit=5)`. See the [semantic search guide](docs/semantic-search.md) for setup, unified SQLite/index actions, Homebrew, model changes and validation.

## Search coverage and data handling

- Supported formats: PDF, CSV, TSV, XLSX, DOCX, PPTX, DOC, XLS, TeX, Keynote, Pages, Numbers and ZIP. Images/videos are explicitly excluded. See [extraction scope and limitations](docs/file-formats.md). Metadata and extracted text are searched with SQLite FTS5. Optional semantic search embeds title/abstract only. OCR is not performed.
- Citations identify PDF pages, PPTX slides, spreadsheet sheets/tables and rows, document parts/paragraphs or objects, TeX source lines and ZIP members. Full-text results include chunk IDs.
- Missing text, partial extraction and unsupported formats are distinguished. Image-only, encrypted or damaged PDFs, columns and tables may yield insufficient text. Verify scientific claims against original sources.
- Indexing and search run locally, without external API submission or automatic model downloads. **Metadata/excerpts returned to Codex are passed to Codex's model processing**, subject to its terms and settings.
- The index is plaintext SQLite. The application creates configuration/index files with mode 0600. Users manage backups and Mac access permissions.

For filters, custom paths, multiple libraries and extraction limits, see the [CLI and configuration guide](docs/usage.md#english).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `brew install` cannot find the distribution | Run `brew update`, then use the full name `brew install KentoYana/tap/bibdesk-rag`. Check access to the [tap](https://github.com/KentoYana/homebrew-tap) and GitHub. |
| `bibdesk-rag: command not found` | Check installation and PATH. Try `"$(brew --prefix)/bin/bibdesk-rag" --version`. |
| `codex: command not found` | Check the existing CLI installation and PATH. Install with `brew install --cask codex` if needed, or [register in the application](docs/codex.md#without-codex-cli). |
| Missing `config.toml` | Check `--config path`. Use `--config use PATH` to select an existing configuration, or `--setup` / `--config create` for a new one. Ensure CLI and Codex use the same configuration. |
| `unable to open database file` | Check that `--index update` completed for the same configuration and that the index location is accessible. |
| Registered in Codex but tools unavailable | Reconnect in a new session; check the absolute executable path and selected configuration. See [Connection troubleshooting](docs/codex.md#connection-troubleshooting). |
| Metadata found but no full text | Check links and extraction states with `bibdesk-rag --paper attachments CITEKEY --format json`. Replace `--paper attachments CITEKEY` with `--index status` for overall index status. |

Check database integrity with `bibdesk-rag --index check --format json`. Inspect the selected configuration with `--config show`; attachments, status and check use that same selection. Large databases require memory for checks. Include the version, command and error text in support requests, redacting private paths, metadata and excerpts as needed.

## Development and source installation

Python 3.11+ is supported; development and local validation use only pyenv Python 3.14.10, pinned by `.python-version`. Homebrew uses `python@3.14` and a separate virtualenv. Homebrew users do not need these development steps.

From the source root, use local pyenv configuration, standard venv and pip:

```sh
pyenv install -s 3.14.10
pyenv local 3.14.10
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
```

Source commands are `.venv/bin/bibdesk-rag` and `.venv/bin/bibdesk-rag-mcp`. Register the latter with its absolute path in Codex. Do not change global pyenv settings. BibDeskParser's upstream build backend is named `uv_build`; the uv command/environment manager is not used.

## Distribution, validation and design

```sh
.venv/bin/python -m build
```

This generates sdist and wheel in `dist/`. A published Formula needs actual fixed release URLs and verified SHA-256 hashes. This repository keeps a generation template; the installable Formula lives in the external tap. See [Homebrew distribution](packaging/homebrew/README.md#english) for local validation and publication procedures.

- [Validation record](docs/validation.md#english) / [Homebrew validation](docs/homebrew-validation.md#english) / [MCP validation](docs/mcp-validation.md#english)
- [Compatibility and index upgrades](docs/compatibility.md) / [P0 validation](docs/p0-validation.md)
- [Codex connection guide](docs/codex.md#english) / [CLI, configuration and extraction](docs/usage.md#english)
- [Architecture and extensions](docs/architecture.md#english): local title/abstract embeddings are optional; hybrid search, OCR and figure/table analysis are not implemented.
- [MIT License](LICENSE) / [Third-party licenses and dependencies](THIRD_PARTY_NOTICES.md#english)
