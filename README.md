# BibDesk RAG

BibDeskで管理する文献を、Codexから検索・参照するためのローカルツールです。書誌情報で候補を絞り、PDFや補足資料の短い抜粋を、citekey・DOI・ファイルの場所・PDFページ番号とともに取得できます。

BibDeskの `.bib` と添付ファイルを読み取り専用で扱い、検索用の索引を別の場所に作ります。対象は登録した1つのライブラリと、そのライブラリにリンクされたファイルです。ライブラリの書き換えや添付ファイルの移動は行いません。

本体は [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG)、Homebrew Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap) で管理しています。[v0.1.1のRelease](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.1) にはソース配布・wheel・Homebrew用ビルド依存bundleと `SHA256SUMS` を掲載しています。ソースから利用する場合は [開発とソースからの利用](#開発とソースからの利用) を参照してください。

## Homebrewで導入してCodexから使う

必要なものは、Mac、Homebrew、手元のBibDeskライブラリと添付ファイル、ローカルMCPを利用できるCodexです。Homebrew版にはPython環境が付属するため、利用者によるpyenv・pipの設定は不要です。MCPは下記のアプリ設定画面から登録できます。Codex CLIはコマンドで登録する場合だけ使う任意のツールで、本体の依存関係として自動インストールされません。

この手順は**同じMac上のCodexとの接続**を対象にします。ChatGPTの通常Chatへの接続は、この配布の対応範囲に含めません。別途ローカルプラグインを登録する必要もありません。

### 1. インストールする

Homebrewの外部tapからインストールします。

```sh
brew install KentoYana/tap/bibdesk-rag
bibdesk-rag --version
```

### 2. 自分のライブラリを登録し、索引を作る

以下は同じターミナルで実行します。`/absolute/path/to/references.bib` を自分の `.bib` の絶対パスに置き換えてください。空白を含むパスも引用符で囲んで指定できます。

```sh
bibdesk_rag_config="$HOME/.config/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" init \
  --bib "/absolute/path/to/references.bib" \
  --data-dir "$HOME/.local/share/bibdesk-rag"
bibdesk-rag --config "$bibdesk_rag_config" index
bibdesk-rag --config "$bibdesk_rag_config" status --json
```

`init` は設定を作成し、`index` は書誌情報と対応する添付ファイルの本文を索引化します。初回はファイル数・サイズに応じて時間がかかります。`status` で文献数と抽出状態を確認してください。本文を抽出できない添付があっても、書誌情報は検索できます。

v0.1.1以降では、`index` / `update` をターミナルで実行すると、文献・添付ファイルの処理件数を1行の進捗バーで表示します。終了時には短い結果要約を表示し、PDF読み取り時の警告は件数と少数の例にまとめます。`--json` で集計結果と要確認事項の全件をJSON出力、`--verbose` で警告・要確認事項をすべて表示、`--no-progress` で進捗バーだけを無効にできます。出力をファイルやパイプへ渡す場合は、従来どおりJSONを出力します。[表示オプション](docs/usage.md#進捗と結果の表示)

この手順では、設定と索引を次の場所に保存します。`init` と `index` が必要なフォルダを作成するため、手でフォルダを作る必要はありません。

| 保存するもの | 保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

既存の設定は上書きしません。登録済みなら `init` を繰り返さず、現在の設定を指定して `update` を使ってください。別の場所で登録済みの場合、上の変数を書き換えるだけでは設定・索引は移動しません。

このREADMEでは上記を標準の手順として使います。v0.1.0・v0.1.1では、保存先の引数・環境変数を何も指定しない場合、macOSでは `~/Library/Application Support/bibdesk-rag/` を使うため、以降も `--config` を明示します。原本やHomebrewのインストール先には保存しません。[保存先の指定](docs/usage.md#ライブラリ登録と索引化)

### 3. Codexに読み取り専用MCPを登録する

アプリの設定画面かCLIの、どちらか一方で登録します。

#### アプリの設定画面から登録する（Codex CLIは不要）

Macアプリで **設定 → 左側の「連携」にある「プラグイン」→ 右上の「追加」→「MCP サーバーを追加」** と進みます。2026年11月2日に確認した日本語画面の配置です。

次の表に沿って、1つずつ入力・選択します。引数は**2つに分けて**、1件目、2件目の順に追加してください。

| 入力欄 | 入力・選択する値 |
| --- | --- |
| 名前 / Name | `bibdesk-rag` |
| 接続方式 / Transport | `STDIO` |
| コマンド / Command | 下の①で表示された1行 |
| 引数 / Arguments の1件目 | `--config` |
| 引数 / Arguments の2件目 | 下の②で表示された1行 |

① ターミナルで次を実行し、**出力されたパスだけ**を「コマンド」欄へコピーします。

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

② ターミナルで次を実行し、**出力されたパスだけ**を「引数」の2件目へコピーします。

```sh
printf '%s\n' "$HOME/.config/bibdesk-rag/config.toml"
```

設定を別の場所に作った場合は、②にその保存先を指定してください。GUIにはコマンドそのものや `$HOME`、`$(brew --prefix)`、パスを囲む引用符を貼り付けません。「コマンド」欄には実行ファイルのパスだけを入れ、`--config` を混ぜないでください。環境変数や作業ディレクトリの欄がある場合は空欄のままで構いません。

保存後、「プラグイン」画面の **MCP** タブで `bibdesk-rag` の登録を確認します。接続を再起動し、手順4の検索へ進みます。[詳しい接続ガイド](docs/codex.md#codex-cliがない場合)

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
  --config "$HOME/.config/bibdesk-rag/config.toml"
codex mcp get bibdesk-rag
```

この操作でCodexのMCP設定に `bibdesk-rag` を追加します。同名の登録がある場合は、先に `codex mcp get bibdesk-rag` で内容を確認してください。Homebrewの版番号を含まない実行パスを使うため、通常のアップグレード後も登録を使えます。索引を作る操作はCLIで行い、Codexへ公開するのは検索・参照の6ツールだけです。

GUI・CLIのどちらで登録した場合も、登録内容の表示だけでは接続成功の確認にはなりません。MCP接続を再起動し、新しいチャットで次の検索を試してください。接続できない場合はCodexのアプリまたはCLIセッションも再起動します。MCPサーバーはCodexが起動するため、ターミナルで常時起動したり `brew services` に登録したりする必要はありません。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

### 4. Codexで検索する

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

## 日常の使い方

BibDeskで文献や添付ファイルを追加・変更した後は、索引を更新します。自動監視・自動更新は行いません。

```sh
bibdesk-rag --config "$HOME/.config/bibdesk-rag/config.toml" update
```

ファイルのサイズと更新日時だけでは変更を判断できない場合は `update --verify-hashes` を使います。`index` は索引全体を作り直す操作です。どちらもBibDeskの原本は変更しません。

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

**元の `.bib` と添付ファイル、保存済みの設定・索引は残ります。** このREADMEの手順で作った設定・索引も不要なら、Finderの「移動 → フォルダへ移動」で次の場所をそれぞれ開き、中身を確認して対象ファイルをゴミ箱へ移動してください。

| 開くフォルダ | 削除対象 |
| --- | --- |
| `~/.config/bibdesk-rag/` | `config.toml` |
| `~/.local/share/bibdesk-rag/` | `index.sqlite3` |

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
| `config.toml` が見つからない | `init` の完了と、CLI・Codexが同じ `--config` を使うことを確認します。 |
| `unable to open database file` | 同じ設定を指定して `index` が完了したか、索引の保存先にアクセスできるかを確認します。 |
| Codexに登録済みだがツールを使えない | 新しいセッションで接続し、実行ファイルと設定ファイルの絶対パスを確認します。詳細は [接続の切り分け](docs/codex.md#接続の切り分け)。 |
| 文献は見つかるが本文が返らない | `bibdesk-rag --config "$HOME/.config/bibdesk-rag/config.toml" attachments CITEKEY --json` で添付リンク・抽出状態を確認します。索引全体の状態は `attachments CITEKEY` を `status` に置き換えて確認できます。 |

DBの整合性は `bibdesk-rag --config "$HOME/.config/bibdesk-rag/config.toml" doctor --json` で検査できます。大きなDBでは検査用のメモリが必要です。問い合わせや不具合報告には、バージョン、実行コマンド、エラー文を添えてください。パス・書誌情報・本文などの私的な情報は必要に応じて伏せてください。

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
