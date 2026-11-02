# CLI・設定・抽出仕様

初回導入とCodexへの登録は [README](../README.md) を参照してください。以下の手動コマンド例はREADMEのManual Setupと同じ保存先を明示します。対話型セットアップの既定保存先とは異なります。独自の設定を使う場合は、各例の `bibdesk_rag_config` をその設定ファイルの絶対パスに置き換えてください。

## 対話型セットアップ

```sh
bibdesk-rag setup
bibdesk-rag --config "/absolute/path/to/config.toml" setup
```

`setup` はv0.2.0以降で利用できます。標準入力・標準エラー出力が両方とも端末の場合に動作します。`--config` や保存先の環境変数がないmacOSでは、設定・索引を `~/Library/Application Support/bibdesk-rag/` に作成します。実行時に表示する保存先を確認してください。

1. 実行環境・バージョン・保存先・実行ファイルを確認し、新規の場合は `.bib` のパスを入力します。`~`、相対パス、引用符やドラッグ＆ドロップ時のシェルエスケープに対応します。入力をシェルで実行することはありません。文献数・添付数を確認してから `init` と同じ処理で設定を作ります。
2. 既存設定があれば、継続・詳細表示・終了を選びます。不正な設定は自動修復せず、手作業で直すための案内を表示します。ライブラリ切り替え・強制上書きは行いません。
3. 索引がなければ初回作成を提案します。既存索引はそのまま使用するのが既定で、差分更新・全件再構築を明示的に選べます。処理の進捗と、文献数・添付数・本文チャンク数・抽出状態を表示します。一部の添付に問題があっても、索引作成が完了すれば継続します。
4. Codex CLIがあれば、同名登録を確認してから任意で登録します。同じ登録を重複追加せず、異なる登録を置き換えません。CLIがない場合、検出した絶対パスを使った手動接続方法を表示します。
5. 設定とSQLiteの読み取り、MCPサーバーの初期化とツール一覧を確認します。Codexからの実検索は別途必要です。MCP登録・疎通の失敗は、作成済み索引の失敗とは区別します。

Ctrl+Cは終了コード130で、EOFもtracebackなしで中断します。中断した工程と完了した工程を表示し、既存設定や作成済み設定を削除しません。索引作成に失敗した場合も、同じ `--config` で `setup` を再実行できます。索引への書き込みは既存のトランザクション処理を使います。

非TTYでは入力を読まず、既存CLIの手順を標準エラー出力に表示して終了コード1で終了します。`setup --help` は非TTYでも終了コード0で利用できます。スクリプトでは、以下の `init`・`index`・`update`・`status`・`doctor` を引き続き使ってください。

## ライブラリ登録と索引化

```sh
bibdesk_rag_config="$HOME/.config/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" init \
  --bib "/absolute/path/to/references.bib" \
  --data-dir "$HOME/.local/share/bibdesk-rag"
bibdesk-rag --config "$bibdesk_rag_config" index
bibdesk-rag --config "$bibdesk_rag_config" status --json
bibdesk-rag --config "$bibdesk_rag_config" doctor --json
```

`/absolute/path/to/references.bib` を自分の `.bib` の絶対パスに置き換え、同じターミナルで実行します。`init` は初回登録用で、既存設定を上書きしません。登録済みなら同じ設定を指定して `update` を使ってください。

| 用途 | このガイドで指定する保存先 |
| --- | --- |
| BibDesk RAGの設定 | `~/.config/bibdesk-rag/config.toml` |
| 検索索引 | `~/.local/share/bibdesk-rag/index.sqlite3` |

`.bib` は絶対パスで登録され、添付の相対パスは `.bib` の親ディレクトリが基準です。設定と索引は原本やHomebrewのインストール先から分離します。

保存先のオプションや環境変数を指定しない場合、macOSでは設定と索引を `~/Library/Application Support/bibdesk-rag/` に置きます。上の手順では `--config` と `--data-dir` で保存先を明示するため、表の場所になります。既存の設定・索引は自動で移動しません。すでに別の場所で使っている場合は、その設定を引き続き指定できます。`init` が設定に保存する `database` は絶対パスなので、設定ファイルやシェル変数だけを変更しても索引の保存先は変わりません。

