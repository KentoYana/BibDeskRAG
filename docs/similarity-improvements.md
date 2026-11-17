# 類似論文検索の改善評価 / Similar Papers improvement evaluation

## 日本語

2026-11-17、3課題を実装し、キャッシュ済み実E5モデルによるオフライン評価を完了しました。
開発用40起点とは分野・文章・定型文の異なる52文献／36起点を先に固定し、方式・閾値を
開発集合だけで選択してから評価しました。別集合の事前条件7件をすべて満たしました。
これは人手作成の合成書誌での結果です。実ライブラリや独立専門家の判定による検証ではありません。

### 実装

1. **長文の定型文**：索引作成時にTitleだけの独立したベクトルを先に保存します。
   旧来のAbstract全文passageも省略せず保持します。複数passageのAbstractを含む比較は
   Titleの先頭ベクトル同士で行い、共通付録の最大cosineによる順位支配を避けます。
   通常の短いAbstract同士では従来のTitle/Abstract比較を維持します。
2. **Titleのみ**：意味順位と語彙順位を重み0.5ずつ、定数10のreciprocal rank fusionで統合します。
   語彙はTitleを3回とAbstract先頭600文字、英数字単語・CJK bigram、sublinear TF／平滑IDFです。
   Abstractのある起点の語彙重みは0です。開発実験では語彙重みを増すと長文・短文双方が悪化しました。
3. **関連候補を判断できない場合**：Title同士のcosineを全索引候補の中央値に対する相対差で評価します。
   最大語彙cosineが0.15未満**かつ**相対差が0.35未満なら `insufficient_evidence` として0件を返します。
   相対差は `(最大Title cosine − 中央値) / (1 − 中央値)` です。背景候補10件未満、または起点Titleなしも
   判断材料不足です。これは「関連文献が存在しない」の断定ではありません。

このプロファイルは固定revisionの `intfloat/multilingual-e5-small`、384次元、標準prefix・token上限、
SentenceTransformers backendを対象とします。別モデルは従来の最大cosine候補を返し、
`assessment.calibrated=false` / `uncalibrated_candidates` と明記します。評価したbackendの正確な版はJSONに記録しています。
閾値を別モデルや実ライブラリの普遍的な確信度と解釈できません。

前処理署名を `title-anchor-v2` に更新したため、既存ベクトルには明示的な `--index update` が必要です。
通常の索引更新で派生ベクトルだけを再生成し、その後は差分再利用します。検索から更新・推論・ダウンロードはしません。
今回、利用者の索引更新は実行していません。本文検索・原本・添付は変更しません。
通常の自由文semantic検索も追加Titleベクトルを検索対象とします。その実ライブラリでの順位変化は未検証です。

`ranking_score` が実際の順位、`similarity_score` は使った意味比較のcosine、`lexical_score` は語彙cosineです。
同点はcitekey順です。`assessment` をCLI/MCP/GUI APIに返し、GUIは判断材料不足を表示します。
背景と語彙IDFはフィルタ適用前の全索引で計算し、その後に候補フィルタ・件数上限を適用します。
背景候補も検証するため、フィルタ外の古い／不正な保存ベクトルもエラーになります。
検索は標準ライブラリだけで動作しますが、全背景ベクトルと語彙表をメモリに保持します。大規模実索引での性能は未検証です。

### 固定した別集合での結果

| 指標 | 旧最大passage | 改善後 |
| --- | ---: | ---: |
| nDCG@10（正例起点32件） | 0.3144 | **0.6093** |
| Recall@10 | 0.3438 | **0.4750** |
| MRR@10 | 0.5208 | **0.9594** |
| 長文：首位がgrade 0 | 8/8 | **0/8** |
| Titleのみ：nDCG@10 | 0.2218 | **0.5686** |
| 関連文献なし：候補を返した起点 | 4/4 | **0/4** |
| 正例起点の候補返却率 | 32/32 | **32/32** |

Titleのみの語彙ベースラインは0.5028で、改善後はこれも上回りました。
日本語8起点のnDCGは0.1089から0.5066です。正例なし4起点は正例指標の分母から除外しています。
全体nDCG改善、Titleのみが語彙以上、長文首位誤り2件以下、正例返却率90%以上、対照4件の棄却、
Recall低下0.05以内、日本語nDCG低下0.05以内の7条件を事前設定し、すべて通過しました。

開発集合ではnDCG 0.5535→0.6652、長文首位誤り8→1件、対照返却4→0件でした。
ただし開発集合の短いAbstractはnDCG 0.7204→0.6150、全体Recallは0.6444→0.6278と低下しました。
すべての条件で単調に改善したわけではありません。残る開発長文の誤首位や全順位も結果JSONに保存しています。
別集合でもRecallは0.4750であり、広い分野の関連文献を漏れなく取得できる状態ではありません。
対照は各集合4件だけで、一般的な棄却性能・誤棄却率の保証はできません。

