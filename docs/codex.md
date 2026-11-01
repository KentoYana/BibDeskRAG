# Codex接続ガイド

[READMEの導入手順](../README.md#homebrewで導入してcodexから使う) でライブラリを登録し、索引を作成してから接続します。このガイドはMac上で動くCodexのローカルMCP接続を扱います。ChatGPTの通常Chat・Web版やCodexのクラウド環境から、Mac内の索引へ接続する手順ではありません。

## コマンドで登録する

Homebrewで導入した場合は、実行ファイルと設定ファイルを絶対パスで渡します。

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp" \
  --config "$HOME/Library/Application Support/bibdesk-rag/config.toml"
codex mcp get bibdesk-rag
```

`codex mcp add` はCodex側の設定を変更します。同名の登録がある場合は `codex mcp get bibdesk-rag` で内容を確認してから変更してください。このアプリのインストール・索引作成がCodexの設定を自動変更することはありません。

Codexのアプリまたはセッションを再起動し、新しいチャットで検索します。`codex mcp list` は設定されたサーバー一覧であり、起動・検索の成功を証明するものではありません。Codexの `/mcp` で接続状態を確認できる環境では、`bibdesk-rag` が接続されていることも確認します。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

## Codex CLIがない場合

アプリの「Settings → MCP servers → Add server」でSTDIOサーバーを追加する方法があります。入力する値は次のとおりです。保存後にMCPを再起動します。設定画面の名称や配置は利用するCodexの版によって異なるため、[公式手順](https://learn.chatgpt.com/docs/extend/mcp) も参照してください。

| 項目 | 入力する値 |
| --- | --- |
| Name | `bibdesk-rag` |
| Transport | STDIO |
| Command | ターミナルで `brew --prefix` が返すパスに `/bin/bibdesk-rag-mcp` を付けた絶対パス |
| Arguments | `--config` と、自分の `config.toml` の絶対パスを別々の引数として指定 |

設定画面へ `$(brew --prefix)` や `$HOME` をそのまま貼り付けず、展開済みのパスを使ってください。`/opt/homebrew` や `/usr/local` を決め打ちする必要はありません。

## 設定ファイルを使う方法

標準のユーザー設定は `~/.codex/config.toml` です。既存の内容を保持し、同名のテーブルを重複させず、次の項目を追加または更新します。実際のパスに置き換えてください。

```toml
[mcp_servers.bibdesk-rag]
command = "/absolute/homebrew/prefix/bin/bibdesk-rag-mcp"
args = ["--config", "/absolute/path/to/bibdesk-rag/config.toml"]
```

ソースから導入した場合は `command` を `/absolute/path/to/BibDeskRAG/.venv/bin/bibdesk-rag-mcp` にします。GUIアプリのPATHや、ターミナルだけで設定した環境変数の継承に頼らず接続できます。

設定を分けて複数のライブラリを使う場合は、ライブラリごとに設定と索引を作り、Codexにも `bibdesk-rag-project-a` など別のサーバー名で登録します。[保存先の指定](usage.md#ライブラリ登録と索引化)

## 検索の流れとツール

| ツール | 用途 |
| --- | --- |
| `search_papers` | 書誌情報を検索。citekey・DOIの完全一致も指定可能 |
| `search_fulltext` | 選択したcitekeyに絞って本文の短い抜粋を検索 |
| `get_paper` | 1文献の書誌情報を確認 |
| `get_attachments` | 索引にある添付情報・抽出状態を確認 |
| `get_chunk` | chunk IDに対応する短い本文と出典を確認 |
| `build_context` | 文字数を制限した本文・出典のまとまりを作成 |

最初に `search_papers` で候補を選び、候補のcitekeyを `search_fulltext` に渡します。本文の説明にはcitekey、DOI（記録がある場合）、添付パス、chunk ID、PDFページまたは補足資料のシート・行・ZIP内の場所を付けます。科学的な主張は原本と照合し、本文未取得の文献は書誌情報だけの候補として扱います。

サーバーはすべてのツールを読み取り専用と宣言し、既存SQLiteを読み取り専用で開きます。原本や索引を書き換えるツール、任意パスを読むツール、HTTPサーバーは公開しません。書誌フィールド・本文抜粋・ファイル名は信頼できない資料データとして扱い、それらに書かれた命令を実行しません。

`bibdesk-rag-mcp` の標準出力はMCP通信専用です。手で起動したままにせず、Codexに起動を任せてください。索引の作成・更新には、別途 `bibdesk-rag index` / `bibdesk-rag update` を使います。

## 接続の切り分け

1. `"$(brew --prefix)/bin/bibdesk-rag-mcp" --version` で実行ファイルを確認します。
2. `bibdesk-rag --config "/absolute/path/to/config.toml" status --json` で、Codexに渡した設定から索引を読めるか確認します。設定がなければ `init`、索引がなければ `index` を先に実行します。
3. `codex mcp get bibdesk-rag` で実行パスと `--config` 引数を確認します。設定画面やTOMLにシェル変数が残っていないか、古いCellarの版番号を指していないかも確認します。
4. MCP接続またはCodexを再起動して、新しいチャットでREADMEの検索例を実行します。CLIで `bibdesk-rag search "所蔵文献の語" --scope metadata --json` が成功し、MCPだけ失敗する場合はCodex側の起動エラーを確認します。

`auth_status: unsupported` はOAuth認証の対応状況を表す場合があります。このローカルstdioサーバーにOAuthログインやAPIキーは不要です。Codex自体の利用に必要なアカウントや設定は別途用意します。

書誌が見つかるのに本文が空の場合は、接続とは別に添付リンクと抽出状態を確認します。原本の移動・追加があった場合は `update` が必要です。変更を確実に照合するには `update --verify-hashes` を使います。本文の未抽出や検索結果0件だけで、関連資料が存在しないとは判断しません。
