# 類似論文検索 / Similar papers

## 日本語

```sh
bibdesk-rag --paper similar Example2025 --top 10 --format json
bibdesk-rag --paper similar Example2025 --author "Smith" --year 2026
bibdesk-rag --paper similar Example2025 --citekey CandidateA --citekey CandidateB
```

MCPは `similar_papers(citekey="Example2025", top=10)`、Web GUIは各文献カードの
**Similar Papers** に対応します。CLI/MCP/GUIは同じ読み取り専用処理を使います。
意味検索が有効で、起点文献のTitle/Abstractベクトルが既に索引に保存されている必要があります。
この操作は推論モデル・NumPyを読み込まず、モデル取得・API送信・索引更新を行いません。
モデルキャッシュがなくても、設定と保存済みモデル情報が一致すれば検索できます。

起点を除外し、1文献1件を返します。標準E5ではTitle anchorを使った長文対策、
Titleのみの語彙・意味順位統合、判断材料不足時の棄却を行います。
`ranking_score` の降順、同点はcitekey順です。cosineは関連性の確率・検証済み根拠ではありません。
方式・適用条件・索引更新要件は[改善評価](similarity-improvements.md)を参照してください。
別モデルは最大passage cosine候補を `assessment.calibrated=false` として返します。
必要な主張は `search_fulltext` と原本で確認してください。

フィルタは `year`（完全一致）、`author`（大小文字を区別しない部分一致）、
`doi`（既存方式で正規化して完全一致）、`citekeys`（候補の限定）です。
すべて共通部分として適用し、絞り込みで0件になっても対象を勝手に広げません。
MCPの空のcitekeys配列は候補なしです。CLIの繰り返し `--citekey` は起点ではなく
**候補**の指定です。起点は `--paper similar` の直後の引数で指定します。
GUIは現在のResults件数と、有効になっているAuthor・Year・DOI・Citekeyフィルタを使います。
非表示・無効のフィルタ、検索語、Metadata query、Excerpts per paperは類似検索には使いません。

応答は `source`、`results`、`embedding_model`、`index`、`filters`、`candidates` を含みます。
`source/results` の `title_only`・`has_abstract`・`indexed_fields` でabstract欠損を区別します。
abstractがなくてもTitleのベクトルがあれば検索可能で、GUIもTitle onlyを表示します。
`embedding_parts` はその文献の保存済みベクトル数です。
`candidates.total` は起点除外・フィルタ後の件数、`indexed` は比較した文献数、
`missing_vectors` はベクトルがなく比較しなかった件数です。`empty_metadata` はそのうち
TitleとAbstractが両方空の件数です。未索引候補の存在を「関連文献なし」とは扱いません。
GUIは共通結果を文献カードにまとめます。

| エラーコード（MCP/GUI API） | 意味 |
| --- | --- |
| `semantic_disabled` | 意味検索が無効。保存ベクトルが残っていても無断で使いません |
| `index_missing` | 索引ファイルがない |
| `unknown_citekey` | 起点が現在の索引にない |
| `semantic_index_missing` | 文献ベクトル形式または有効モデルの記録がない |
| `paper_vectors_missing` | 起点文献に保存ベクトルがない。Title/Abstractが両方空の場合も含む |
| `model_mismatch` | 設定・モデル署名の不一致、または比較対象に別モデルのベクトルがある |
| `stale_vectors` | 保存ベクトルと索引内の現在のTitle/Abstractのハッシュが一致しない |
| `invalid_vectors` | 次元、有限性、正規化、part番号、title_only等が不整合 |

モデル名・固定revision・次元・prefix・token上限・前処理版を確認し、同じ有効モデルIDの
ベクトルだけを比較します。保存済みbackend識別子は保持しますが、現在インストールされた
推論ライブラリとの比較や読み込みは行いません。チャンク用の旧ベクトルは対象外です。
標準E5では背景集合も検証し、古い／不正なベクトルがあれば、その一部だけを黙って除外せずエラーにします。
必要な修復・更新は利用者がCLIで明示的に行います。