### 再現と証跡

- [事前条件](../tests/fixtures/similarity_improvement_preregistration.json)、[別評価集合](../tests/fixtures/similarity_holdout.json)、
  [全順位・集計・判定・モデル情報・ハッシュ](similarity-improvement-results.json)を保存しています。
- 別集合SHA-256: `cc11e32422b4d63ef8d8afc1f3c4ebee52373240e72c9d83e5cb555f5d94902f`。
- Mac/arm64、Python 3.14.10、CPU 1 thread。固定モデル・既存キャッシュのみを使い、socket/URL接続を禁止しました。
- 旧方式は新規保存されたベクトルから追加Title anchorを除いて再構成しました。
  開発集合の旧方式は[改善前の実測](similarity-evaluation.md)と全体指標が一致しました。
- 各起点を2回検索し応答の一致を確認。検索前後の生成BibTeX／派生索引のハッシュが不変です。
  実ライブラリ・PDFは読み取りも更新もしていません。#9のRecall/MRR集計を共用しています。
- 別集合の結果を見て閾値・重み・正解を変更していません。開発中、先頭Abstractを優先するだけでは定型文に負けたため、
  独立Title anchorを採用しました。この変更は別集合の実行前です。

```sh
.venv/bin/python tools/evaluate_similarity_improvements.py \
  --model-cache /path/to/existing/model-cache --output /tmp/new-similarity-evaluation
```

既存出力先を上書きしません。semantic extraと固定モデルのキャッシュが必要です。自動インストール・取得はしません。

## English

The three improvements were implemented and evaluated offline with cached E5 on 2026-11-17.
A separate authored synthetic set (52 papers, 36 sources: 32 positive and four no-related controls)
was frozen before selecting the policy on the original 40-source development set. All seven
preregistered holdout gates passed. This is a controlled synthetic experiment, without independent
expert judgments or real-library validation.

Indexing now saves separate title anchors before retaining all abstract passages. Comparisons involving
multi-passage abstracts use the first title anchors, preventing shared appendices from dominating.
Short abstracts retain their full-metadata comparison. Title-only sources fuse semantic and lexical
ranks equally using RRF with constant 10. Lexical TF-IDF uses three copies of the title and the first
600 abstract characters, Latin words and CJK bigrams. Abstract-bearing sources use semantic ranking only.

The pinned E5 profile abstains when both maximum lexical cosine is below 0.15 and the title-anchor
semantic margin relative to the full-library median is below 0.35. Fewer than ten background candidates
or a missing source title also produces insufficient evidence. This is not proof that no related paper
exists. Other models return explicitly uncalibrated maximum-cosine candidates. The profile is not a
universal confidence threshold; exact evaluated backend versions are recorded in the results.

On holdout, nDCG@10 improved **0.3144→0.6093**, Recall **0.3438→0.4750**, MRR **0.5208→0.9594**.
Long-abstract wrong top results fell **8/8→0/8**. Title-only nDCG rose **0.2218→0.5686**, exceeding
lexical **0.5028**. All four no-related controls abstained; all 32 positive sources returned candidates.
Japanese nDCG rose **0.1089→0.5066**. The seven gates cover ranking, recall, Japanese retention,
title-only versus lexical, long-source errors, control abstention and positive-source coverage.

Development nDCG improved 0.5535→0.6652, but short-abstract nDCG declined 0.7204→0.6150 and overall
Recall declined 0.6444→0.6278. One development long-source wrong top result remains. Holdout Recall
is still only 0.4750; four controls per set cannot establish general rejection accuracy.
All failures and rankings are retained in the [full results](similarity-improvement-results.json).

The new preprocessing signature requires an explicit `--index update`; subsequent unchanged updates
reuse vectors. Search itself remains read-only with no inference, optional numeric imports, model
fetch or API submission. No user index update was performed. Free-text semantic search also sees
the added title vectors; its real-library ranking changes remain untested.

`ranking_score` determines order; `similarity_score` and `lexical_score` are component cosines.
Ties use exact citekey order. CLI/MCP/GUI expose `assessment`, and the GUI explains abstention.
Background calibration and IDF precede filters and top limits. All background vectors are validated,
including candidates outside filters. The service holds background vectors/lexical data in memory;
large-library performance is untested.

The command above reproduces evaluation without overwriting previous results. It requires existing
semantic dependencies and a cached pinned model. Socket/URL connections are prohibited. Removing
the added title anchor reconstructs the legacy baseline; development aggregate metrics match the
original evaluation. Queries were repeated twice identically, with generated source/index hashes
unchanged. No user bibliography or attachment was read or changed. Recall/MRR share #9's evaluator.
No weights, thresholds or labels were changed after viewing holdout results.
