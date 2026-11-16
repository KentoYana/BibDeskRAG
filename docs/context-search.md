# Contextの検索範囲 / Context search scope

## 日本語

```sh
# 既定: 書誌候補を先に選ぶ従来の二段階検索
bibdesk-rag --paper context "RecQ helicase" --scope all --format json
# 明示的に、索引にある全添付本文を検索
bibdesk-rag --paper context "RecQ helicase" --scope fulltext --format json
# 広域モードでも明示した対象を尊重
bibdesk-rag --paper context "RecQ helicase" --scope fulltext --citekey Example2025
bibdesk-rag --paper context "RecQ helicase" --scope fulltext --metadata-query "Neurospora"
```

MCPは `build_context(query="RecQ helicase", scope="fulltext")` に対応します。
省略時の `scope="all"` は従来の順位・動作を維持します。`metadata` はcontextの
scopeではなく、既存の `--paper search --scope metadata` 用です。

- `all`: 書誌候補を最大 `min(100,max(20,top))` 件選び、その本文を検索します。
  明示的な条件がなく書誌候補0件の場合だけ、従来どおり索引の全本文へフォールバックします。
  本文にない書誌情報だけの一致も候補として返します。
- `fulltext`: 書誌情報を確認した上で、通常の書誌候補の件数制限で本文対象を絞らず検索します。
  返すのは添付から抽出済みの本文だけです。添付のないDOI/citekeyの確認には
  `search_papers` または既定のcontextを使います。
- `citekeys` は両モードで必ず本文対象を制限します。MCPの空配列は対象なしです。
- `metadata_query` は両モードで厳格な書誌条件です。候補0件でも無断で範囲を広げません。
  候補上限も従来どおりです。MCPで `citekeys` と両方指定した場合は共通部分を使います。
  CLIは従来どおり `--citekey` と `--metadata-query` の併用を拒否します。

「全添付」は現在の索引にある抽出済み本文です。原本を新たに読んだり、未索引資料・
暗号化資料・除外された画像等の本文を自動取得したりする機能ではありません。
意味検索・OCR・API送信・モデル取得は行いません。

JSONの `search_scope` は、実際の範囲と候補の打切りを示します。

| フィールド | 意味 |
| --- | --- |
| `requested_scope`, `strategy` | 指定モードと検索方式 |
| `metadata_match_count` | 同じ書誌条件に一致する全件数。DOI/citekey完全一致はFTS順位と独立 |
| `metadata_candidate_count`, `metadata_candidate_limit` | 使用した候補数と上限 |
| `metadata_candidates_omitted`, `metadata_omitted_count` | 上限による書誌候補の省略の有無・件数 |
| `metadata_candidate_citekeys` | 実際の書誌候補（最大100件） |
| `metadata_limits_fulltext` | 書誌候補が本文検索対象を制限しているか |
| `fulltext_citekeys` | 本文対象。nullは索引全体、配列は選択文献、空配列は対象なし |
| `fulltext_scope` | `all_indexed_papers` / `selected_papers` / `not_searched` |
| `fulltext_status` | `matched` / `no_matches` / `not_searched` |
| `fulltext_result_count` | contextの文字数制限を適用する前の本文検索結果数 |

`not_searched` は明示的な候補が空、または検索可能な語がない場合です。`no_matches` は
指定範囲を検索して本文一致がなかった場合です。どちらも文献・根拠の不在を証明しません。
書誌候補を省略していても、広域モードで `metadata_limits_fulltext=false` なら、その上限で
本文対象を省略した意味ではありません。通常のtext出力は範囲・状態・候補数を標準エラーに
表示します。JSONでは出典と併せて完全な範囲情報を確認できます。

文字数、結果数、文献ごとの上限、保存済みハッシュ、表セル範囲、読み取りスナップショットは
維持します。`fulltext_result_count` とcontextの `returned` が違う場合は、書誌候補の追加や
文字数による省略を確認してください。鮮度は引き続き未確認です。
固定評価の方法・結果・限界は [検索評価](search-evaluation.md) を参照してください。

## English

Use `--paper context QUERY --scope all` (default) for the existing metadata-first
path, or `--scope fulltext` for all indexed attachment text. MCP uses
`build_context(query=QUERY, scope="fulltext")`. `metadata` is only a paper-search
scope, not a context scope.

Default `all` selects at most `min(100,max(20,top))` metadata candidates, searches
their text, and can return metadata-only candidates. If no metadata candidates
exist and there is no explicit filter, its existing whole-index fallback remains.
`fulltext` examines metadata but does not limit text to that ordinary candidate
window. It returns extracted text only: use metadata search/default context for
identifiers of papers without attachments.

Both modes honor explicit citekeys and strict `metadata_query`; an empty strict
selection never broadens silently. Strict metadata selection retains the same
candidate cap. An MCP empty citekey array means no targets. When both selectors
are passed through MCP/Python, their intersection applies. The CLI retains its
existing rejection of combining `--citekey` with `--metadata-query`.

All-attachment scope covers only already indexed extracted text. It does not read
new source files, obtain unavailable/encrypted/excluded content, perform OCR,
use semantic inference, download models or submit data to an API.

`search_scope` records the requested mode/strategy, total metadata matches,
selected candidate count/limit/list, omitted count/flag, whether metadata limits
full text, actual full-text targets and status. `fulltext_citekeys=null` means the
whole index; an array lists selected papers; an empty array means no targets.
`fulltext_scope` is `all_indexed_papers`, `selected_papers` or `not_searched`.
`fulltext_status` distinguishes `matched`, `no_matches` and `not_searched`.
The last means an empty explicit selection or no searchable query terms.
`fulltext_result_count` precedes context character-budget truncation. Metadata
candidate omission does not imply a full-text restriction when
`metadata_limits_fulltext=false`. Text CLI output prints scope/status/counts to
stderr; JSON includes all diagnostics alongside citations.

Counts/results are bounded and share the source/index snapshot. Exact identifier
lookup remains independent of BM25. Existing result, per-paper and character
limits, source hashes and table-cell provenance remain. No-match and unsearched
states do not establish absence of evidence; index freshness remains unverified.
See [the fixed search evaluation](search-evaluation.md) for results and limits.
