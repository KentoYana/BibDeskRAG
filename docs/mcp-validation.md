[日本語](#japanese) | [English](#english)

<a id="english"></a>

# MCP interoperability validation

Validated locally on 2026-11-01 (Asia/Tokyo), macOS 26.7.2, Apple Silicon,
Python 3.12.13, bibdesk-rag 0.1.0.

## Official SDK client

The official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
2.3.0 and `mcp-types` 2.3.0 were installed with pip into the isolated,
Git-ignored `.venv-mcp-client`. They are validation dependencies only; neither
was added to the application's runtime environment or package requirements.
The SDK's installed `Client`, `StdioServerParameters`, and transport/negotiation
implementation were inspected alongside its [official documentation](https://py.sdk.modelcontextprotocol.io/).

Run the reproducible check from the repository root after the ordinary app
development installation:

```sh
.venv/bin/python -m venv .venv-mcp-client
.venv-mcp-client/bin/python -m pip install "mcp==2.3.0"
.venv-mcp-client/bin/python tools/validate_mcp_sdk.py --app-python .venv/bin/python
```

The helper generates a temporary `.bib`, supplementary CSV, configuration and
index; launches the installed application in a real stdio subprocess; and uses
the SDK's default `auto` negotiation. It succeeded with protocol `2025-06-18`.
The client automatically fell back from modern discovery to the server's
supported initialize handshake; no forced legacy mode was necessary.

| Check | Result |
| --- | --- |
| Initialization and six tool descriptors | Passed; all tools marked read-only |
| `search_papers` | Exact DOI returned the expected citekey |
| `search_fulltext` | Returned supplementary CSV path, row 2 and chunk ID |
| `get_paper` | Returned the expected DOI and metadata |
| `get_attachments` | Returned the correct local file path |
| `get_chunk` | Returned source text and matching citation |
| `build_context` | Returned bounded evidence and source locations |
| Invalid `max_chars` | Returned a tool error accepted by the SDK |
| Source/index SHA-256 before and after calls | Identical |

No LLM or external content API was called. Package installation used PyPI;
the interoperability calls themselves used local subprocess stdin/stdout.

## Codex configuration recognition

The installed `codex-cli 0.166.0-alpha.5.1` successfully recognized the server
through temporary command-line `-c` overrides and `codex mcp list --json`.
The reported entry was enabled with transport type `stdio`, the absolute
`bibdesk-rag-mcp` executable, and the temporary app configuration argument.
`auth_status: unsupported` refers to OAuth support, which this local stdio
server does not require.

The invocation had this form, substituting the actual executable and temporary
application config paths:

```sh
codex \
  -c 'mcp_servers.bibdesk-rag-validation.command="/absolute/path/to/bibdesk-rag-mcp"' \
  -c 'mcp_servers.bibdesk-rag-validation.args=["--config","/temporary/config.toml"]' \
  mcp list --json
```

This was a configuration-recognition check, not an end-to-end Codex model tool
call. `mcp list` lists configured servers; it does not establish a successful
tool invocation. The actual stdio handshake and calls were verified with the
official SDK above. See the [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for the distinction between configured servers and active connections.

No Codex user/project config was written, no `CODEX_HOME` override was used,
and the SHA-256 of the existing global config was unchanged. No Codex model
request, login, or persistent MCP registration was performed.

## Response and parser bounds

Regression tests verify that MCP context results retain citation fields but
omit the duplicate excerpt already contained in `context`. A 90,000-character
synthetic context fits within the 120,000-character JSON content limit. List
truncation in `get_paper` is explicitly identified in `truncated_fields`.
Outputs beyond the final response limit produce a valid JSON tool error;
serialized JSON is never cut in the middle.

The supplementary BibTeX macro evaluator was separately exercised with cyclic
definitions, a 40-level reference chain and a concatenated value exceeding
1,000,000 characters. All three were rejected with clear `ValueError`s. The
code limits recursive expansion to 32 levels, performs only string parsing,
and never executes TeX or Python. A regression test confirms that `\\input`
inside an abstract does not read an unrelated file; the LaTeX decoder's file
input facility remains disabled.

The focused `test_bibdesk.py` and `test_mcp.py` suites passed 29 tests after
these checks. This initial SDK run did not establish a Codex desktop session
connection, an Intel Mac run, or an installed Homebrew build. The subsequent
Codex check is recorded below; Homebrew evidence is in
[homebrew-validation.md](homebrew-validation.md).

## Subsequent Codex desktop verification

Later on 2026-11-01, the installed Homebrew executable was registered as the
`bibdesk-rag` stdio MCP server in Codex. An actual Codex conversation invoked
`search_papers` for `RecQ`, then `search_fulltext` restricted to the returned
paper. The result contained the matching citekey, original PDF path, PDF page
number and chunk ID. This was a real tool invocation, not just `codex mcp list`
or a standalone SDK client. No model request was initiated by the package itself.

The user's library, linked attachments, application configuration and index were
checked with SHA-256 before and after the connection work and were unchanged.
These real-library checks are separate from the generated-fixture tests; no
personal library, PDF excerpt, local configuration or index is shipped in the
distribution. A local plugin was also tested, but it is not required for the
documented direct Codex MCP connection.

Ordinary Chat mode in the ChatGPT Mac app is outside the supported setup in
this release. The tested local plugin did not appear there in the user's check,
and no successful ordinary-Chat tool invocation is claimed. Intel Mac execution
also remains unverified.

---

<a id="japanese"></a>

# MCP相互運用検証

2026-11-01（Asia/Tokyo）、macOS 26.7.2、Apple Silicon、Python 3.12.13、bibdesk-rag 0.1.0でローカル検証しました。

## 公式SDKクライアント

公式 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 2.3.0と `mcp-types` 2.3.0を、Git管理外の隔離環境 `.venv-mcp-client` にpipで導入しました。検証専用の依存であり、アプリの実行環境・パッケージ要件には追加していません。インストール済み `Client`、`StdioServerParameters`、通信・ネゴシエーション実装を [公式文書](https://py.sdk.modelcontextprotocol.io/) と合わせて確認しました。

通常の開発用インストール後、リポジトリのルートで再現できます。

```sh
.venv/bin/python -m venv .venv-mcp-client
.venv-mcp-client/bin/python -m pip install "mcp==2.3.0"
.venv-mcp-client/bin/python tools/validate_mcp_sdk.py --app-python .venv/bin/python
```

補助ツールは一時 `.bib`、補足CSV、設定、索引を生成し、インストール済みアプリを実際のstdioサブプロセスとして起動し、SDK既定の `auto` ネゴシエーションを使います。プロトコル `2025-06-18` で成功しました。クライアントは新しいdiscoveryからサーバー対応のinitializeへ自動フォールバックし、旧方式の強制は不要でした。

| 検査 | 結果 |
| --- | --- |
| 初期化と6ツール定義 | 成功。すべて読み取り専用 |
| `search_papers` | DOI完全一致で期待したcitekeyを取得 |
| `search_fulltext` | 補足CSVパス・2行目・chunk IDを取得 |
| `get_paper` | 期待したDOI・書誌情報を取得 |
| `get_attachments` | 正しいローカルパスを取得 |
| `get_chunk` | 原文と一致する引用を取得 |
| `build_context` | 上限付きの証拠と出典位置を取得 |
| 不正な `max_chars` | SDKが受理するツールエラーを返却 |
| 呼出し前後の原本・索引SHA-256 | 一致 |

LLMや外部コンテンツAPIは呼んでいません。パッケージ導入はPyPIを使いましたが、相互運用の呼出し自体はローカル子プロセスの標準入出力です。

## Codex設定の認識

インストール済み `codex-cli 0.166.0-alpha.5.1` は、一時コマンドライン `-c` 上書きと `codex mcp list --json` でサーバーを認識しました。有効な `stdio` 登録として、`bibdesk-rag-mcp` の絶対パスと一時設定引数を報告しました。`auth_status: unsupported` はOAuth対応を指し、このローカルstdioサーバーには不要です。

実行形は次のとおりで、実際の実行ファイル・一時設定パスに置き換えました。

```sh
codex \
  -c 'mcp_servers.bibdesk-rag-validation.command="/absolute/path/to/bibdesk-rag-mcp"' \
  -c 'mcp_servers.bibdesk-rag-validation.args=["--config","/temporary/config.toml"]' \
  mcp list --json
```

これは設定認識の検証であり、Codexモデルからの一連のツール呼出しではありません。`mcp list` は設定済みサーバーを列挙するだけです。実際のstdio初期化・呼出しは上記公式SDKで確認しました。設定と接続の区別は [公式Codex MCP文書](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) を参照してください。

Codexの利用者・プロジェクト設定へ書き込まず、`CODEX_HOME` も上書きせず、既存global設定のSHA-256は不変でした。Codexモデル要求、ログイン、永続MCP登録は行っていません。

## 応答とパーサーの上限

回帰テストは、MCP contextの引用欄を保持しつつ、`context` に含まれる抜粋の重複を除くことを確認します。90,000文字の合成contextは120,000文字のJSON内容上限に収まり、`get_paper` のリスト省略は `truncated_fields` に明示されます。最終応答上限を超えた場合は正しいJSONツールエラーを返し、シリアライズ途中でJSONを切りません。

補助BibTeXマクロ評価では循環定義、40段の参照連鎖、1,000,000文字を超える連結値を別途検査し、すべて明確な `ValueError` で拒否しました。再帰展開は32段までで、文字列解析のみを行い、TeX/Pythonを実行しません。abstract中の `\\input` が無関係なファイルを読まない回帰テストがあり、LaTeXデコーダーのファイル入力機能は無効です。

これらの確認後、`test_bibdesk.py` と `test_mcp.py` の29テストが成功しました。初期SDK実行はCodexデスクトップ接続、Intel Mac実行、Homebrew版の導入検証ではありません。後日のCodex検証は下記、Homebrewの証拠は [Homebrew検証](homebrew-validation.md#japanese) にあります。

## 後日のCodexデスクトップ検証

同じ2026-11-01の後刻、インストール済みHomebrew実行ファイルをCodexに `bibdesk-rag` stdio MCPとして登録しました。実際のCodex会話で `search_papers` に `RecQ` を渡し、次に返された文献へ限定して `search_fulltext` を呼びました。結果は一致するcitekey、元PDFパス、PDFページ番号、chunk IDを含みました。これは単なる `codex mcp list` や単独SDKクライアントではなく、実際のツール呼出しです。パッケージ自体はモデル要求を開始していません。

接続作業前後に、利用者ライブラリ、リンク添付、アプリ設定、索引のSHA-256を確認し、すべて不変でした。実ライブラリ検証は生成fixtureテストとは別です。個人ライブラリ、PDF抜粋、ローカル設定、索引は配布物に含めません。ローカルプラグインも試しましたが、文書化したCodex直接MCP接続には不要です。

ChatGPT Macアプリの通常Chatはこのリリースの対応範囲外です。試したローカルプラグインは利用者の確認時に通常Chatへ表示されず、通常Chatでの呼出し成功は主張していません。Intel Macでの実行も未検証です。
