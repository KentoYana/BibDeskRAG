[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# SQLite・index・setup統合の実装・検証（2026-11-06）

Title・Abstractの意味検索を、既存SQLiteと索引管理・対話型setupへ統合しました。
利用手順は [意味検索ガイド](semantic-search.md) を参照してください。

## 実装

| 項目 | 現在の動作 |
| --- | --- |
| SQLite | 既存 `embedding_models` と `embeddings.vector` を再利用。BRAGのschema 1から2へトランザクション移行。 |
| 対応関係 | `paper_id`・分割番号、または既存chunkへの対応を保持。既存chunkベクトルも移行時に保持。 |
| 保存内容 | little-endian float32、内容SHA-256、モデルID・固定revision・次元・接頭辞・バックエンド版、日時・title-only。 |
| `--index update/rebuild` | 書誌・添付本文と、有効なTitle/Abstractベクトルを同じトランザクションで更新。モデル事前確認は書き込み前。 |
| `--index status/check` | 書誌・本文・ベクトルの件数・古さ・モデル情報と整合性を読取専用で確認。推論依存/モデルなしでも実行可能。 |
| `--setup` | 利用するか選択。モデル未取得時だけ別途ダウンロード確認。新規は無効が既定、既存設定は現在値を既定にする。 |
| 設定保存 | 明示選択した `semantic.enabled` だけを原子的に保存。他のTOML値・コメントを保持し、ハードリンク衝突・競合書込を拒否。 |
| 無効時 | 推論依存をロードせず、モデルを取得せず、保存済みベクトルは保持。古さを表示し、再有効化updateで変更分を再生成。 |
| 検索 | 既定keywordと既存MCPツールを維持。`--mode semantic` と `semantic_search_papers` は同じSQLite・論文IDを使用。 |
| Homebrew | Apple Siliconの推論依存は固定オフラインwheelを既存Formula環境へ導入。追加venvや実行時pipは不要。モデル本体は含まない。 |

## 検証

- Python 3.12.13の `.venv` で、実モデルを含む **449テスト成功**。
  モデルキャッシュ未指定の通常実行では実モデル1件をskipします。
- ruffと `git diff --check` は成功。
- 生成fixtureで、schema-1の旧chunkベクトルとFTSを保持する移行、移行・書誌・本文・ベクトルの
  一括ロールバック、モデル事前確認失敗時の無書込、差分再利用、無効化中の更新、再有効化、
  次元/正規化/内容ハッシュ/モデル/分割番号の破損検出を検証しました。
- setupは実際の選択フローを生成fixtureで検証。利用拒否、取得拒否、取得失敗・中断、
  取得済みキャッシュ再利用、既存設定とコメントの保持、linked config拒否、
  既存keyword索引を保持した場合のベクトル未作成案内を含みます。
- 実TTYでもsetupの利用選択・既存モデルキャッシュ再利用・統合SQLite作成を確認しました。
  既存Codex登録は変更せず、stdio handshakeを確認しました。
- 実E5モデルのオフラインテストは英語の合成4文献・日英8クエリで、期待候補がすべて上位2件。
  長いAbstractの実トークン分割、差分更新、重複排除も成功。テスト中のsocket接続を拒否しました。
- 実CLIのupdate/status/check・日本語検索、実stdio MCPの意味検索が成功。
  変更なしupdateは **embedded=0, reused=4**。読取操作前後のSQLite SHA-256は不変でした。
- Homebrew同一環境での実モデル検索が成功。基本検索・PDF/CSV・MCPはpackage smokeで検証しました。

## 配布方式と記録

`tools/lock_semantic_resources.py` はテスト済み環境から追加依存を辿り、Python 3.14・
macOS 14+ arm64用の31 wheelを取得し、PyPIのSHA-256と照合して固定します。
`build-resources.json` の `semantic_runtime` 行を既存のoffline bundleへ同梱し、
Formulaはその既存virtualenvへ無通信で導入します。各wheel内のライセンス・noticeを保持します。
Pipのsemantic extraは任意のままです。Intel版の推論wheel lockは含まず、基本検索を維持します。

ローカル専用keg `local/bibdesk-rag-semantic-test/bibdesk-rag-semantic-test` を用い、
通常の公開版を置き換えずにソース導入・更新・brew style・strict audit・brew testが成功しました。
検証ログ・生成データ・配布物はgit対象外の `.local/integrated-validation/` に保存します。
この初期検証段階では公開、push、Release、実ライブラリの索引更新は行っていません。後続の実ライブラリ検証は下記に記録します。

## 環境と制約

- 開発環境は `.python-version` の3.12.13と `.venv` へ統一済み。
  不足OpenSSL 3を追加してSSLを修復し、`.venv-semantic` は削除しました。
  global pyenv/pip・Python本体・既存OpenSSL 4は変更していません。
- Homebrewは配布用の既存Python 3.14環境を使います。開発用venvとは別の役割です。
- schema 2へ移行したSQLiteは、schema 1しか理解しない旧アプリでは開けません。
- 試作の別 `index-semantic.sqlite3` は読み込み・削除しません。統合updateで再生成します。
  試作の `semantic.database` を使った設定では、その項目を手動で削除してください。
- 実ライブラリ全体の定量的な精度評価、Mac mini M1/16GBでの速度・最大メモリは未検証です。
- 最大partスコアで集約するため、長い文献はpart数により順位が有利になる場合があります。
- hybrid、PDF embedding、OCR、GUI、外部API、要約・翻訳は対象外です。

## 最終配布検証

- sdist・wheel・固定offline bundleのビルドと3アーカイブ検査が成功。
  wheel内のアプリPython/同梱リソースは最終ソースとバイト一致を確認しました。
- sdistとwheelをそれぞれ空のPython 3.12 venvへ導入し、`pip check` と
  `tools/package_smoke.py` が成功。基本pip環境にNumPy/SentenceTransformersが
  自動導入されないことも確認しました。使い捨て検証venvは削除済みです。
- 最終Homebrew Formulaは検証用revision `0.3.1_2 → 0.3.1_3` で更新。
  更新直後、生成した原本・設定・従来索引・統合ベクトル索引・モデルsafetensorsの
  SHA-256がすべて不変でした。その後に明示的な索引更新を行う配布smokeも成功。
- 最終HomebrewのPythonモジュールはソースと一致。`brew style`、`brew test`、
  `brew audit --strict` が成功し、同じHomebrew環境で実E5の日本語検索も成功しました。
- 最終配布物とSHA256SUMSは `.local/integrated-validation/final-dist/`、実CLI/MCP結果は
  `.local/integrated-validation/real-cli-mcp.json`、最終Homebrew検索結果は
  `.local/integrated-validation/final-homebrew-search.json` に保存しました。
- この配布検証段階では通常の公開版の実行ファイルリンク・Codex登録・実ライブラリは変更していません。

## 後続の実ライブラリ・通常Homebrew・Codex検証

- 明示的に選択された実ライブラリの既存SQLiteをschema 1から2へ移行し、
  1,718文献から1,817ベクトルを生成しました。99文献は分割入力、232文献はTitleのみです。
  移行前SQLiteのバックアップを保存し、既存の書誌・添付・本文・対応テーブルの内容は保持しました。
- 変更なしの再updateでは生成0・再利用1,718。原本BibTeXと読み取り可能な添付1,555ファイルの
  SHA-256・サイズ・更新日時は不変でした。既存の未解決パス5件は解決済みとは扱いません。
- 通常のHomebrew Formulaをローカル更新し、引数なしのCLI/MCPが移行済みSQLiteと同じ設定を
  使用することを確認。既存のCodex登録は保持しました。brew style・strict audit・testが成功しました。
- CodexでMCPを再起動後、実際のこの会話からkeyword、日本語・英語semantic、選択文献のfulltextが
  成功。7つの読み取り専用ツールが認識され、全文結果にはPDFページ・パス・chunk IDが付きました。
- モデルは取得済みキャッシュを使用し、この検証では新規モデル取得や外部API送信を行っていません。
- 検索スコアは確率ではありません。語義の曖昧さによる不適切な上位候補があり、keywordと全文照合を
  併用します。hybrid自動融合は未実装です。これはメタデータ検索の確認であり、科学的主張の原本検証ではありません。

<a id="english"></a>

# Integrated SQLite, index and setup validation (2026-11-06)

Title/abstract semantic retrieval shares the existing SQLite index and management commands.
See the [semantic search guide](semantic-search.md#english) for usage.

## Implementation and generated-fixture checks

- Schema 1 migrates transactionally to schema 2, reusing `embedding_models` and
  `embeddings.vector` and preserving legacy chunk vectors. Paper ID/part number,
  little-endian float32 vectors, content hashes, model/revision/dimensions/prefixes,
  backend version, timestamps and title-only flags are persisted.
- `--index update/rebuild` atomically updates bibliography, indexed text and enabled
  vectors after offline model preflight. `status/check` are read-only and work without
  inference dependencies. Disabled vectors are retained and their staleness reported.
- Interactive setup separately asks whether to use semantic retrieval and, if missing,
  whether to acquire the model. New installs default to disabled. Only the explicitly
  selected enabled flag is saved atomically; other TOML values/comments are retained.
- All 449 Python 3.12.13 tests passed with the opt-in real model; ordinary tests skip
  that one test unless its pre-downloaded cache is specified. Ruff and diff checks passed.
  Generated fixtures cover migration/FTS/legacy-vector retention, transaction rollback,
  incremental reuse, disabled/re-enabled updates, malformed vectors/model/hash/parts,
  setup refusal/failure/interruption, config collision safety and existing CLI/MCP bounds.
- Offline actual E5 checks use four synthetic papers and eight Japanese/English queries,
  with expected papers in the top two. Token splitting, incremental reuse and deduplication
  passed while socket connections were blocked. Actual CLI and stdio MCP searches passed.
- Clean sdist/wheel installs, pip checks and package smoke tests passed. Base pip installs
  do not automatically install NumPy or SentenceTransformers. Archive contents and licenses
  were checked. Local Homebrew source installs, revision upgrades, style, strict audit,
  Formula tests and same-environment E5 retrieval passed; synthetic sources, config, SQLite
  and model hashes were preserved across upgrade.

## Distribution and environment

Apple Silicon Homebrew installs 31 PyPI SHA-256-verified Python 3.14/macOS 14+ arm64
inference wheels into its existing managed venv, from the locked offline resource bundle.
Original wheel license/notice files are retained. Model weights are separate and acquired
only by explicit choice. Pip keeps semantic dependencies optional. Intel retains base
retrieval; Intel inference wheels and Intel semantic execution are not validated.

Development uses Python 3.12.13 and the single `.venv`. Installing the missing OpenSSL 3
dependency restored that interpreter's SSL; global pyenv/pip and existing OpenSSL 4 were
unchanged. Homebrew's managed Python 3.14 is a separate distribution environment.

## Subsequent real-library and connected Codex validation

The selected live schema-1 SQLite was backed up, migrated to schema 2, and populated with
1,817 vectors for 1,718 papers: 99 split papers and 232 title-only papers. Existing paper,
attachment, text-chunk and association table contents were retained. A second unchanged
update generated zero papers and reused 1,718. Original BibTeX and 1,555 readable attachment
hashes, sizes and modification times were unchanged; five pre-existing unresolved paths
remain unresolved.

The normal Homebrew executable was locally upgraded and used the migrated SQLite via the
existing shared config. The Codex registration was unchanged. After MCP restart, actual
calls in this conversation succeeded for keyword, Japanese/English semantic and
selected-paper fulltext search. Seven read-only tools were available, with PDF page/path/
chunk provenance in fulltext results. Cached weights were used without further model
download or external API submission. Private reports and sources are excluded from release
archives.

## Limits

Schema-1-only older applications cannot open the migrated schema-2 index. Experimental
separate semantic databases are not read or deleted; experimental `semantic.database`
config entries must be removed manually. Maximum-part scoring can favor long papers.
Ambiguous terms can rank irrelevant candidates; use keyword searches and fulltext checks.
This verifies retrieval, not scientific claims against original PDFs. Quantitative
whole-library relevance, M1/16GB performance and peak memory remain unverified. Automatic
hybrid fusion, PDF embeddings, OCR, GUI, external APIs, summaries and translation are out
of scope.

## 追加・変更したファイル

- `CHANGELOG.md`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `config.example.toml`
- `docs/architecture.md`
- `docs/homebrew-validation.md`
- `docs/semantic-search.md`
- `docs/semantic-validation.md`
- `docs/usage.md`
- `docs/validation.md`
- `packaging/homebrew/Formula/bibdesk-rag.rb`
- `packaging/homebrew/README.md`
- `packaging/homebrew/build-resources.json`
- `pyproject.toml`
- `src/bibdesk_rag/cli.py`
- `src/bibdesk_rag/cli_arguments.py`
- `src/bibdesk_rag/cli_resources.py`
- `src/bibdesk_rag/config.py`
- `src/bibdesk_rag/database.py`
- `src/bibdesk_rag/embeddings.py`
- `src/bibdesk_rag/indexer.py`
- `src/bibdesk_rag/mcp_server.py`
- `src/bibdesk_rag/progress.py`
- `src/bibdesk_rag/resources/config-template.toml`
- `src/bibdesk_rag/resources/examples.txt`
- `src/bibdesk_rag/resources/manual.txt`
- `src/bibdesk_rag/semantic.py`
- `src/bibdesk_rag/semantic_config.py`
- `src/bibdesk_rag/setup.py`
- `src/bibdesk_rag/setup_connection.py`
- `tests/test_config_cli.py`
- `tests/test_mcp.py`
- `tests/test_semantic.py`
- `tests/test_semantic_integration.py`
- `tests/test_setup.py`
- `tests/test_setup_semantic.py`
- `tools/lock_semantic_resources.py`
- `tools/package_smoke.py`
