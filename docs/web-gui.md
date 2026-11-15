[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# ローカル検索GUI

既存の設定と索引を読み取り専用で利用する英語UIです。ソースからは
`.venv/bin/bibdesk-rag` を使います。Homebrew版でも同じCLIオプションを使用できます。

```sh
bibdesk-rag --web
bibdesk-rag --web --port 8765 --no-browser
bibdesk-rag --temp "/absolute/path/config.toml" --web
bibdesk-rag --web-open='RecQ helicase'
bibdesk-rag --web-open='相同組換え'
bibdesk-rag --web-open=''
bibdesk-rag --web-stop
```

`--web` はフォアグラウンド起動でCtrl+C終了です。準備完了後に既定ブラウザを開きます。
`--no-browser` はURL表示のみです。127.0.0.1以外の待受アドレスは指定できません。
ポート未指定では8765を試し、使用中ならOSが割り当てる空きポートへ切り替えます。
明示したポートの競合はエラーです。ブラウザ起動失敗でもサーバーは継続します。

`--web-open QUERY` は同じ設定のサーバーを再利用し、なければバックグラウンドで起動して、
独立した検索タブを開きます。空文字列なら自動検索しません。先頭がハイフンの検索語は
`--web-open='-query'` のように `=` を使います。ログイン項目・launchd・brew servicesは登録しません。
`--web-stop` は当該設定の所有サーバーへ認証付きで正常終了を要求します。
通常の設定優先順位（`--temp` → 環境変数 → 保存済み選択 → 既定）を維持し、
起動後は設定を固定します。別ライブラリには別のサーバーを使います。

未設定なら `bibdesk-rag --setup`、索引がなければ同じ設定で
`bibdesk-rag --index update` を実行してください。GUIでは書誌・設定の編集、索引更新、
モデル取得、OCR、回答生成を行いません。外部CDNやWebフォントは使用しません。

## 検索条件と結果

KeywordのMetadata / Full text / BothはCLIのmetadata / fulltext / allと同じです。
Author・Year（単年）・DOIはMetadata専用、Metadata queryはBoth専用です。
Citekeyは1行1件で、Metadataでは1件のみ、本文検索では最大100件です。
Metadata queryとCitekeyは併用できません。DOIだけの検索も可能です。
Resultsは1〜100（既定10）、Excerpts per paperは1〜10（既定2）です。
Full text / BothのResultsは返されるヒットの上限であり、文献数ではありません。
同じ文献をカードへまとめても順位・ヒット数を変更せず、追加検索で水増ししません。

SemanticはTitle・Abstractのみが対象で、Results以外の条件を送信しません。
初回はローカルモデル読み込みに時間がかかる場合があり、プロセス内で再利用します。
未設定・モデル未取得・索引不整合はエラーとして表示し、Keywordへ切り替えません。
設定には既存の `--setup` と[意味検索ガイド](semantic-search.md)を使います。
日本語入力は保持し、自動翻訳しません。スコアは確信度・確率ではありません。

結果には書誌、全文Abstract、取得できた抜粋、chunk ID、ページ・行・ZIP内位置、
添付ごとの抽出状態と欠損状態を表示します。原文をHTMLとして実行しません。
Copy citekey / Copy BibTeXはクリップボードへコピーし、Open DOIだけが正規化した
`https://doi.org/…` を開きます。任意の書誌URLを実行可能リンクにしません。
検索語・文献内容をURL、localStorage、サーバーの永続履歴へ保存しません。
初期検索はメモリ上に60秒間保持し、URLフラグメントの一回限りの要求IDで受け渡します。
画面は読み取り後にフラグメントを除去します。期限切れなら通常の検索を行ってください。

## Skim

PDFはブラウザへ配信せず、macOSのSkimで開きます。Skimが必要です。
登録済み添付IDだけをPOSTで受け取り、選択ライブラリの通常のPDFファイルを
`/usr/bin/open -a Skim` の引数配列で開きます。欠損・非PDF・不正IDは拒否します。
ZIP内PDFをクリック時に展開したり、移動したファイルを走査したりしません。
リンクが変わった場合はBibDeskで確認後、CLIで索引を更新してください。

ページ指定は同梱の固定AppleScriptへ絶対パスと正の整数をargvとして渡します。
Skimのdocumentをパスで特定し、`go … to page …` で移動し、対象文書を前面化します。
PDF先頭を1とする物理ページ番号で、印刷ページ番号とは異なる場合があります。
macOSがAutomation許可を求めた場合は利用者が判断してください。権限の自動変更はしません。
ページ移動が失敗しても、PDFを開けた場合はその旨と参照ページを表示します。
公式資料：[Skim scripting](https://skim-app.sourceforge.io/manual/SkimHelp_45.html)。
この実装では実機の `Skim.sdef` と同梱displaylineのdocument選択方式も参照しました。

## ローカル実行情報と検証

実行情報は設定のSQLiteと同じアプリデータディレクトリ内の `web-runtime/` に置きます。
ディレクトリ0700、設定別ロックと情報ファイル0600で、設定パス・ポート・起動ID・
所有トークンだけを保持します。PIDだけでは所有判定しません。
Host・Origin・CSRFを検証し、CLI専用APIには別トークンを要求します。
リクエスト本文は32 KiB、同時ワーカーは4、初期検索は最大100件・60秒に制限します。

自動テストは生成fixtureのみを使います。Safariで検索・Abstract・複数添付表示と
Skim起動を確認しました。ページ指定オープンは修正後、利用者による動作確認済みです。
別PDFが前面の場合やAutomation拒否を含む全受け入れ条件の網羅確認とは区別しています。

<a id="english"></a>

# Local search GUI

The English-only GUI reads the existing selected configuration and index.
Use `.venv/bin/bibdesk-rag` from a source checkout; the Homebrew package supports the same options.

```sh
bibdesk-rag --web
bibdesk-rag --web --port 8765 --no-browser
bibdesk-rag --temp "/absolute/path/config.toml" --web
bibdesk-rag --web-open='RecQ helicase'
bibdesk-rag --web-open='相同組換え'
bibdesk-rag --web-open=''
bibdesk-rag --web-stop
```

`--web` runs in the foreground; Ctrl+C shuts it down. It opens the default browser
after binding. `--no-browser` prints the URL only. Only 127.0.0.1 is supported.
Without an explicit port it tries 8765 and falls back to an OS-assigned free port.
An explicitly occupied port is an error. Browser launch failure leaves the server running.

`--web-open QUERY` reuses the authenticated server for that configuration, or
starts a detached background server, then opens an independent search tab. An
empty query opens an idle form. Use `--web-open='-query'` for leading hyphens.
No login item, launchd job or Homebrew service is registered. `--web-stop` requests
graceful shutdown of only that configuration's owned server. Normal configuration
precedence is retained (`--temp`, environment, saved selection, default). All
settings are pinned at startup; different configurations use separate servers.

Run `bibdesk-rag --setup` if unconfigured, then `bibdesk-rag --index update` with
the same configuration if the index is missing. The GUI never edits metadata,
settings or indexes, downloads models, runs OCR or generates answers. It has no
CDN, analytics, external font or Node runtime dependency.

## Search and results

Keyword scopes reuse the CLI's metadata/fulltext/all behavior. Author, Year
(one year) and DOI apply only to Metadata. Metadata query applies only to Both.
Citekeys are entered one per line: one for Metadata or up to 100 for full text.
Choose Citekey or Metadata query. DOI-only searches with an empty query work.
Results accepts 1..100 (default 10); Excerpts per paper accepts 1..10 (default 2).
For Full text/Both, Results limits returned hits, not unique papers. Grouping
cards preserves first-hit rank and never adds extra search results.

Semantic searches Title/Abstract only and accepts Results, without keyword filters.
The local model loads on first use and is reused within the server. Disabled,
uncached or inconsistent semantic search produces an error and setup guidance;
it never silently switches to Keyword. See [semantic setup](semantic-search.md).
Multilingual input is preserved without translation. Similarity is not confidence.

Cards show full Abstract, metadata, exact excerpts, chunks, file/page/row/member
provenance and attachment extraction/missing states. Copy citekey and Copy BibTeX
report clipboard success or failure. Open DOI uses a validated normalized DOI,
never arbitrary source URLs. Source text is displayed as text, not HTML.
Queries/content are not saved to localStorage, URL queries or persistent server
history. Initial searches live in memory for 60 seconds; a one-use opaque fragment
ID is removed by the page before consumption. Expired requests leave a usable form.

## Skim

macOS and Skim are required for opening PDFs. The browser POSTs a registered
attachment ID and optional positive physical PDF page number; the server opens
only existing regular linked PDFs using `/usr/bin/open -a Skim` as an argument
array. No PDF bytes, `file://` URLs, arbitrary paths, ZIP extraction or directory
search are exposed. Fix missing links in BibDesk and update the CLI index.

A bundled constant AppleScript receives the resolved path/page as argv, identifies
the matching Skim document, goes to its page and brings its window forward.
Page numbers count from 1 at the file's beginning and may differ from printed labels.
macOS may ask for Automation permission; the application never changes permissions.
Page-navigation failure is distinguished from successful basic PDF opening.
See [Skim's official scripting help](https://skim-app.sourceforge.io/manual/SkimHelp_45.html).
The installed Skim dictionary and bundled displayline script were also inspected.

## Runtime and verification

Runtime metadata lives under `web-runtime/` next to the selected application's
SQLite index. The directory is 0700; lock/state files are 0600. Only configuration
path, port, instance and owner token persist. Ownership uses an authenticated
handshake, not a PID/port alone. Browser Host/Origin/CSRF checks remain separate
from CLI bearer authentication. Bodies are capped at 32 KiB, workers at four,
and pending initial searches at 100 with a 60-second lifetime.

Generated-fixture tests cover search equivalence, provenance, validation, ownership,
security, immutability, Skim command mocks and packaging. Safari search, Abstract,
multiple attachment display and basic Skim opening were observed on a Mac.
The user confirmed that opening a specified page works after the script correction.
This is distinct from exhaustive acceptance testing of every state, including
another PDF in front and denied Automation permission.
