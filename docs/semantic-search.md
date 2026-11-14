# ローカル意味検索 / Local semantic search

意味検索は **Title・Abstractだけ**を数値ベクトルに変換し、日本語・英語の自然文で
関連する文献候補を探します。EmbeddingはLLMによる文章生成ではなく、要約・翻訳も行いません。
著者・年・雑誌・DOIは表示用です。PDF本文・添付資料を埋め込みには含めません。
既定のキーワード検索、DOI/citekey完全一致、本文検索は維持します。
スコアはコサイン類似度であり、関連性の確率や研究上の証拠ではありません。
候補のcitekeyで全文検索し、科学的な主張は原本と照合してください。

Semantic search compares title/abstract meaning locally on CPU. Embeddings are numerical
representations, not LLM text generation. No external LLM API, PDF embeddings, OCR,
summarization or translation is involved. Keyword search remains the default.

## 初回設定 / Setup

```sh
bibdesk-rag --setup
```

1. BibDeskライブラリを選びます。原本・添付は変更しません。
2. 意味検索を使うか選びます。新規設定の既定は **利用しない** です。
3. 利用する場合、取得済みモデルがあればそのキャッシュを使います。未取得なら、
   モデルファイルのダウンロードを明示的に選びます。書誌テキストは送信しません。
4. 従来の検索索引とベクトルを、同じSQLiteへ作成・更新します。
5. 必要に応じて既存のMCP接続設定へ進みます。

Selecting no never loads inference dependencies, inspects a model cache or downloads a model.
Existing setups default to their current semantic choice. Only the selected
`semantic.enabled` option is saved; other TOML values/comments are preserved. Declining a
missing-model download leaves semantic search disabled. A failed download/load leaves the
previous configuration and index intact; a partially downloaded model cache can be retried.
No inference dependencies are installed by application runtime/setup.

開発用Python環境は `.python-version` の **3.12.13と `.venv` ひとつ**です。

```sh
pyenv local
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,semantic]'
.venv/bin/bibdesk-rag --setup
```

Pip installations that need semantic search use `pip install 'bibdesk-rag[semantic]'`
in their existing standard venv (a release containing this feature is required).
The extra adds NumPy and SentenceTransformers/PyTorch. Without it, keyword retrieval
works and setup explains missing dependencies if semantic search is selected.

Apple Silicon Homebrew builds include those inference dependencies in the Formula's
existing managed virtualenv, installed from fixed/checksummed offline wheels. **No companion
venv or pip modification of Cellar/libexec is needed.** Model weights are not bundled.
The pinned semantic wheels target Python 3.14, macOS 14+ arm64. Intel has the base
keyword/fulltext configuration; this semantic runtime lock does not cover Intel.
The added cryptography 50.0.2 source build remains unverified on Intel macOS;
see [packaging requirements](../packaging/homebrew/README.md).

## 統合した索引管理 / Unified index operations

```sh
bibdesk-rag --index update
bibdesk-rag -i rebuild
bibdesk-rag --index status --format json
bibdesk-rag --index check --format json
```

| Action | Behavior |
| --- | --- |
| `update` | Update bibliography and attachment text; if enabled, embed only new/changed title/abstract content. |
| `rebuild` | Re-extract existing derived text and regenerate enabled paper vectors. |
| `status` | Report metadata/text counts plus vector coverage, missing abstracts, stale vectors, model, dimensions and timestamps. |
| `check` | Check SQLite, foreign keys, FTS, vector lengths/norms, content hashes, part numbering and model consistency. No inference/model download. |

意味検索が無効なら従来の索引処理だけを行い、モデルをロードしません。保存済みベクトルは
自動削除せず保持します。無効の間にTitle/Abstractが変更されたベクトルはstatusでstale、
checkで警告として示し、再有効化後のupdateで更新します。
`--index update` は従来どおり添付本文の抽出も行いますが、ベクトル入力はTitle/Abstractだけです。