保存先は次の方法で指定できます。

- `BIBDESK_RAG_HOME=/path/to/app-data`：設定とDBをまとめて指定。
- `BIBDESK_RAG_CONFIG=/path/to/config.toml` または全コマンド先頭の `--config PATH`：設定の場所を指定。
- `XDG_CONFIG_HOME` / `XDG_DATA_HOME`：設定・データの標準位置を個別指定。
- `init --data-dir PATH`：DBの保存先を指定。

`--config` は `bibdesk-rag --config PATH search ...` の順に置きます。設定ファイル内の相対パスは設定ファイルの親が基準です。[config.example.toml](../config.example.toml) にチャンク長、重複長、ファイル・ZIP上限を記載しています。複数ライブラリには別の設定とDBを使用してください。

## 進捗と結果の表示

以下はv0.1.1以降の機能です。

`index` / `update` の通常のターミナル実行では、処理済みの文献数・添付数を標準エラー出力の1行で更新します。同じ添付が複数の文献にリンクされていても、添付数には1回だけ数えます。進捗率は処理済み文献数と添付数に基づく目安で、残り時間の見積もりではありません。索引の保存が完了してから100%を表示します。

終了時の標準出力は、文献の追加・変更件数、添付の抽出試行・再利用件数、今回の処理で発生した要確認件数をまとめた短い要約です。抽出試行数は本文の抽出成功数ではなく、未対応形式や本文なしのファイルも含みます。要確認には部分抽出や未対応形式も含まれます。PDFなどの読み取りライブラリが出す警告は、抽出結果とは別に件数と最大3例にまとめます。読み取りの復旧警告があっても、本文を抽出できている場合があります。

| オプション | 表示 |
| --- | --- |
| 指定なし | ターミナルでは進捗バーと短い要約。要確認事項の例は最大3件 |
| `--no-progress` | 進捗バーを無効化。短い要約は表示 |
| `--json` | 集計結果と今回の要確認事項の全件をJSONで標準出力に出力。進捗バーなし |
| `--verbose` | 読み取り中の警告・要確認事項を標準エラー出力にすべて表示。進捗バーなし |

標準出力をファイル・パイプに渡した場合は、互換性のためオプションなしでも従来のJSONを出力します。進捗バーは標準出力・標準エラー出力の両方がターミナルにつながっている場合だけ表示し、`TERM=dumb` では表示しません。`--json --verbose` の併用も可能で、その場合も標準出力のJSONに警告は混ざりません。

抽出の要確認事項は索引にも保持されます。再抽出せずに状態を調べる場合は、同じ `--config` を指定した `status --json` や `attachments CITEKEY --json` を使ってください。

## 検索と出典の取得

```sh
bibdesk_rag_config="$HOME/.config/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" search "histone H3K4 UV damage" --top 10 --json
bibdesk-rag --config "$bibdesk_rag_config" search "RecQ helicase" --scope fulltext --json
bibdesk-rag --config "$bibdesk_rag_config" search "Neurospora" --scope metadata --json
bibdesk-rag --config "$bibdesk_rag_config" search "Example2025" --scope metadata
bibdesk-rag --config "$bibdesk_rag_config" search "10.1234/example" --scope metadata
bibdesk-rag --config "$bibdesk_rag_config" search "" --scope metadata --doi "https://doi.org/10.1234/example"
bibdesk-rag --config "$bibdesk_rag_config" search "histone" --scope metadata --year 2025 --author Muller
bibdesk-rag --config "$bibdesk_rag_config" get Example2025 --json
bibdesk-rag --config "$bibdesk_rag_config" get Example2025 --format bibtex
bibdesk-rag --config "$bibdesk_rag_config" attachments Example2025 --json
```

DOIとcitekeyは完全一致を優先し、同じDOIの複数エントリを保持します。FTSの問い合わせは単語のAND検索で、入力をFTS構文やSQLとして実行しません。部分一致・同義語推論・意味検索は初期版にはありません。ハイフンの表記ゆれ、`hH3-K4R` / `hH3K4R`、`mus-9`、`Δset-1` に共通の検索正規化を適用します。返す本文抜粋は元の抽出テキストを保ち、数値や記号を検索用文字列で置き換えません。

