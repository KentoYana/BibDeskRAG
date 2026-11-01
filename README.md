# BibDesk RAG

BibDeskで管理する文献を、Codexから検索・参照するためのローカルツールです。書誌情報で候補を絞り、PDFや補足資料の短い抜粋を、citekey・DOI・ファイルの場所・PDFページ番号とともに取得できます。

BibDeskの `.bib` と添付ファイルを読み取り専用で扱い、検索用の索引を別の場所に作ります。対象は登録した1つのライブラリと、そのライブラリにリンクされたファイルです。ライブラリの書き換えや添付ファイルの移動は行いません。

本体は [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG)、Homebrew Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap) で管理しています。[v0.1.0のRelease](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0) にはソース配布・wheel・Homebrew用ビルド依存bundleと `SHA256SUMS` を掲載します。ソースから利用する場合は [開発とソースからの利用](#開発とソースからの利用) を参照してください。

## Homebrewで導入してCodexから使う

必要なものは、Mac、Homebrew、手元のBibDeskライブラリと添付ファイル、ローカルMCPを利用できるCodexです。Homebrew版にはPython環境が付属するため、利用者によるpyenv・pipの設定は不要です。Codexをコマンドで設定する場合は `codex` コマンドも必要です。CLIを使わない設定方法は [Codex接続ガイド](docs/codex.md) にあります。

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
bibdesk_rag_config="$HOME/Library/Application Support/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" init --bib "/absolute/path/to/references.bib"
bibdesk-rag --config "$bibdesk_rag_config" index
bibdesk-rag --config "$bibdesk_rag_config" status --json
```

`init` は設定を作成し、`index` は書誌情報と対応する添付ファイルの本文を索引化します。初回はファイル数・サイズに応じて時間がかかります。`status` で文献数と抽出状態を確認してください。本文を抽出できない添付があっても、書誌情報は検索できます。

既存の設定は上書きしません。登録済みなら `init` を繰り返さず、現在の設定を確認して `update` を使ってください。標準では設定と索引を `~/Library/Application Support/bibdesk-rag/` に保存します。原本やHomebrewのインストール先には保存しません。

### 3. Codexに読み取り専用MCPを登録する

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp" \
  --config "$HOME/Library/Application Support/bibdesk-rag/config.toml"
codex mcp get bibdesk-rag
```

この操作でCodexのMCP設定に `bibdesk-rag` を追加します。同名の登録がある場合は、先に `codex mcp get bibdesk-rag` で内容を確認してください。Homebrewの版番号を含まない実行パスを使うため、通常のアップグレード後も登録を使えます。索引を作る操作はCLIで行い、Codexへ公開するのは検索・参照の6ツールだけです。

登録内容の表示だけでは接続成功の確認にはなりません。Codexのアプリまたはセッションを再起動し、新しいチャットで次の検索を試してください。MCPサーバーはCodexが起動するため、ターミナルで常時起動したり `brew services` に登録したりする必要はありません。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

### 4. Codexで検索する

次の依頼をCodexに送ります。RecQを所蔵していない場合は、ライブラリにある文献のタイトル中の語へ置き換えてください。

```text
bibdesk-rag MCPを使い、RecQに関する文献を最大5件探してください。
まず書誌情報を検索し、選んだ候補の本文から関連箇所を取得してください。
タイトル、著者、年、citekey、DOI、短い本文抜粋、PDFページ番号、
ファイルの場所とchunk IDを示してください。
書誌情報だけで確認できた内容と、本文で確認できた内容を区別してください。
MCPを利用できない場合は、その旨を教えてください。
```

CodexがMCPの `search_papers` と `search_fulltext` を呼び、所蔵資料の出典を伴う結果を返すことが接続確認になります。結果が0件でも接続失敗とは限りません。PDFページ番号はファイル先頭を1とする番号で、論文に印刷されたページ番号とは異なる場合があります。

## 日常の使い方

BibDeskで文献や添付ファイルを追加・変更した後は、索引を更新します。自動監視・自動更新は行いません。

```sh
bibdesk-rag --config "$HOME/Library/Application Support/bibdesk-rag/config.toml" update
```

ファイルのサイズと更新日時だけでは変更を判断できない場合は `update --verify-hashes` を使います。`index` は索引全体を作り直す操作です。どちらもBibDeskの原本は変更しません。

アプリを更新する場合は、次を実行します。

```sh
brew update
brew upgrade KentoYana/tap/bibdesk-rag
```

更新後はCodexのMCP接続を再起動します。Homebrewのupgrade・reinstall・uninstall時に設定や索引を削除するフックはありません。利用を止める場合は `codex mcp remove bibdesk-rag` でCodexの登録を外せます。この操作もBibDeskの原本や索引を削除しません。

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
| `config.toml` が見つからない | `init` の完了と、CLI・Codexが同じ `--config` を使うことを確認します。 |
| `unable to open database file` | 同じ設定を指定して `index` が完了したか、索引の保存先にアクセスできるかを確認します。 |
| Codexに登録済みだがツールを使えない | 新しいセッションで接続し、実行ファイルと設定ファイルの絶対パスを確認します。詳細は [接続の切り分け](docs/codex.md#接続の切り分け)。 |
| 文献は見つかるが本文が返らない | `bibdesk-rag attachments CITEKEY --json` と `status --json` で添付リンク・抽出状態を確認します。独自設定では先頭に `--config PATH` を付けます。 |

DBの整合性は `bibdesk-rag doctor --json` で検査できます。大きなDBでは検査用のメモリが必要です。問い合わせや不具合報告には、バージョン、実行コマンド、エラー文を添えてください。パス・書誌情報・本文などの私的な情報は必要に応じて伏せてください。

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