Enabled semantic indexing preflights the local model before opening SQLite for writing.
Schema migration, bibliography, attachment text and vectors share one transaction. Inference
failure or detected source mutation rolls back the entire update, including migration.
Recoverable extraction issues retain the existing per-file handling. Readers see a committed
snapshot. Status/check open SQLite read-only and do not need NumPy, Torch or a model cache.

## CLI検索 / Search examples

```sh
bibdesk-rag --paper search "相同組換え修復とDNA二本鎖切断" --mode semantic --top 5
bibdesk-rag --paper search "DNA repair mechanisms" --mode semantic --format json
bibdesk-rag --paper search "DNA複製ストレスにおけるRecQヘリカーゼの役割" --mode semantic
bibdesk-rag --paper search "クロマチン修飾と紫外線損傷耐性" --mode semantic
bibdesk-rag --paper search "糸状菌におけるゲノム安定性の維持" --mode semantic
bibdesk-rag --paper search "RecQ helicase and genome stability" --mode semantic
bibdesk-rag --paper search "Chromatin regulation and UV tolerance" --mode semantic
bibdesk-rag --paper search RecQ --mode keyword
```

`--top` overrides `semantic.default_limit` (5, valid range 1..100).
Keyword scopes/filters and `--per-paper` do not apply to semantic mode. Queries have a
2,000-character limit and must also fit the model's token budget. Add `--temp PATH` to
pin any command to a config without changing its saved selection.

## MCP

```json
{"name":"semantic_search_papers","arguments":{"query":"相同組換え修復","limit":5}}
```

`search_papers` remains keyword metadata search; `search_fulltext` remains attachment text
search. Semantic results include bibliography metadata, exact citekey/DOI, cosine score,
`title_only`/`has_abstract`, model identity, embedding timestamp, source bibliography path/hash,
and `metadata_similarity_unverified`. Paper IDs now refer to the same `papers` table as
other tools. No PDF chunk/page citation is fabricated. Abstracts have bounded MCP budgets;
`truncated_fields` records shortening. Identifiers/model identity remain exact. A result that
exceeds the global response budget returns guidance to reduce the limit.

MCP opens the same SQLite read-only, caches the CPU model between calls, and never downloads
models, installs dependencies or updates an index. Retrieved content remains untrusted data.

## 設定 / Configuration

Old configs without `[semantic]` remain valid and default to disabled. Setup changes only
`enabled` after an explicit choice. Other settings can be edited manually:

```toml
[semantic]
enabled = true
model = "intfloat/multilingual-e5-small"
revision = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
dimensions = 384
passage_prefix = "passage: "
query_prefix = "query: "
max_tokens = 512
default_limit = 5
batch_size = 16
# Optional; defaults to models/ beside the existing database:
# cache_dir = "~/.local/share/bibdesk-rag/models"
```

The existing top-level `database` selects the only SQLite file. There is no
`semantic.database` option. Config, database/sidecars and cache must not collide with
sources or Python/Homebrew installations. Relative paths are relative to the config.

For noninteractive setup, explicitly enable `[semantic]`, then run:

```sh
bibdesk-rag --semantic download
bibdesk-rag --index update
```

`--semantic download` is the sole noninteractive model-acquisition command. The trial
`--semantic update/rebuild/status` operations are replaced by unified `--index` actions.
Neither ordinary index/search commands nor MCP initiate a download.

## 保存・移行・差分 / Storage, migration, incremental reuse

The existing `index.sqlite3` retains the BRAG application identifier. Schema **1 → 2**
is migrated transactionally on update/rebuild; read-only keyword retrieval/status/check
can inspect schema 1 without migration. New schema 2 requires the compatible application;
older application versions that only understand schema 1 refuse it.

- `embedding_models` stores model ID, fixed revision, dimensions and a complete signature
  including prefixes, token limit, preprocessing and inference-library versions.
