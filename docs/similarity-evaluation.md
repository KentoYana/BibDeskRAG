# 類似論文検索の品質評価 / Similar Papers quality evaluation

改善前の記録です。現在の実装と追加評価は [3課題の改善評価](similarity-improvements.md) を参照してください。
This is the pre-improvement record; see the [current policy and holdout evaluation](similarity-improvements.md).

## 日本語

**実モデルでの固定評価を完了しました。候補探索として改善は見られますが、長文の共通定型文と
Titleのみの文献では順位に課題があります。** 高いcosineを関連性の保証として扱う用途には
向きません。今回の判定は、人手作成の合成文献による制御実験の範囲です。

2026-11-16（Asia/Tokyo）、Mac/arm64、Python 3.14.10、CPU・Torch 1 threadで実行しました。
設定済みキャッシュの `intfloat/multilingual-e5-small`、固定revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98` を使用し、52文献から68本の実ベクトルを
作成しました。モデル取得・外部API・ネットワーク接続を禁止し、利用者の実ライブラリは
読み取りも更新も行っていません。実ベクトル作成後の評価は本番の `similar_papers` を
呼び出し、検索中にencoderを呼んでいません。

[固定データ](../tests/fixtures/similarity_evaluation.json)と正解をモデル実行前に固定し、
SHA-256は `47fed5670f3a59a13707945413994c4962e1637dd895ef41e1a6fa62c9b1e68d` です。
モデルの重み・設定・tokenizer、評価コード、#20サービスコードのハッシュと全順位を
[機械可読の評価結果](similarity-evaluation-results.json)に保存しました。
CPU実行を3回行い、各回の3方式×40起点の120順位と集計値が完全一致しました。

### 正解集合と比較条件

- 文献は8分野×6件と、孤立対照4件の計52件です。Title/Abstractはすべてプロジェクト作成の
  合成文章（CC0-1.0）です。実際の論文・実験結果を示す書誌ではありません。
- 各分野は2つの主機構に分け、同じ主機構をgrade 2、同じ大分野の別機構をgrade 1、
  他の候補をgrade 0と定義しました。モデルの順位・類似度を見て正解を変更していません。
  独立した専門家・盲検による関連度判定ではなく、分野間にもあり得る関連は対象外です。
- 正例を持つ起点36件と、正例なしの対照4件の計40起点です。日英、Titleのみの起点8件、
  共通の事務的付録を繰り返した長文Abstractの起点8件を含めました。長文条件は、
  最大passage方式の弱点を調べるために事前設定したストレス試験です。
- 同じ52件を対象に、語彙TF-IDF cosine、同じ保存ベクトルの平均を正規化したcentroid cosine、
  #20の最大passage組合せcosineを比較しました。起点はすべて候補から除外し、上位10文献を
  文献単位で評価します。TF-IDFは英数字単語と日本語/CJK文字bigram、sublinear TF・平滑IDFです。
- Recall@10とMRR@10はgrade 1/2を関連とし、#9の集計処理を再利用しています。
  nDCG@10は利得 `2^grade-1`、割引 `log2(rank+1)` としました。
  正例なし4件は正例指標の分母から除き、候補数・最高スコアを別に記録します。

### 結果

| 方式 | Recall@10 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: |
| 語彙TF-IDF | 0.4389 | **0.7917** | 0.4041 |
| 保存ベクトルcentroid | 0.5833 | 0.7604 | 0.5104 |
| #20・最大passage | **0.6444** | 0.7662 | **0.5535** |

事前に定義した「全体nDCGが語彙ベースライン以上」のscreenは満たしました。
MRRは語彙方式を下回っており、すべての指標で優位という結果ではありません。
このscreenは実運用の合格保証・統計的な有意差・外部コーパスへの一般化を意味しません。

| 起点の条件 | 件数 | #20 Recall@10 | #20 MRR@10 | #20 nDCG@10 | 語彙nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 短いAbstract | 20 | 0.7300 | 1.0000 | 0.7204 | 0.4149 |
| Titleのみ | 8 | 0.5500 | 0.8229 | 0.4378 | **0.6203** |
| 定型付録のある長いAbstract | 8 | 0.5250 | 0.1250 | 0.2521 | 0.1610 |

日本語起点12件の#20 nDCGは0.5780、英語の正例起点24件は0.5413でした。
英語には長文・Titleのみのストレス条件が多く、この差を言語性能の優劣とは解釈できません。

### 確認できた弱点

**長文の最大値集約。** 長文起点8件すべてで、最上位がgrade 0の別分野文献でした。
最上位スコアを実際に決めたpassageの組合せを保存ベクトルから再計算したところ、
いずれも両文献のpart 1（0始まり）でした。このpartはAbstract冒頭の主題文を含まず、
共通付録と繰り返されたTitleを含みます。例えばDNA修復のP001からミトコンドリアのP013が
最上位になります。共通定型文の強い一致が主題との関連より上位になる失敗例です。

**Titleのみ。** この条件では語彙nDCG 0.6203に対して#20は0.4378でした。
短いメタデータでの語彙一致の活用は改善候補です。現行のTitle only表示は品質上も重要です。

**正例なしの扱い。** 孤立対照4件とも#20は10件を返し、最高スコアは0.8503〜0.8617でした。
現行APIは関連性の閾値や棄却判定を持たず、順位に従って候補を返します。この対照の高い
スコアから普遍的な関連度閾値は設定できません。「候補がある」「高いcosine」を
検証済みの関連性と同一視しない扱いが必要です。

### 再実行と検証範囲

```sh
.venv/bin/python tools/evaluate_similarity.py \
  --model-cache /absolute/path/to/existing/model-cache \
  --output .local/similarity-quality-run-001
