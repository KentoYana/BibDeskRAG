# 索引状態と選択的な再抽出 / Index status and selective retry

## 日本語

`bibdesk-rag --index status --format json` と読み取り専用MCPの
`get_index_status()` で、ライブラリの識別情報、保存済みBibTeX SHA-256、
最終成功日時、索引世代、文献・添付・チャンク数、抽出状態別件数を確認できます。
MCPは現在の原本を読まず、`freshness: "unverified"`（鮮度未確認）を返します。
日時が新しくても、現在の原本との一致は保証しません。`excluded` は画像・動画の
意図的な対象外で、抽出失敗とは区別します。

`index_generation` は成功した更新ごとに変わる識別子です。原本に変更のない更新でも
変わります。処理がロールバックされた場合は以前の世代が保持されます。古い索引に
保存値がなければ `null` とし、次に明示的な更新が成功すると保存します。
`last_successful_update` は保存済みのUnix時刻（秒の文字列）です。成功した更新は
全添付の抽出成功を意味せず、残存する問題は状態別件数で確認します。

失敗した同一内容の添付を再試行する例:

```sh
bibdesk-rag --paper attachments Example2025 --format json
bibdesk-rag --index update --retry-citekey Example2025 --retry-status error
bibdesk-rag --index update --retry-attachment 12
bibdesk-rag --index update --retry-path "/absolute/path/to/supplement.csv"
bibdesk-rag --index update --retry-status error --retry-status partial --format json
```

- `--retry-citekey`、`--retry-attachment`、`--retry-path` は繰り返し指定でき、
  いずれかで選ばれた添付を対象にします。同じ添付を複数文献が共有していても処理は1回です。
- `--retry-status` は更新前の索引に保存された状態で対象を絞ります。複数の状態はORです。
  識別子を指定せず状態だけを指定すると、その状態の全リンク済み添付が対象です。
- 状態は `ok`、`partial`、`unsupported`、`empty`、`encrypted`、`error`、
  `image_only`、`no_text`、将来のワーカー用 `timeout`、`resource-limit` を指定できます。
  この変更自体は時間・メモリ制限を追加しません。
- 画像・動画の `excluded` は再抽出しません。未登録citekey・不明ID・現在のライブラリに
  リンクのないパスはエラーにし、更新をロールバックします。相対パスは実行ディレクトリ基準です。
- 再試行指定は `--index update` 専用です。通常の差分更新も行うため、原本・抽出方式・
  オプションが変わった別の添付は通常どおり更新します。正常な未変更添付は再利用します。
- `--verify-hashes` は内容を確認する指定で、内容が同じ添付の強制再抽出ではありません。
  選択的再試行はstat/hashが同じでも対象を再抽出します。

JSONの `errors` は今回記録した抽出診断、`new_issues` は以前に問題として記録されて
いなかった添付の問題数、`resolved_issues` は以前の問題から `ok` に変わった件数、
`remaining_issues` は更新後に索引に残る問題の状態別件数です。後者は再利用した添付も
含み、`ok` と `excluded` を含みません。`retry.selected/attempted` は選択した対象と
その処理試行数で、抽出成功数ではありません。本文が取れない場合は添付情報の状態・
診断を併せて確認してください。

`build_context` のJSONは、`index` に同じ索引情報、`search_scope` に実際の書誌候補と
本文検索対象を返します。`fulltext_citekeys: null` は索引全体、配列は選択文献、空配列は
対象なしです。`fulltext_scope: "not_searched"` は明示した書誌条件に候補がなかった
場合です。書誌候補には従来の件数上限があり、対象の一覧は全関連文献の網羅を意味しません。
各出典には保存済みの `content_hash`（添付SHA-256）、`indexed_bib_hash`、
`index_generation` が付きます。書誌情報だけの候補では `content_hash` は `null` です。
ZIP内のチャンクは外側の添付のハッシュを使い、メンバーの位置も保持します。
検索・原文・世代は1つのSQLiteスナップショットで取得します。
これらは現在のファイルを再検証した証拠や、科学的主張の検証結果ではありません。

## English

Use `bibdesk-rag --index status --format json` or the read-only MCP tool
`get_index_status()` to inspect library identity, saved BibTeX SHA-256, the last
successful update, index generation, paper/attachment/chunk counts, and counts by
extraction state. MCP never reads current source files. It returns
`freshness: "unverified"`; a recent timestamp does not establish agreement with
current sources. `excluded` identifies intentionally excluded images/videos,
separately from extraction failures.

`index_generation` changes after every successful update, including updates with
unchanged sources. Rollback retains the previous generation. Older indexes with
no saved generation return `null` until the next explicit successful update.
`last_successful_update` is the saved Unix timestamp in seconds, represented as a
string. A successful update can still contain extraction failures; inspect the
state counts for remaining problems.

Examples for retrying unchanged failed attachments:

```sh
bibdesk-rag --paper attachments Example2025 --format json
bibdesk-rag --index update --retry-citekey Example2025 --retry-status error
bibdesk-rag --index update --retry-attachment 12
bibdesk-rag --index update --retry-path "/absolute/path/to/supplement.csv"
bibdesk-rag --index update --retry-status error --retry-status partial --format json
```

- Repeatable `--retry-citekey`, `--retry-attachment` and `--retry-path` select the
  union of their attachments. Shared attachments are processed once.
- `--retry-status` filters those targets using their saved pre-update states.
  Multiple statuses are alternatives. With no identity selectors, statuses alone
  select all currently linked attachments in those states.
- Accepted states are `ok`, `partial`, `unsupported`, `empty`, `encrypted`,
  `error`, `image_only`, `no_text`, plus `timeout` and `resource-limit` for future
  workers. This change does not itself add time or memory limits.
- Excluded images/videos are never force-extracted. Unknown citekeys/IDs and paths
  not linked to the current library fail and roll back the update. Relative paths
  are resolved from the current working directory.
- Retry selectors require `--index update`. Normal incremental maintenance still
  occurs, so other attachments with changed sources, extraction policy or options
  are updated normally. Unchanged healthy attachments are reused.
- `--verify-hashes` checks content; it does not force extraction when content is
  identical. Retry forces selected attachments even when stat/hash is unchanged.

In JSON, `errors` contains extraction diagnostics recorded in this run;
`new_issues` counts attachments not previously recorded as problematic;
`resolved_issues` counts previously problematic attachments now `ok`;
`remaining_issues` counts post-update problems by state, including reused
attachments but excluding `ok` and `excluded`. `retry.selected/attempted` counts
targets and processing attempts, not successful extractions. Inspect attachment
states and diagnostics when text is unavailable.

`build_context` JSON includes saved index information in `index` and actual
metadata candidates and full-text scope in `search_scope`. A `null`
`fulltext_citekeys` means the whole index; an array lists selected papers, and an
empty array means no papers. `fulltext_scope: "not_searched"` means an explicit
metadata condition found no candidates. Existing metadata candidate limits still
apply; the recorded scope does not imply complete coverage of relevant papers.
Each citation includes saved `content_hash` (attachment SHA-256),
`indexed_bib_hash` and `index_generation`. Metadata-only results have a `null`
`content_hash`. ZIP chunks use the outer attachment hash and retain member
locations. Retrieval, source text and generation share one SQLite snapshot.
These fields do not establish freshness of current files or verify scientific
claims.
