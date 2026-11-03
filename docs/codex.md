[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# Codex接続ガイド

[READMEの導入手順](../README.md#homebrewで導入してcodexから使う) でライブラリを登録し、索引を作成してから接続します。このガイドはMac上で動くCodexのローカルMCP接続を扱います。ChatGPTの通常Chat・Web版やCodexのクラウド環境から、Mac内の索引へ接続する手順ではありません。

以下はv0.3.0以降の接続手順です。旧CLI構文からの変更は [移行ガイド](usage.md#旧コマンドからの移行) を参照してください。既存のMCP登録にある `--config PATH` は互換用として引き続き使用できます。

## 対話型セットアップ（推奨）

```sh
bibdesk-rag --setup
```

対話型セットアップは `--setup` で開始します。別の場所に既存設定がある場合は、先に `bibdesk-rag --config use "/absolute/path/to/config.toml"` で選んでから `bibdesk-rag --setup` を実行してください。一度だけ使う場合は `bibdesk-rag --temp PATH --setup` で、保存済みの選択を変更せずに実行できます。

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

新規の既定保存先は次のとおりです。ほかの場所に登録済みなら、その設定ファイルを使用します。`bibdesk-rag --config path` またはウィザードが表示する実際の絶対パスを確認してください。

| 保存するもの | 保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

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
  --temp "$(bibdesk-rag --config path)"
codex mcp get bibdesk-rag
```

`codex mcp add` はCodex側の設定を変更します。同名の登録がある場合は `codex mcp get bibdesk-rag` で内容を確認してから変更してください。このアプリのインストール・索引作成だけではCodexの設定を変更しません。`--setup` で登録を承認した場合、または上の手動登録コマンドを実行した場合にだけ変更します。

Codexのアプリまたはセッションを再起動し、新しいチャットで検索します。`codex mcp list` は設定されたサーバー一覧であり、起動・検索の成功を証明するものではありません。Codexの `/mcp` で接続状態を確認できる環境では、`bibdesk-rag` が接続されていることも確認します。[OpenAI公式MCP設定手順](https://learn.chatgpt.com/docs/extend/mcp)

## Codex CLIがない場合

Macアプリで **設定 → 左側の「連携」にある「プラグイン」→ 右上の「追加」→「MCP サーバーを追加」** と進みます。2026年11月2日に確認した日本語画面の配置です。

`--setup` が表示した実行ファイル・設定ファイルの絶対パスを使って、次の表の値を1つずつ入力・選択します。未実行の場合は①・②でパスを確認できます。「引数」は2つに分け、1件目、2件目の順に追加してください。

| 入力欄 | 入力・選択する値 |
| --- | --- |
| 名前 / Name | `bibdesk-rag` |
| 接続方式 / Transport | `STDIO` |
| コマンド / Command | 下の①で表示された1行 |
| 引数 / Arguments の1件目 | `--temp` |
| 引数 / Arguments の2件目 | 下の②で表示された1行 |

① ターミナルで実行し、出力されたパスだけを「コマンド」欄へコピーします。

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

② ターミナルで実行し、出力されたパスだけを「引数」の2件目へコピーします。

```sh
bibdesk-rag --config path
```

`--config path` は選択中の設定パスを表示します。別の設定を確認するには `bibdesk-rag --temp PATH --config path` と指定します。GUIへコマンドそのものや `$(brew --prefix)`、`$HOME`、パスを囲む引用符は貼り付けません。「コマンド」欄には実行ファイルのパスだけを入れ、`--temp` は引数の1件目に入れます。`/opt/homebrew` や `/usr/local` を決め打ちする必要はありません。環境変数や作業ディレクトリの欄がある場合は空欄のままで構いません。

保存後、「プラグイン」画面の **MCP** タブで `bibdesk-rag` を確認して接続を再起動し、新しいチャットでREADMEの検索例を試します。登録が表示されるだけでは、索引を検索できることの確認にはなりません。画面の配置は版によって変わる場合があります。[公式MCPガイド](https://learn.chatgpt.com/docs/extend/mcp) は接続方式と設定項目の参考にしてください。

## 設定ファイルを使う方法

Codex自身の標準ユーザー設定は `~/.codex/config.toml` です。これは **BibDesk RAGの設定ファイルとは別のファイル** です。既存の内容を保持し、同名のテーブルを重複させず、次の項目を追加または更新します。`command` は上の①で表示したパス、`args` の2つ目は②で表示したパスに置き換えてください。

```toml
[mcp_servers.bibdesk-rag]
command = "/absolute/homebrew/prefix/bin/bibdesk-rag-mcp"
args = ["--temp", "/absolute/path/to/bibdesk-rag/config.toml"]
```

ソースから導入した場合は `command` を `/absolute/path/to/BibDeskRAG/.venv/bin/bibdesk-rag-mcp` にします。GUIアプリのPATHや、ターミナルだけで設定した環境変数の継承に頼らず接続できます。

設定を分けて複数のライブラリを使う場合は、ライブラリごとに設定と索引を作り、Codexにも `bibdesk-rag-project-a` など別のサーバー名で登録します。[保存先の指定](usage.md#ライブラリ登録と索引化)

`--temp` はMCPサーバーの起動単位で設定を指定するため、登録先の設定に固定されます。CLIで `--config use PATH` を実行しても、既存のCodex登録を変更しません。MCPもCLIの保存済み選択に従わせたい場合は、登録時の `--temp` とパスを省略します。同じ設定用ディレクトリを使用する必要があり、ターミナルだけで指定した `BIBDESK_RAG_HOME` や `XDG_CONFIG_HOME` はGUIに引き継がれない場合があります。設定を固定する場合は、このガイドのように絶対パスを登録してください。

以前のMCP登録にある `--config` は、`bibdesk-rag-mcp` に限り互換用として受け付けます。同じ設定を指す登録は `--setup` で書き換えません。通常の `bibdesk-rag` の `--config` は設定管理用の操作引数を受け取り、一時的な設定ファイルの指定には `--temp` を使います。

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

`bibdesk-rag-mcp` の標準出力はMCP通信専用です。手で起動したままにせず、Codexに起動を任せてください。索引の作成・差分更新にはCLIの `--index update`、全件再構築には `--index rebuild` を使います。`--config path` とCodexの登録先が一致していれば、CLIで設定パスを指定し直す必要はありません。

## 接続の切り分け

1. `"$(brew --prefix)/bin/bibdesk-rag-mcp" --version` で実行ファイルを確認します。
2. `bibdesk-rag --config show` で設定と索引の場所を確認し、`bibdesk-rag --index status --format json` で索引を読めるか確認します。Codexに別の設定を登録している場合は `bibdesk-rag --temp PATH --index status --format json` で照合します。設定・索引がなければ同じ設定パスで `--setup` を実行するか、READMEの手動手順で `--config create`・`--index update` を実行します。
3. `codex mcp get bibdesk-rag` で実行パスと `--temp` 引数を確認します。設定画面やTOMLにシェル変数が残っていないか、古いCellarの版番号を指していないかも確認します。
4. MCP接続またはCodexを再起動して、新しいチャットでREADMEの検索例を実行します。同じ設定を使ったCLIの `bibdesk-rag --paper search "所蔵文献の語" --scope metadata --format json` が成功し、MCPだけ失敗する場合はCodex側の起動エラーを確認します。

`Transport closed` が出た場合は、MCP接続を再起動して新しいチャットで試してください。継続する場合は上記1〜3で起動パスと設定を確認します。このエラーだけでは索引の破損や文献の不在を意味しません。

`auth_status: unsupported` はOAuth認証の対応状況を表す場合があります。このローカルstdioサーバーにOAuthログインやAPIキーは不要です。Codex自体の利用に必要なアカウントや設定は別途用意します。

書誌が見つかるのに本文が空の場合は、接続とは別に添付リンクと抽出状態を確認します。原本の移動・追加があった場合は `--index update` が必要です。変更を確実に照合するには `--index update --verify-hashes` を使います。本文の未抽出や検索結果0件だけで、関連資料が存在しないとは判断しません。

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
| `~/.config/bibdesk-rag/`（既定） | `config.toml`、設定選択を記録する `active-config.json` |
| `~/.local/share/bibdesk-rag/`（既定） | `index.sqlite3` |

`index.sqlite3-wal`、`index.sqlite3-shm`、`index.sqlite3-journal` が同じ索引の隣に残っていれば、それらも索引の補助ファイルです。原本の `.bib` や添付ファイルは削除しません。

`--temp`、`--config create --data-dir`、`BIBDESK_RAG_CONFIG`、`BIBDESK_RAG_HOME`、`XDG_CONFIG_HOME`、`XDG_DATA_HOME` で別の保存先を指定した場合も含め、実際に使っている場所を確認してから削除します。ほかのデータと同居するフォルダをまとめて削除せず、確認した設定・索引とその補助ファイル、不要な設定選択の記録だけをゴミ箱へ移動してください。`BIBDESK_RAG_*` をシェル設定に追加していた場合も、このツール用の設定だけを取り除きます。

再開するときは同じ保存先で `--setup` を実行するか、設定を削除していれば `--config create`、索引を削除していれば `--index update` を実行します。削除したCodexのMCP接続も再登録してください。

### 4. Codex CLIも不要な場合

この用途のためにHomebrewでCodex CLIを導入し、ほかの用途でも使わなくなった場合だけ、次を実行できます。先に上記のMCP接続解除を済ませてください。

```sh
brew uninstall --cask codex
```

ほかの方法で導入したCLIには、その導入方法に対応する削除手順を使います。Codexアプリやほかのプロジェクトと共有する設定・認証情報・履歴を保持するため、`~/.codex/` の一括削除は行いません。

---

<a id="english"></a>

# Codex connection guide

Register the library and build its index using the [README](../README.md#install-with-homebrew-and-connect-to-codex) before connecting. This guide covers local MCP in Codex running on the Mac. It does not describe connecting ordinary Chat/ChatGPT Web or Codex cloud environments to the Mac's index.

These instructions apply to v0.3.0 and later. See [Migration](usage.md#migrating-from-older-commands) for CLI changes. Existing MCP registrations using `--config PATH` remain compatible.

## Interactive setup (recommended)

```sh
bibdesk-rag --setup
```

Start with `--setup`. To reuse configuration elsewhere, first run `bibdesk-rag --config use "/absolute/path/to/config.toml"`, then setup. For a one-time choice without changing the saved selection, use `bibdesk-rag --temp PATH --setup`.

After library registration/index creation, the wizard offers MCP registration if Codex CLI exists. Only after approval does it register the detected `bibdesk-rag-mcp` executable and configuration using absolute paths. Matching registrations are retained; conflicting or indeterminate registrations are not changed. Other Codex settings and servers are untouched.

Without the CLI, after skipping registration or after registration failure, the completed index is still usable from the CLI. Enter the displayed manual connection details in [application settings](#without-codex-cli). If the executable cannot be found, check package installation/PATH and rerun. Codex CLI is never automatically installed.

Completion reports distinguish these checks:

| Reported state | Verified scope |
| --- | --- |
| Configuration/index available | Configuration read; SQLite opened read-only and counts obtained |
| MCP registered | Codex registration matches executable/configuration paths |
| Local MCP server verified | Local stdio `initialize` and `tools/list` succeeded |
| Actual Codex search unverified | Restart Codex and separately try the README search example |

The handshake check does not call paper-search tools or pass paper text through Codex command arguments. Successful `codex mcp get` alone is not successful MCP communication.

## Manual setup — English

New defaults are below. If already registered elsewhere, use that configuration. Check the actual absolute path with `bibdesk-rag --config path` or the wizard.

| Data | Location |
| --- | --- |
| BibDesk RAG configuration | `~/.config/bibdesk-rag/config.toml` |
| Search index | `~/.local/share/bibdesk-rag/index.sqlite3` |

Choose one registration method: GUI, CLI or configuration file.

## Register using commands

This method requires Codex CLI. BibDesk RAG itself works without it, and does not install it as a required dependency. Check availability:

```sh
codex --version
```

If absent, install [Codex CLI with Homebrew](https://formulae.brew.sh/cask/codex) and verify. If installed another way, use that CLI; check its location/PATH if it cannot be found.

```sh
brew install --cask codex
codex --version
```

To avoid CLI registration, use [application settings](#without-codex-cli) or the [configuration file](#using-the-configuration-file). For CLI registration, pass absolute Homebrew executable/configuration paths:

```sh
codex mcp add bibdesk-rag -- "$(brew --prefix)/bin/bibdesk-rag-mcp" \
  --temp "$(bibdesk-rag --config path)"
codex mcp get bibdesk-rag
```

`codex mcp add` changes Codex settings. Inspect any existing registration with `codex mcp get bibdesk-rag` before changing it. Installing/indexing alone does not change Codex settings; approval during setup or the explicit registration command does.

Restart the Codex application/session and search in a new chat. `codex mcp list` lists configuration; it does not prove successful startup/search. Where Codex supports `/mcp`, also check that `bibdesk-rag` is connected. See the [official MCP guide](https://learn.chatgpt.com/docs/extend/mcp).

## Without Codex CLI

In the Mac application, go to **Settings → Plugins under “Integrations” on the left → Add at the upper right → Add MCP server**. This is the Japanese UI layout observed on November 2, 2026.

Use the absolute executable/configuration paths shown by `--setup`. If setup has not run, obtain them with ① and ② below. Enter each field separately, adding two distinct arguments in order:

| Field | Value |
| --- | --- |
| Name | `bibdesk-rag` |
| Transport | `STDIO` |
| Command | The single path printed by ① |
| Argument 1 | `--temp` |
| Argument 2 | The single path printed by ② |

① Run in a terminal; copy only the printed path into Command:

```sh
printf '%s\n' "$(brew --prefix)/bin/bibdesk-rag-mcp"
```

② Run in a terminal; copy only the printed path into Argument 2:

```sh
bibdesk-rag --config path
```

`--config path` prints the selected configuration. To inspect another, use `bibdesk-rag --temp PATH --config path`. Do not paste shell commands, `$(brew --prefix)`, `$HOME` or surrounding quotes into GUI fields. Command contains only the executable path; `--temp` is Argument 1. There is no need to assume `/opt/homebrew` or `/usr/local`. Environment-variable/working-directory fields can stay empty.

After saving, check `bibdesk-rag` in Plugins → **MCP**, restart the connection and try the README search in a new chat. A displayed registration alone does not verify index searches. UI layout may vary by version; consult the [official MCP guide](https://learn.chatgpt.com/docs/extend/mcp) for transport/configuration concepts.

## Using the configuration file

Codex's default user configuration is `~/.codex/config.toml`, **a different file from BibDesk RAG's configuration**. Preserve existing settings and add/update the following without duplicating table names. Replace `command` with the path from ① and the second `args` item with the path from ②.

```toml
[mcp_servers.bibdesk-rag]
command = "/absolute/homebrew/prefix/bin/bibdesk-rag-mcp"
args = ["--temp", "/absolute/path/to/bibdesk-rag/config.toml"]
```

For source installations, use `/absolute/path/to/BibDeskRAG/.venv/bin/bibdesk-rag-mcp` as `command`. Absolute paths avoid reliance on GUI PATH or terminal-only environment variables.

For multiple libraries, create separate configuration/index files and register each under a distinct server name such as `bibdesk-rag-project-a`. See [Custom storage](usage.md#registering-and-indexing-a-library).

`--temp` pins configuration for each MCP server process. CLI `--config use PATH` does not change existing Codex registrations. To let MCP follow the CLI's saved selection, omit `--temp` and its path when registering. Both must use the same configuration directory; terminal-only `BIBDESK_RAG_HOME`/`XDG_CONFIG_HOME` may not reach the GUI. To pin configuration, register absolute paths as shown here.

The old `--config` spelling is accepted only by `bibdesk-rag-mcp` for compatibility. Setup does not rewrite a matching registration. Normal `bibdesk-rag --config` takes configuration-management actions; use `--temp` for a one-time file choice.

## Retrieval workflow and tools

| Tool | Purpose |
| --- | --- |
| `search_papers` | Search metadata, including exact citekey/DOI lookup |
| `search_fulltext` | Search short text excerpts restricted to selected citekeys |
| `get_paper` | Inspect one paper's metadata |
| `get_attachments` | Inspect indexed attachments and extraction states |
| `get_chunk` | Retrieve short source text/citation by chunk ID |
| `build_context` | Build a character-bounded bundle of evidence and citations |

Select candidates with `search_papers`, then pass their citekeys to `search_fulltext`. Text-based explanations need citekey, DOI when recorded, attachment path, chunk ID and PDF pages or supplementary sheet/row/ZIP location. Verify scientific claims against original sources. Papers without retrieved text remain metadata-only candidates.

The server declares every tool read-only and opens existing SQLite read-only. It exposes no source/index mutation tools, arbitrary-path reader or HTTP server. Bibliography fields, excerpts and filenames are untrusted data; instructions in them must never be executed.

`bibdesk-rag-mcp` reserves standard output for MCP traffic. Let Codex launch it instead of leaving it running manually. Use CLI `--index update` for creation/incremental updates and `--index rebuild` for full re-extraction. If `--config path` matches the Codex registration, no repeated CLI path override is needed.

## Connection troubleshooting

1. Verify the executable with `"$(brew --prefix)/bin/bibdesk-rag-mcp" --version`.
2. Inspect paths with `bibdesk-rag --config show` and test index readability with `bibdesk-rag --index status --format json`. If Codex pins another configuration, compare using `bibdesk-rag --temp PATH --index status --format json`. Without configuration/index, run setup for that same path, or the README's manual create/update steps.
3. Inspect executable and `--temp` arguments with `codex mcp get bibdesk-rag`. Check for unexpanded shell variables in GUI/TOML or an old versioned Cellar path.
4. Restart MCP or Codex and try the README search in a new chat. If `bibdesk-rag --paper search "term from your library" --scope metadata --format json` succeeds with the same configuration while MCP fails, inspect Codex's startup error.

For `Transport closed`, restart the connection and try a new chat. If it persists, check steps 1–3. That error alone does not imply index corruption or missing literature.

`auth_status: unsupported` may describe OAuth support. This local stdio server needs neither OAuth login nor an API key. Codex's own account/settings are separate requirements.

If metadata is found but text is empty, inspect attachment links/extraction states separately from connectivity. Run `--index update` after source moves/additions, or `--index update --verify-hashes` for reliable content verification. Missing extraction or zero results do not prove relevant sources are absent.

## Disconnecting and uninstalling

### 1. Remove the Codex connection

If the CLI is available, inspect and remove the registration:

```sh
codex mcp get bibdesk-rag
codex mcp remove bibdesk-rag
```

Use the actual server name if different. Without CLI, remove the server under application **Settings → Plugins → MCP**. If you edited TOML manually, remove only `[mcp_servers.bibdesk-rag]` and that server's settings. Preserve other servers/settings; do not delete the entire `~/.codex/` directory.

Close Codex application/CLI sessions using BibDesk RAG to stop MCP servers before proceeding. If disconnecting only, you are done.

### 2. Remove BibDesk RAG

```sh
brew uninstall KentoYana/tap/bibdesk-rag
```

This removes the application and its dedicated Homebrew Python environment. **Original `.bib` files, attachments and application-data configuration/index remain.** Reinstalling with the same configuration can reuse the saved index. There is no need to manually remove shared Python/libraries or the `KentoYana/tap` tap, which may distribute other software.

### 3. Remove configuration/index only if unwanted

Skip this step to retain application data. Before deletion, record any settings needed later and inspect `database` in the actual `config.toml`. `bib` identifies original source data and is not a deletion target.

With default setup or README Manual Setup, use Finder's Go → Go to Folder to inspect each location and move the intended files to Trash:

| Folder | Files to remove |
| --- | --- |
| `~/.config/bibdesk-rag/` (default) | `config.toml`, `active-config.json` (saved selection) |
| `~/.local/share/bibdesk-rag/` (default) | `index.sqlite3` |

Adjacent `index.sqlite3-wal`, `index.sqlite3-shm` and `index.sqlite3-journal` belong to the same derived index. Never delete original `.bib` files or attachments.

Check actual locations first, including overrides from `--temp`, `--config create --data-dir`, `BIBDESK_RAG_CONFIG`, `BIBDESK_RAG_HOME`, `XDG_CONFIG_HOME` or `XDG_DATA_HOME`. Do not delete whole shared folders. Remove only verified configuration/index files, their sidecars and unwanted saved-selection records. If shell settings contain `BIBDESK_RAG_*`, remove only this tool's entries.

To resume, run `--setup` at the same location, or `--config create` if configuration was removed and `--index update` if the index was removed. Restore any deleted Codex MCP registration too.

### 4. Optionally remove Codex CLI

Only if installed with Homebrew solely for this purpose and no longer used elsewhere, run the following after removing the MCP connection:

```sh
brew uninstall --cask codex
```

For other installation methods, use their corresponding removal procedure. Preserve configuration, credentials and history shared with Codex and other projects; do not delete all of `~/.codex/`.
