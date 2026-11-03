[日本語](#japanese) | [English](#english)

<a id="english"></a>

# Architecture

The only authoritative data is the user-selected BibDesk library and its explicitly linked attachments. The application never saves a `bibdeskparser.Library`, resolves online metadata, evaluates spreadsheet formulas, executes document instructions, or downloads an embedding model.

## Data flow

`Library / Entry.files → normalized PaperRecord → transactional indexer → SQLite → SQLiteSearch → CLI / bounded context / read-only MCP`

The read adapter uses BibDeskParser's public interfaces for bibliography, groups and attachments. The one isolated compatibility bridge obtains native bookmark/alias bytes from an already parsed entry when its public path is missing. Apple's native resolution disables UI and volume mounting. It never updates the library.

## Storage

- `papers`: stable internal integer primary key; exact case-sensitive unique citekey; normalized DOI (not unique); normalized metadata; original exported BibTeX; a fingerprint; normalized FTS fields.
- `attachments`: one resolved path per record; type, size, nanosecond mtime, SHA-256, extraction status, error and ZIP member manifest.
- `paper_attachments`: many-to-many association with original locator and per-paper role. Shared source paths share chunks.
- `chunks`: stable ID until re-extraction; attachment ID; source type; page start/end, sheet and row range, archive member; original extracted text; separate normalized search text; chunk order.
- `papers_fts`, `chunks_fts`: independent FTS5 external-content indexes updated by insert/delete/update triggers in the same transaction as their source rows.
- `settings`: schema-independent library hash, path, extraction options and last successful index timestamp.
- `embedding_models`, `embeddings`: optional model name/version/dimensions/config, chunk ID and source hash. A future backend must key vectors by model and source content, and must never auto-send text externally. No current code writes these tables.

`PRAGMA application_id` (`0x42524147`, ASCII `BRAG`) identifies an application-owned index, and `PRAGMA user_version` guards schema compatibility. Existing unrelated databases are inspected read-only and refused before opening for writes or changing permissions. Schema initialization is transactional. Foreign keys cascade deletions into links/chunks/embedding rows. The indexer holds one immediate write transaction per update, so readers see the last committed state. Search/MCP use `mode=ro` and `query_only`. Doctor performs the FTS integrity INSERT only on an in-memory backup.

## Incremental semantics

The bibliography is re-read on update (usually small relative to attachments). Metadata fingerprints avoid unnecessary writes. Identical size/mtime skips opening attachments; changed stat triggers SHA-256; identical content reuses chunks. `--verify-hashes` overrides the stat shortcut, and `--index rebuild` or extraction-option changes force re-extraction. Index errors for individual sources clear stale chunks and remain visible; unexpected transaction errors roll back the snapshot. Source changes detected during parse/extraction abort the update.

An unambiguous old/new DOI allows a citation-key rename to preserve the paper ID. Duplicate DOI entries are never merged. Distinct path copies of identical content remain distinct attachments; the required common-path many-to-many sharing is deduplicated.

## Retrieval semantics

FTS expressions consist only of quoted AND terms. Unicode NFKC/case folding, dash normalization and compact identifier tokens handle `hH3-K4R`, `Δset-1`, `mus-9` and `RecQ`. Normalized text is used only for matching, while evidence is verbatim extracted text. Exact DOI/citekey queries do not depend on FTS ranking.

Metadata uses weighted BM25. Search summaries bound text fields (including 4,000-character abstracts) and explicitly report shortened fields; exact citekeys, DOIs and source paths are preserved. Full text uses BM25 and streams ranked candidates while enforcing a per-paper limit, avoiding a fixed candidate window monopolized by one paper. Snippets retain verbatim source characters, including numerical ranges and Greek identifiers. Default all-scope retrieval selects metadata candidates then searches their attachments. Explicit `metadata_query` is a strict first-stage constraint; no candidate means no evidence. Fulltext scope searches all indexed attachments unless citekeys restrict it.

The context builder counts citation headers and delimiters in the character budget. It returns evidence and unverified limitations separately. These labels are an instruction boundary, not a claim that prompt injection can be made impossible in an external LLM. The program itself never executes any retrieved content.

## Resource and format limits

PDF pages never cross chunk boundaries. CSV/TSV use logical record numbers, XLSX uses sheet coordinates, and ZIP preserves member paths without extracting to disk. ZIP and XLSX preflight rejects absolute/traversal paths, symlinks, ambiguous duplicate member paths, encrypted entries and excessive member counts/expanded bytes/ratios. An outer ZIP and its XLSX members share an aggregate expansion budget. XLSX XML is checked with defusedxml. Nested ZIP extraction is intentionally disabled.

The configured byte and chunk limits bound ordinary ingestion. pypdf still parses individual page content in-process; this is not an OS sandbox for adversarial parser CPU/memory consumption. A future worker-process resource limiter is a separate hardening improvement, as is OCR.

## Packaging

PEP 621 metadata, setuptools, sdist and wheel are independent from pyenv. Development uses the local pinned interpreter and pip. Homebrew uses its own Python virtualenv and checksum-pinned resources. Data paths are user-owned, outside the installation. The checked-in Formula cannot represent a release until actual immutable source/bundle URLs and hashes are supplied.

---

<a id="japanese"></a>

# 設計

正本は、利用者が選択したBibDeskライブラリと明示的にリンクされた添付ファイルだけです。アプリは `bibdeskparser.Library` を保存せず、オンライン書誌情報の取得、表計算の数式評価、資料中の命令実行、埋め込みモデルのダウンロードも行いません。

## データの流れ

`Library / Entry.files → 正規化した PaperRecord → トランザクション型 indexer → SQLite → SQLiteSearch → CLI / 文字数制限付き context / 読み取り専用 MCP`

読み取りアダプターは、書誌情報・グループ・添付にBibDeskParserの公開インターフェースを使います。公開パスがない場合だけ、分離した互換処理で解析済みエントリのネイティブbookmark/aliasバイト列を取得します。Appleのネイティブ解決ではUI表示とボリュームのマウントを無効にし、ライブラリを更新しません。

## 保存構造

- `papers`：安定した内部整数主キー、大文字小文字を区別する一意なcitekey、正規化DOI（一意ではない）、正規化書誌情報、元の出力BibTeX、フィンガープリント、正規化FTSフィールド。
- `attachments`：1レコードにつき1つの解決済みパス、種別、サイズ、ナノ秒mtime、SHA-256、抽出状態、エラー、ZIPメンバー一覧。
- `paper_attachments`：元の参照位置と文献ごとの役割を持つ多対多の関連。同じ原本パスはチャンクを共有します。
- `chunks`：再抽出まで安定したID、添付ID、資料種別、開始・終了ページ、シートと行範囲、ZIPメンバー、抽出した原文、独立した正規化検索文、チャンク順序。
- `papers_fts`、`chunks_fts`：独立したFTS5外部コンテンツ索引。原本行と同じトランザクション内でinsert/delete/updateトリガーにより更新します。
- `settings`：スキーマに依存しないライブラリのハッシュ、パス、抽出設定、最後に成功した索引日時。
- `embedding_models`、`embeddings`：将来用のモデル名・版・次元数・設定、チャンクIDと原本ハッシュ。将来のバックエンドはモデルと原本内容をベクトルのキーにし、本文を外部へ自動送信してはいけません。現在これらのテーブルへ書き込むコードはありません。

`PRAGMA application_id`（`0x42524147`、ASCIIで `BRAG`）でアプリの索引を識別し、`PRAGMA user_version` でスキーマ互換性を確認します。無関係な既存DBは読み取り専用で調べ、書き込みや権限変更の前に拒否します。スキーマ初期化はトランザクション内で行い、外部キーによりリンク・チャンク・埋め込み行を連鎖削除します。索引更新ごとに1つのimmediate書き込みトランザクションを保持するため、読み手には最後にコミットした状態が見えます。検索・MCPは `mode=ro` と `query_only` を使います。DoctorのFTS整合性INSERTはメモリ内バックアップだけで実行します。

## 差分更新の規則

更新時には書誌情報を再読込します（通常は添付より小規模です）。書誌フィンガープリントで不要な書き込みを避けます。サイズ・mtimeが同一なら添付を開かず、stat変更時にはSHA-256を計算し、内容が同じならチャンクを再利用します。`--verify-hashes` はstatによる省略を無効にし、`--index rebuild` または抽出設定の変更は再抽出を強制します。個別資料のエラーは古いチャンクを消去して記録し、予期しないトランザクションエラーでは全体をロールバックします。解析・抽出中に原本変更を検出すると更新を中止します。

旧・新DOIの対応が一意なら、citekey変更時も文献IDを保持します。DOIが重複したエントリは統合しません。内容が同じでも異なるパスのコピーは別添付として扱い、共通パスの多対多共有だけを重複排除します。

## 検索の規則

FTS式は引用符付きAND語句だけで構成します。Unicode NFKC・case folding、ダッシュ正規化、識別子の連結トークンにより `hH3-K4R`、`Δset-1`、`mus-9`、`RecQ` に対応します。正規化文は照合だけに使い、証拠には抽出原文を返します。DOI/citekey完全一致はFTS順位に依存しません。

書誌検索は重み付きBM25です。検索要約は4,000文字のabstractを含む各テキスト欄に上限を設け、省略した欄を明示します。citekey・DOI・原本パスは正確に保持します。本文検索はBM25の候補を順位順に読み、文献ごとの上限を適用するため、固定候補枠を1文献が占有しません。抜粋は数値範囲やギリシャ文字の識別子を含め原文の文字を保持します。既定のall-scope取得では書誌候補を選んでから添付本文を検索します。明示的な `metadata_query` は厳密な第1段階の制約で、候補がなければ証拠を返しません。fulltext範囲はcitekey制限がなければ索引内の全添付を検索します。

context生成は引用ヘッダと区切りも文字数予算に含めます。証拠と未検証の制約を分けて返します。これらのラベルは命令の境界を示すもので、外部LLMでのプロンプトインジェクションを完全に防げるという主張ではありません。プログラム自体は取得内容を実行しません。

## 資源と形式の制限

PDFのチャンクはページを跨ぎません。CSV/TSVは論理レコード番号、XLSXはシート座標、ZIPはディスクへ展開せずメンバーパスを保持します。ZIP/XLSXの事前検査は絶対・逸脱パス、symlink、曖昧な重複メンバーパス、暗号化、件数・展開量・圧縮率の超過を拒否します。外側ZIPと内部XLSXは展開量の合計予算を共有します。XLSX XMLはdefusedxmlで検査し、入れ子ZIPの抽出は意図的に無効にしています。

設定したバイト数・チャンク数制限は通常の取込を制限します。ただしpypdfは個別ページを同一プロセス内で解析するため、悪意ある入力によるCPU・メモリ消費をOSで隔離するものではありません。ワーカープロセスによる資源制限とOCRは将来の別改善です。

## パッケージング

PEP 621メタデータ、setuptools、sdist、wheelはpyenvに依存しません。開発はローカル固定Pythonとpipを使い、Homebrewは独自のPython virtualenvとチェックサム固定resourceを使います。データは利用者所有のインストール先外に置きます。リポジトリ内のFormulaは、実在する不変のソース・bundle URLとハッシュが揃うまでリリース用ではありません。