検索・モデル情報・索引世代は同じSQLiteスナップショットから取得します。
原本・設定・派生索引は書き換えません。`index.freshness` は引き続き `unverified` です。
この操作は現在のBibTeXや添付を再読込しないため、原本の変更検出には明示的な索引更新が
必要です。MCPは既存の総応答上限を維持し、長い書誌フィールドの短縮を明示します。

検証は生成したベクトル／書誌のみです。元論文除外、複数part、重複排除、同順位、
各状態・破損・モデル混在、フィルタ、同時更新、CLI/MCP/認証付きGUI APIの一致と原本保持を
確認しました。ブラウザではSimilar Papers操作、起点除外、Titleのみの起点・候補表示を
生成fixtureで確認しました。配布smokeと公式SDKにも、推論依存を持たない保存ベクトルの
正のケースを追加しています。実モデルによる固定合成データの[品質評価](similarity-evaluation.md)を完了しました。
その後の[3課題の改善と別集合評価](similarity-improvements.md)も完了しました。実ライブラリの品質・性能は未検証です。

## English

Use `--paper similar CITEKEY --top 10 --format json`, MCP
`similar_papers(citekey=CITEKEY, top=10)`, or **Similar Papers** on a Web GUI card.
All use one read-only service. Semantic search must be enabled and the source
paper must already have saved Title/Abstract vectors. This operation loads no
model or NumPy, downloads nothing, submits no API data and never updates the
index. A missing model cache does not prevent comparison of compatible saved vectors.

The source is excluded and papers are deduplicated. Standard E5 uses title anchors
for long abstracts, lexical/semantic rank fusion for title-only sources and
abstention when support is insufficient. Order uses `ranking_score`, then citekey.
See the [improvement evaluation](similarity-improvements.md) for the policy,
model scope and required index refresh. Other models return maximum-passage
cosine candidates explicitly marked `assessment.calibrated=false`.
Scores are not probabilities or verified evidence; verify claims against full text.

Filters are exact year, case-insensitive author substring, normalized exact DOI,
and candidate citekeys. They intersect and never silently broaden. An MCP empty
citekey array selects no candidates. CLI `--citekey` selects candidates; the
source follows `--paper similar`. The GUI uses its current Results limit and
currently enabled Author/Year/DOI/Citekey filters, excluding disabled fields,
query text, Metadata query and per-paper excerpt count.

The response includes source/results, model identity, saved index metadata,
filters and candidate counts. Title-only papers remain eligible; `title_only`,
`has_abstract` and `indexed_fields` distinguish missing abstracts. `embedding_parts`
counts stored passage vectors. After source exclusion/filters, `candidates.total`
is the candidate count, `indexed` is the number compared, `missing_vectors` counts
unembedded candidates, and `empty_metadata` is the subset without title or
abstract. Missing vectors do not establish absence of related literature.

MCP/GUI error codes distinguish disabled semantics, missing index, unknown source,
missing semantic index, missing source vectors, model mismatch, stale vectors and
invalid vectors (see table above). The service validates configured model/revision,
dimensions, prefixes, token limit, preprocessing and saved model identity. It
compares only the active model's paper vectors, never legacy chunk vectors.
The saved backend identity is retained without importing or requiring that
backend's current libraries. Invalid/stale background vectors for standard E5 cause an error rather
than silently yielding a partial ranking. Repairs require an explicit CLI action.

Source metadata, candidates, model and generation share one SQLite snapshot.
Originals, configuration and index remain unchanged. Freshness stays unverified;
this operation does not reread source BibTeX/attachments. MCP retains its response
budget and marks shortened metadata fields.

Validation uses generated vectors/libraries, including exclusion, parts, ties,
missing/corrupt/mixed-model states, filters, concurrent updates, CLI/MCP/GUI API
parity and preservation. Browser QA exercised the button, source exclusion and
title-only source/candidate displays with a generated fixture. Installed smoke
and SDK checks include a positive saved-vector case without inference dependencies.
The [real-model controlled quality evaluation](similarity-evaluation.md) is complete,
The subsequent [three improvements and holdout evaluation](similarity-improvements.md) are complete. Real-library quality/performance remain unverified.
