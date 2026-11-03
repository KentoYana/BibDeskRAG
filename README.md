# BibDesk RAG

BibDeskで管理する文献を、Codexから検索・参照するためのローカルツールです。書誌情報で候補を絞り、PDFや補足資料の短い抜粋を、citekey・DOI・ファイルの場所・PDFページ番号とともに取得できます。

BibDeskの `.bib` と添付ファイルを読み取り専用で扱い、検索用の索引を別の場所に作ります。対象は登録した1つのライブラリと、そのライブラリにリンクされたファイルです。ライブラリの書き換えや添付ファイルの移動は行いません。

本体は [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG)、Homebrew Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap) で管理しています。[v0.3.0のRelease](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.3.0) にはソース配布・wheel・Homebrew用ビルド依存bundleと `SHA256SUMS` を掲載しています。ソースから利用する場合は [開発とソースからの利用](#開発とソースからの利用) を参照してください。

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

設定は `-c/--config`、索引は `-i/--index`、文献情報は `-p/--paper` の引数で操作を選びます。主操作は1回につき1つです。結果は既定でテキスト、機械処理には `--format json` を指定します。引数なしなら主な操作と案内だけの短縮ヘルプ、`-h/--help` なら詳細ヘルプを表示します。

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

Codex CLIが見つかれば、承認した場合だけMCPを登録します。同名の登録が一致する場合は再登録せず、異なる場合は変更しません。CLIがなくても索引は作成でき、アプリに手動登録するための実行ファイル・設定ファイルの絶対パスを表示します。Codex CLIを自動インストールすることはありません。

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

`--index update` / `--index rebuild` をターミナルで実行すると、文献・添付ファイルの処理件数を1行の進捗バーで表示します。終了時には短い結果要約を表示し、PDF読み取り時の警告は件数と少数の例にまとめます。`--format json` で集計結果と要確認事項の全件をJSON出力、`--verbose` で警告・要確認事項をすべて表示、`--no-progress` で進捗バーだけを無効にできます。ファイル・パイプへ渡す場合も既定形式はテキストです。[表示オプション](docs/usage.md#進捗と結果の表示)

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

次の表に沿って、1つずつ入力・選択します。引数は**2つに分けて**、1件目、2件目の順に追加してください。

| 入力欄 | 入力・選択する値 |
| --- | --- |
| 名前 / Name | `bibdesk-rag` |
| 接続方式 / Transport | `STDIO` |
| コマンド / Command | 下の①で表示された1行 |
| 引数 / Arguments の1件目 | `--temp` |
| 引数 / Arguments の2件目 | 下の②で表示された1行 |

① ターミナルで次を実行し、**出力されたパスだけ**を「コマンド」欄へコピーします。

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

② ターミナルで次を実行し、**出力されたパスだけ**を「引数」の2件目へコピーします。

```sh
bibdesk-rag --config path
```

`--config path` は選択中の設定パスを表示します。別の設定なら、先に `--config use PATH` で選んでください。GUIにはコマンドそのものや `$HOME`、`$(brew --prefix)`、パスを囲む引用符を貼り付けません。「コマンド」欄には実行ファイルのパスだけを入れ、`--temp` を混ぜないでください。環境変数や作業ディレクトリの欄がある場合は空欄のままで構いません。

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
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp" \
  --temp "$(bibdesk-rag --config path)"
codex mcp get bibdesk-rag
```

この操作でCodexのMCP設定に `bibdesk-rag` を追加します。同名の登録がある場合は、先に `codex mcp get bibdesk-rag` で内容を確認してください。Homebrewの版番号を含まない実行パスを使うため、通常のアップグレード後も登録を使えます。索引を作る操作はCLIで行い、Codexへ公開するのは検索・参照の6ツールだけです。

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

一度だけ別の設定を使う場合は `bibdesk-rag --temp "/absolute/path/to/config.toml" --index update` と指定します。`--temp --setup` でも保存済みの選択は変更しません。`--config use/create` とは併用できません。今後も使う設定には `--config use PATH` を使います。CodexのMCPを設定パス付きで登録している場合は、その登録先を使い続けます。`--config use` はCodexの登録を変更しません。[設定の選択と優先順位](docs/usage.md#設定の確認と選択)

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

## 検索できるものとデータの扱い

- 対応形式はPDF・CSV・TSV・XLSX・ZIPです。書誌情報と抽出できた本文をSQLite FTS5で検索します。意味検索・埋め込みモデル・OCRは使いません。
- PDFはページ番号、CSV/TSVはレコード行、XLSXはシートと行、ZIPは内部ファイル名を出典として返します。本文の検索結果にはchunk IDがあります。
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
| Codexに登録済みだがツールを使えない | 新しいセッションで接続し、実行ファイルと設定ファイルの絶対パスを確認します。詳細は [接続の切り分け](docs/codex.md#接続の切り分け)。 |
| 文献は見つかるが本文が返らない | `bibdesk-rag --paper attachments CITEKEY --format json` で添付リンク・抽出状態を確認します。索引全体の状態は `--paper attachments CITEKEY` を `--index status` に置き換えて確認できます。 |

DBの整合性は `bibdesk-rag --index check --format json` で検査できます。`--config show` で選択先を確認でき、`--paper attachments`・`--index status`・`--index check` もその設定を使います。大きなDBでは検査用のメモリが必要です。問い合わせや不具合報告には、バージョン、実行コマンド、エラー文を添えてください。パス・書誌情報・本文などの私的な情報は必要に応じて伏せてください。

## 開発とソースからの利用

Python 3.11以上を対象とし、開発用の `.python-version` は3.12.13です。Homebrew版は `python@3.14` と独立したvirtualenvを使用します。Homebrew利用者に以下の作業は不要です。

ソースのルートで、pyenvのローカル設定と標準venv・pipを使います。

```sh
pyenv install -s 3.12.13
pyenv local 3.12.13
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
- [Codex接続の詳細](docs/codex.md) / [CLI・設定・抽出仕様](docs/usage.md)
- [設計と拡張](docs/architecture.md)：ローカルembedding、ハイブリッド検索、OCR、図表解析は未実装です。
- [MIT License](LICENSE) / [第三者ライセンスと依存一覧](THIRD_PARTY_NOTICES.md)