既定の `--scope all` は書誌検索で最大100件の候補を選び、その文献の本文を検索します。書誌候補がなければ本文全体へフォールバックします。本文が見つからない候補は書誌情報として返すため、`source_type` を確認してください。本文全体を横断する場合は `--scope fulltext` を使います。

```sh
bibdesk_rag_config="$HOME/.config/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" search "RecQ" --metadata-query "Neurospora" --top 10
bibdesk-rag --config "$bibdesk_rag_config" search "UV" --scope fulltext --citekey Example2025 --citekey Other2024
bibdesk-rag --config "$bibdesk_rag_config" context "UV-induced mutagenesis" --top 5 --max-chars 10000
bibdesk-rag --config "$bibdesk_rag_config" context "RecQ" --metadata-query "histone" --json
```

1文献あたり既定2件（`--per-paper 1..10`）、取得件数は `--top 1..100`。contextの `--max-chars 256..100000` は引用ヘッダと本文を含む **context文字列全体** の上限です。JSONの構造情報はこの上限の外です。`unverified`、`truncated`、`budget_exhausted` に不足や省略を明示します。取得件数が少ないことは、他の証拠が存在しないことを意味しません。

PDFはページを跨がず約1500文字、重複200文字で分割し、1始まりのページ番号を保持します。CSV/TSVはヘッダを1行目とするレコード番号（引用符内改行は1レコード）、XLSXは実際のシート行番号です。XLSXの数式は文字列として保持し、再計算しません。補足PDFは `supplement` / `supp` 等のファイル名を手掛かりにリンクの `role` で識別します。これはファイル内容からの確定分類ではありません。

## 差分更新

```sh
bibdesk_rag_config="$HOME/.config/bibdesk-rag/config.toml"
bibdesk-rag --config "$bibdesk_rag_config" update
bibdesk-rag --config "$bibdesk_rag_config" update --verify-hashes
bibdesk-rag --config "$bibdesk_rag_config" index
```

`update` はエントリの追加・変更・削除と添付リンクを同期し、サイズとナノ秒mtimeが同じ添付の再読込を省略します。変更候補だけSHA-256を計算し、内容が同じなら既存chunk IDを再利用します。`--verify-hashes` は同一サイズ・mtimeでも全ファイルをハッシュ検査します。設定変更または `index` は再抽出します。文献キー変更は旧・新両方で一意なDOIの場合だけ内部IDを維持します。

同じ正規化済みファイルパスを複数文献が参照しても、抽出結果は1つです。別パスに置かれた同内容のコピーは別添付として扱います。書込はトランザクションで行い、致命的エラーでは前の索引を維持します。個々の欠損・抽出不能ファイルはエラー状態として記録し、他の文献を処理します。消えた資料の古い本文は検索対象から除去します。

## 抽出と検索の制約

- `doctor`：SQLite/外部キー/FTS整合性と添付エラーを確認。FTS検査のためDBをメモリにコピーします。大規模DBではメモリが必要です。
- 欠損・移動ファイル：まずBibDesk上でリンクを確認してください。公開 `Entry.files` を優先し、既存パスがない場合のみmacOS bookmark/aliasをUI・マウントなしで解決します。現代のbookmark移動追跡は合成データで検証済み。古い実機alias形式は未検証です。
- 画像のみPDF：`no_text` として記録。OCRはありません。暗号化PDF・壊れたPDFは理由を記録し、処理を継続します。
- ZIP：内部一覧を記録し、対応形式のみメモリ内で解析。パス逸脱、symlink、暗号化、サイズ・件数・圧縮率超過を拒否。入れ子ZIPは本文未解析です。XLSXもZIP/XMLの安全性を検査します。
- `.xls`、画像、その他形式：名前・拡張子を記録し、本文未解析にします。
- PDFの読み順・段組・表の再構成精度はpypdfの抽出に依存します。抽出テキストは原本を代替しません。
- 索引は平文のローカルSQLiteです。アプリはファイルを0600で作成します。バックアップやOSのアクセス権は利用者側で管理します。
- 生物学的表記の正規化は検索補助であり、異なる実験条件や変異体が同一であるとは推論しません。

