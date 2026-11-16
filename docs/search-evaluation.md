# 固定検索評価 / Fixed search evaluation

## 日本語

2026-11-16（Asia/Tokyo）、このMacのPython 3.14.10で、生成した175文献・40問を
評価しました。実ライブラリ、既存PDF、外部API、実モデルを使用していません。
[固定データ](../tests/fixtures/search_evaluation.json)はプロジェクト作成の文字列のみ
（CC0-1.0）で、検索・出典対応の回帰評価です。科学的な文献関連度の実測ではありません。

baselineは#10の `f28088c` の導入済みwheelです。導入済み43ファイルが同コミットの
ソース・同梱リソースと一致することを確認してから、そのCLIを実際に起動しました。
改修後の既定モードの全40問の文献順位はbaselineと一致しました。
[機械可読の集計結果](search-evaluation-results.json)も同梱します。

| 指標 | baseline | 改修後・既定all | 改修後・fulltext |
| --- | ---: | ---: | ---: |
| Recall@10（正例35問の平均） | 0.542857 | 0.542857 | 0.885714 |
| MRR@10（正例35問の平均） | 0.542857 | 0.542857 | 0.885714 |
| 該当なし5問で空結果 | 5/5 | 5/5 | 5/5 |
| 対応を確認した本文抜粋 | 23 | 23 | 39 |
| 書誌情報だけの候補（支持本文ではない） | 65 | 65 | 0 |

| 分類 | 問数 | baseline Recall@10 | fulltext Recall@10 |
| --- | ---: | ---: | ---: |
| 書誌の別候補があり、本文だけに正例がある | 8 | 0 | 1 |
| 書誌候補26件目の本文が正例 | 5 | 0 | 1 |
| 遺伝子記号・表記揺れ | 8 | 1 | 1 |
| CSV・ZIP内補足表 | 6 | 0.5 | 1 |
| 添付のないcitekey/DOI完全一致 | 4 | 1 | 0 |
| 複数の正例文献 | 4 | 1 | 1 |
| 該当なし | 5 | 正例指標の分母から除外 | 正例指標の分母から除外 |

正解は各問の `relevance` に固定しています。grade 2は、指定した添付内に正規化後の
完全な検索マーカーがある文献です。識別子問題だけは、本文なしの書誌識別を正解にします。
他の文献はgrade 0です。書誌に同じマーカーがあっても本文にないdecoyは本文問題の正解には
しません。これは資料生成時の役割に基づく判定で、査読者等による独立した関連度判定では
ありません。遺伝子表記の対は意図的な回帰ケースで、独立した学術サンプルではありません。

Recall@10は重複を除いた上位10文献に含まれる正解の割合を問ごとに平均します。
MRR@10は最初の正解文献の順位の逆数を平均します。正解のない5問は別集計です。
`top=10, per_paper=2, max_chars=100000` を共通条件としています。
fulltextの識別子4問の低下は仕様上の限界で、本文のない文献に支持本文を作りません。

出典は、citekey・DOI、chunk ID、リンクされた実ファイル・SHA-256、PDFの物理2ページ目、
CSVレコード・セル文字範囲、ZIPメンバーと生成元文字列を照合しました。索引・設定・
生成原本の前後ハッシュも一致しています。これは出典対応の検査であり、科学的主張の
真偽・資料の網羅性の検証ではありません。

再実行例（baselineは既に導入した#10の環境を指定）:

```sh
.venv/bin/python tools/evaluate_search.py \
  --baseline-python /absolute/path/to/baseline-venv/bin/python \
  --output .local/search-evaluation.json
```

baselineを省略すると、現行の変更していない二段階経路を比較対象にします。
資料は一時ディレクトリだけに生成し、実ライブラリを走査・収集しません。
データのSHA-256は `2b65b97d6ad8a1158f3f23c2889461b29673f57b0443414c2b613299e0a3f98c`。

マーカーは人工的で、自然文の曖昧さ、実際のPDF抽出失敗、分野内の難しい順位付けは
評価していません。baselineの時間にはCLIプロセス起動が含まれ、改修後の時間は同一
プロセス内なので、速度比較には使えません。実ライブラリでの検索品質改善、意味検索の
品質、ホストCI、現行クライアントでの実操作は、この評価からは主張しません。

## English

On 2026-11-16 (Asia/Tokyo), Python 3.14.10 on this Mac evaluated 175 generated
papers and 40 fixed queries. No real library, existing PDF collection, external
API or real model was used. The project-authored CC0 dataset tests lexical
retrieval and citation correspondence, not real scientific relevance.

The baseline was the installed #10 wheel from commit `f28088c`; all 43 installed
source/resource files were checked against that commit before running its CLI.
The new default mode reproduces all 40 baseline paper rankings. The shared tables
above and [JSON summary](search-evaluation-results.json) record the measurements.

Of 40 queries, 35 have positives and five are no-match controls. Grade 2 designates
an attachment containing the complete normalized query marker, except exact
identifier cases, whose positives are metadata-only identities. All other papers
have grade 0. Metadata decoys are deliberately not positive evidence for body
questions. These are author-assigned synthetic roles, not independent scientific
relevance judgments. Paired gene variants are deliberate regression cases.

Recall@10 is mean per-query recall over unique top-ten papers; MRR@10 is mean
reciprocal rank of the first relevant paper. No-match controls have separate
empty-result counts. All runs use top=10, per_paper=2 and max_chars=100000.
Broad fulltext improves the designed body-only, candidate-window and supplementary
cases but misses four metadata-only identifier cases, an explicit scope limitation.

Citation checks cover citekey/DOI, chunk ID, linked file/hash, physical PDF page 2,
CSV record/cell ranges, ZIP member and generated source strings. Source,
configuration and index hashes are unchanged. These checks establish correspondence,
not scientific truth or completeness. Raw this-run timing is not comparable:
baseline measurements include CLI startup while current modes run in-process.

Run `tools/evaluate_search.py --baseline-python /absolute/path/to/venv/bin/python
--output .local/search-evaluation.json` with the project Python. Without an
installed baseline it compares the current unchanged two-stage path. Data are
created only in a temporary directory. The fixed dataset digest is listed above.
The artificial markers do not test ambiguous natural language, real extraction
failures, difficult scientific ranking, real-library improvements or model quality.
Hosted CI and live client use were not tested by this evaluation.