- Existing `embeddings.vector` stores little-endian float32. Rows now support either a legacy
  `chunk_id`, or `paper_id` plus `part`. Foreign keys and unique partial indexes protect both.
- Rows retain title/abstract SHA-256, model ID, timestamp and title-only flag. Existing legacy
  chunk vectors are preserved during migration/model switching; this feature creates none.
- `settings` records the active paper model and last vector-update time alongside existing
  source hash/path and index timestamps. No duplicate bibliography table is introduced.

Unchanged normalized title/abstract hashes reuse vectors even if author/year/journal changes.
Deleted papers cascade their vectors; missing-title-and-abstract entries are skipped/countable.
Title-only and abstract-only entries are supported. Changing the model/signature regenerates
paper vectors atomically and never mixes models. Source `.bib` and attachments stay read-only.

The previous unreleased separate `index-semantic.sqlite3` trial is not imported or deleted.
Run unified `--index update` to generate vectors in the existing index; remove obsolete
`semantic.database` settings manually if used. Source-library files are never changed.

## モデル入力・オフライン動作 / Inputs and offline operation

The existing BibTeX adapter converts LaTeX; semantic preprocessing normalizes Unicode NFC
and whitespace while retaining scientific identifiers. E5 inputs use
`passage: Title: … Abstract: …` and `query: …`. Vectors are L2-normalized.
Complete prefixed input token counts include special tokens. Long abstracts are split into
fitting parts, normally repeating the title. A very long title is split as part of the full
labelled text. Nothing is silently truncated. Maximum part cosine similarity determines
paper rank; each paper appears once. More parts can favor long papers; reranking is future work.
Similarity matrices are processed in batches of 1,024 rows.

Only the explicit setup download or `--semantic download` contacts Hugging Face, for fixed
revision weights/tokenizer/configuration/notices. No text is uploaded. Inference always uses
CPU, local-only model lookup, safetensors and `trust_remote_code=False`. No pickle weights,
remote Python code, OCR, ONNX export, fallback download or external LLM API is used.
To change models, update ID/revision/dimensions/prefixes/token limit, explicitly download
if missing, then run `--index update`. Backend-library changes also require vector update.

SentenceTransformers supplies E5 pooling/tokenization directly. Transformers alone retains
the Torch footprint while requiring custom pooling. ONNX would require a separate pinned
artifact/runtime validation; no ONNX benchmark or conversion is claimed.

## 困ったとき / Troubleshooting

| Symptom | Action |
| --- | --- |
| Semantic search disabled | Run `--setup` and choose semantic search. |
| Missing dependencies in pip installation | Install `.[semantic]` into the same development venv, or the released semantic extra. |
| Model missing/incomplete | Run `--setup` and explicitly allow download, or `--semantic download` after enabling. |
| Semantic vectors missing/stale | Run `--index update` with semantic search enabled. |
| Invalid vectors/dimensions | Confirm model settings, then `--index rebuild`. |
| Query too long | Shorten it; character and token limits both apply. |
| Memory pressure | Reduce `batch_size`, for example to 4. CPU execution needs no GPU. |
| Network unavailable | Index/search remain offline with an already cached model; postpone first download. |
| Older executable refuses schema 2 | Use the compatible updated application; do not overwrite the index with an older binary. |

## 検証 / Validation

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
BIBDESK_RAG_REAL_MODEL_CACHE=/absolute/path/to/models .venv/bin/python -m pytest tests/test_semantic.py -k real_multilingual
```

Normal tests use generated data and fake embeddings for mechanics. The opt-in E5 test uses
four synthetic English references and eight English/Japanese queries, blocks socket
connections, and checks expected top-two candidates plus real token splitting. This does
not benchmark a real library or Mac mini M1/16-GB performance. See the [validation report](semantic-validation.md).

Primary references: [E5 model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/fd1525a9fd15316a2d503bf26ab031a61d056e98/README.md),
[SentenceTransformer API](https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html).
