# Codex接続ガイド

[READMEの導入手順](../README.md#homebrewで導入してcodexから使う) でライブラリを登録し、索引を作成してから接続します。このガイドはMac上で動くCodexのローカルMCP接続を扱います。ChatGPTの通常Chat・Web版やCodexのクラウド環境から、Mac内の索引へ接続する手順ではありません。

## 対話型セットアップ（推奨）

```sh
bibdesk-rag setup
```

`setup` はv0.2.0以降で利用できます。v0.1.xでは下の手動接続手順を使うか、本体を更新してください。別の場所に設定がある場合は `bibdesk-rag --config "/absolute/path/to/config.toml" setup` と指定してください。

ウィザードはライブラリ登録・索引作成の後、Codex CLIがあればMCP登録を提案します。承認した場合だけ、検出した `bibdesk-rag-mcp` と設定ファイルの絶対パスを渡して登録します。既存の同名登録が一致すれば再登録せず、異なる場合や登録状況を判定できない場合は変更しません。Codexのほかの設定・サーバー登録も変更しません。

CLIがない場合、登録を省略した場合、登録に失敗した場合にも、作成済み索引はCLIで利用できます。画面に表示した手動接続情報を [アプリ設定](#codex-cliがない場合) に入力してください。実行ファイルを検出できなかった場合は、パッケージの導入先・PATHを確認してから再実行します。CLIの自動インストールはしません。

完了画面は、次の確認範囲を分けて表示します。

| 表示する状態 | 確認した範囲 |
| --- | --- |
| 設定・索引が利用可能 | 設定を読み込み、SQLiteを読み取り専用で開いて件数を取得 |
| MCP登録済み | Codexの登録内容が実行ファイル・設定パスと一致 |
| MCPサーバー疎通確認済み | ローカルstdioで `initialize` と `tools/list` に成功 |
| Codexからの実検索は未検証 | Codexを再起動し、READMEの検索例で別途確認が必要 |

疎通確認では文献検索ツールを呼ばず、文献本文をCodexのコマンド引数に渡しません。`codex mcp get` の成功だけをMCP通信成功とは扱いません。

## Manual Setup

以下の接続例は、保存先の指定・環境変数がないmacOSでの既定値です。READMEのManual Setupで登録した場合は `~/.config/bibdesk-rag/config.toml`、ほかの場所に登録済みならその設定ファイルを指定してください。ウィザードが表示した実際の絶対パスを優先します。

| 保存するもの | 保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/Library/Application Support/bibdesk-rag/config.toml` |
| 検索索引 | `~/Library/Application Support/bibdesk-rag/index.sqlite3` |

GUI・CLI・設定ファイルのうち、いずれか1つの方法でMCPを登録します。

## コマンドで登録する

この方法にはCodex CLIが必要です。BibDesk RAG本体はCodex CLIなしで動作するため、Codex CLIは必須依存として自動インストールされません。まず次のコマンドで確認します。

```sh
codex --version
```

未導入なら、[HomebrewのCodex CLI](https://formulae.brew.sh/cask/codex)をインストールして確認します。すでに別の方法でCLIを導入している場合は、そのCLIを使い、コマンドが見つからなければ導入先とPATHを確認してください。

```sh
brew install --cask codex
codex --version
```

CLIを使わない場合は [アプリからの設定](#codex-cliがない場合) または [設定ファイルを使う方法](#設定ファイルを使う方法) に進みます。CLIで登録する場合は、Homebrewで導入した実行ファイルと設定ファイルを絶対パスで渡します。

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp" \
  --config "$HOME/Library/Application Support/bibdesk-rag/config.toml"
codex mcp get bibdesk-rag
```

`codex mcp add` はCodex側の設定を変更します。同名の登録がある場合は `codex mcp get bibdesk-rag` で内容を確認してから変更してください。このアプリのインストール・索引作成だけではCodexの設定を変更しません。`setup` で登録を承認した場合、または上の手動登録コマンドを実行した場合にだけ変更します。

Codexのアプリまたはセッションを再起動し、新しいチャットで検索します。`codex mcp list` は設定されたサーバー一覧であり、起動・検索の成功を証明するものではありません。Codexの `/mcp` で接続状態を確認できる環境では、`bibdesk-rag` が接続されていることも確認します。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

## Codex CLIがない場合

Macアプリで **設定 → 左側の「連携」にある「プラグイン」→ 右上の「追加」→「MCP サーバーを追加」** と進みます。2026年11月2日に確認した日本語画面の配置です。

`setup` が表示した実行ファイル・設定ファイルの絶対パスを使って、次の表の値を1つずつ入力・選択します。未実行の場合は①・②でパスを確認できます。「引数」は2つに分け、1件目、2件目の順に追加してください。

| 入力欄 | 入力・選択する値 |
| --- | --- |
| 名前 / Name | `bibdesk-rag` |
| 接続方式 / Transport | `STDIO` |
| コマンド / Command | 下の①で表示された1行 |
| 引数 / Arguments の1件目 | `--config` |
| 引数 / Arguments の2件目 | 下の②で表示された1行 |

① ターミナルで実行し、出力されたパスだけを「コマンド」欄へコピーします。

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

② ターミナルで実行し、出力されたパスだけを「引数」の2件目へコピーします。

```sh
printf '%s\n' "$HOME/Library/Application Support/bibdesk-rag/config.toml"
```

設定を別の場所に作った場合は、②にその保存先を指定します。GUIへコマンドそのものや `$(brew --prefix)`、`$HOME`、パスを囲む引用符は貼り付けません。「コマンド」欄には実行ファイルのパスだけを入れ、`--config` は引数の1件目に入れます。`/opt/homebrew` や `/usr/local` を決め打ちする必要はありません。環境変数や作業ディレクトリの欄がある場合は空欄のままで構いません。

保存後、「プラグイン」画面の **MCP** タブで `bibdesk-rag` を確認して接続を再起動し、新しいチャットでREADMEの検索例を試します。登録が表示されるだけでは、索引を検索できることの確認にはなりません。画面の配置は版によって変わる場合があります。[公式MCPガイド](https://learn.chatgpt.com/docs/extend/mcp) は接続方式と設定項目の参考にしてください。

## 設定ファイルを使う方法

Codex自身の標準ユーザー設定は `~/.codex/config.toml` です。これは **BibDesk RAGの設定ファイルとは別のファイル** です。既存の内容を保持し、同名のテーブルを重複させず、次の項目を追加または更新します。`command` は上の①で表示したパス、`args` の2つ目は②で表示したパスに置き換えてください。

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

`bibdesk-rag-mcp` の標準出力はMCP通信専用です。手で起動したままにせず、Codexに起動を任せてください。索引の作成・更新には、別途CLIで同じ `--config` を指定して `index` / `update` を使います。

## 接続の切り分け

1. `"$(brew --prefix)/bin/bibdesk-rag-mcp" --version` で実行ファイルを確認します。
2. `bibdesk-rag --config "$HOME/Library/Application Support/bibdesk-rag/config.toml" status --json` で、Codexに渡した設定から索引を読めるか確認します。独自の保存先ならそのパスに置き換えます。設定・索引がなければ同じ設定パスで `setup` を実行するか、READMEの手動手順で `init`・`index` を実行します。
3. `codex mcp get bibdesk-rag` で実行パスと `--config` 引数を確認します。設定画面やTOMLにシェル変数が残っていないか、古いCellarの版番号を指していないかも確認します。
4. MCP接続またはCodexを再起動して、新しいチャットでREADMEの検索例を実行します。CLIで `bibdesk-rag --config "$HOME/Library/Application Support/bibdesk-rag/config.toml" search "所蔵文献の語" --scope metadata --json` が成功し、MCPだけ失敗する場合はCodex側の起動エラーを確認します。

`Transport closed` が出た場合は、MCP接続を再起動して新しいチャットで試してください。継続する場合は上記1〜3で起動パスと設定を確認します。このエラーだけでは索引の破損や文献の不在を意味しません。

`auth_status: unsupported` はOAuth認証の対応状況を表す場合があります。このローカルstdioサーバーにOAuthログインやAPIキーは不要です。Codex自体の利用に必要なアカウントや設定は別途用意します。

書誌が見つかるのに本文が空の場合は、接続とは別に添付リンクと抽出状態を確認します。原本の移動・追加があった場合は `update` が必要です。変更を確実に照合するには `update --verify-hashes` を使います。本文の未抽出や検索結果0件だけで、関連資料が存在しないとは判断しません。

## 接続解除とアンインストール

### 1. Codexから接続を外す

CLIが使える場合は、削除する接続を確認して登録を外します。

```sh
codex mcp get bibdesk-rag
codex mcp remove bibdesk-rag
```

別の名前で登録した場合は、その名前を指定してください。CLIがない場合は、アプリの **設定 → プラグイン → MCP** タブから対象サーバーの登録を削除します。設定ファイルを手で編集した場合は、登録先の `config.toml` にある `[mcp_servers.bibdesk-rag]` テーブルと、そのサーバー配下の設定だけを取り除く方法もあります。ほかのサーバーや設定を残し、Codex全体の `~/.codex/` は削除しません。

その後、BibDesk RAGを使っていたCodexのアプリ・CLIセッションを終了し、MCPサーバーを停止してから次へ進みます。接続解除だけなら、ここで完了です。

### 2. BibDesk RAG本体を削除する

```sh
brew uninstall KentoYana/tap/bibdesk-rag
```

本体とHomebrew内の専用Python環境が削除されます。**元の `.bib` と添付ファイル、アプリデータ側の設定・索引は残ります。** 再インストールして同じ設定を指定すれば、保存済みの索引を使えます。共有しているPythonやライブラリ、ほかのソフトも配布している `KentoYana/tap` を手動で削除する必要はありません。

### 3. 設定・索引も不要な場合だけ削除する

設定と索引を残しておく場合は、この手順を省略します。削除する場合は、先に必要な設定を控え、実際の `config.toml` にある `database` の値で索引の保存先を確認してください。`bib` は原本の場所なので削除対象ではありません。

既定のセットアップまたはREADMEのManual Setupで登録した場合は、Finderの「移動 → フォルダへ移動」で次のフォルダをそれぞれ開き、中身を確認して対象ファイルをゴミ箱へ移動します。

| 開くフォルダ | 削除対象 |
| --- | --- |
| `~/Library/Application Support/bibdesk-rag/`（既定） | `config.toml`、`index.sqlite3` |
| `~/.config/bibdesk-rag/`（Manual Setupの例） | `config.toml` |
| `~/.local/share/bibdesk-rag/`（Manual Setupの例） | `index.sqlite3` |

`index.sqlite3-wal`、`index.sqlite3-shm`、`index.sqlite3-journal` が同じ索引の隣に残っていれば、それらも索引の補助ファイルです。原本の `.bib` や添付ファイルは削除しません。

保存先を指定しないv0.1.0・v0.1.1も、macOSでは上記の既定保存先を使います。`--config`、`init --data-dir`、`BIBDESK_RAG_CONFIG`、`BIBDESK_RAG_HOME`、`XDG_CONFIG_HOME`、`XDG_DATA_HOME` で別の保存先を指定した場合も含め、実際に使っている場所を確認してから削除します。ほかのデータと同居するフォルダをまとめて削除せず、確認した設定・索引とその補助ファイルだけをゴミ箱へ移動してください。`BIBDESK_RAG_*` をシェル設定に追加していた場合も、このツール用の設定だけを取り除きます。

再開するときは同じ保存先で `setup` を実行するか、設定を削除していれば `init`、索引を削除していれば `index` を実行します。削除したCodexのMCP接続も再登録してください。

### 4. Codex CLIも不要な場合

この用途のためにHomebrewでCodex CLIを導入し、ほかの用途でも使わなくなった場合だけ、次を実行できます。先に上記のMCP接続解除を済ませてください。

```sh
brew uninstall --cask codex
```

ほかの方法で導入したCLIには、その導入方法に対応する削除手順を使います。Codexアプリやほかのプロジェクトと共有する設定・認証情報・履歴を保持するため、`~/.codex/` の一括削除は行いません。