```

既存のキャッシュがない場合はダウンロードせず停止します。出力先は毎回新しいディレクトリを
指定します。`preregistration.json` をモデル読み込み前に保存し、結果、全順位、条件別集計、
モデル署名・SHA、生成原本／索引の検索前後不変性、使用資源を `results.json` に保存します。
平均ベクトルやTF-IDFは事前計算を使い、#20はSQLite読み取り・検証を含むため、個別の
`retrieval_ms` は最適化条件を揃えた速度ベンチマークではありません。

検証したのは、実モデルがこの固定合成コーパスで返す順位です。実ライブラリ、独立した
関連度判定、多数の自然文・実論文、異なるモデル／OSの品質や速度は未検証です。
高得点を作るための正解・コーパス・#20の順位方式の調整は行わず、失敗例を保存しました。
既定CIの数学・データ整合・ネットワーク禁止・保存サービス呼び出しの試験は生成fixtureで
行い、今回の実モデル評価とは区別します。

## English

Real-model evaluation is complete on a frozen, authored synthetic corpus. #20
improves overall Recall/nDCG over the lexical comparator, while long shared
boilerplate and title-only records expose substantial ranking weaknesses.
This supports exploratory candidate discovery within the controlled task; high
cosine is not a guarantee of relevance.

On 2026-11-16, Mac/arm64, Python 3.14.10, CPU/Torch one thread used the existing
cached multilingual-e5-small revision listed above. Fifty-two papers produced
68 actual passage vectors. Network connections, model downloads and API calls
were prohibited. No user library was read or updated. Retrieval called the
production saved-vector service after discarding the encoder.

The CC0 dataset and judgments were frozen before inference. Eight domains each
contain two primary subtopics, three papers per subtopic; four isolated controls
complete the 52 records. Grade 2 means the same primary subtopic, grade 1 the same
declared broad domain, and grade 0 all other candidates. These are author-assigned
synthetic roles, not independent blinded expert judgments; real cross-domain
connections are outside the task. Forty seeds include 36 positives and four
no-related controls, English/Japanese, eight title-only sources and eight long
abstract sources with deliberately shared administrative appendices.

The comparators are lexical TF-IDF cosine (alphanumeric words/CJK bigrams,
sublinear TF and smoothed IDF), normalized mean saved-vector cosine, and #20
maximum pairwise passage cosine. All exclude the source and rank unique papers.
Recall/MRR reuse #9's aggregation with grades 1/2 relevant. nDCG uses exponential
gain and logarithmic discount. No-related controls are excluded from positive
metric denominators and reported separately. The shared tables above give all
primary and condition-level measurements.

The predeclared screen that max-pairwise overall nDCG is at least lexical nDCG
passes. MRR is lower than lexical, and title-only nDCG is also worse; this is not
uniform superiority or a release certification. The Japanese/English strata are
confounded by condition mix and do not establish language-level superiority.

Every long-source top result belongs to a grade-0 different domain. Recomputing
the winning passage pairs identifies part 1 in both source and target: shared
appendix/repeated title, without the abstract's topical opening. P001 (DNA repair)
ranking P013 (mitochondria) first is one preserved failure. All four isolated
controls still return ten candidates; top cosine is 0.8503–0.8617. The API has no
abstention threshold, and these scores do not justify a universal relevance cutoff.

Three independent CPU runs produced identical 120 method/seed rankings and
aggregate metrics. The JSON report records the frozen dataset digest, model
weights/config/tokenizer fingerprints, evaluator/service hashes, complete ranks,
strata, winning-pair diagnostics and source/index preservation. The reproduction
command above requires existing cached weights and a new output directory. No
resources are installed or downloaded automatically. Timings use unequal
precomputation/SQLite overhead and are not a fair performance benchmark.

Limits include authored synthetic judgments, a small fixed corpus, artificial
boilerplate stress, no independent expert assessment and no real-library or
cross-model/OS validation. Labels and the production ranking method remained
fixed throughout; failures are retained. Default CI tests use generated fixtures
for evaluation mathematics and mechanics, separate from this completed real-model run.
