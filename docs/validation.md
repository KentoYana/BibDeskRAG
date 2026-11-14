[日本語](#japanese) | [English](#english)

<a id="english"></a>

# Validation record

Current local execution uses only pyenv Python 3.14.10; see the
[single-version validation](python314-validation.md).

For the unreleased PDF dependency addition, see the
[2026-11-14 validation record](pdf-dependency-validation.md).

Date: 2026-11-01 (Asia/Tokyo). Machine: Apple Silicon macOS. Application version: 0.1.0.

Phases 1–3 below record the initial generated-fixture validation. The later
read-only real-library and Codex checks are recorded separately under
[Subsequent Codex desktop verification](mcp-validation.md#subsequent-codex-desktop-verification).
Publication statements in those phases describe the pre-release validation;
see the [v0.1.0 release](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0)
for the public distribution.

## Phase 1: ingestion, indexing and CLI

The full suite passed **115 tests** on the project-local pyenv Python **3.12.13** and on
an independent venv created from Homebrew Python **3.14.10**. The latter used the built
wheel, not an editable source installation. Ruff and `pip check` passed.

Coverage includes BibDesk fields, LaTeX, string macros and concatenation, groups,
multiple attachments, relative/absolute/Japanese paths, missing sources, DOI
normalization and duplicates, modern macOS bookmarks after a file rename, PDF pages,
supplementary PDFs, CSV/TSV/XLSX rows and cells, formula preservation, ZIP/XLSX safety,
BM25 ranking, per-paper limits and biological identifier normalization.

Incremental tests assert that unchanged attachments are neither rehashed nor
re-extracted; mtime-only changes hash without extraction; content changes re-extract;
source deletion removes stale hits; unambiguous DOI renames preserve internal IDs;
ambiguous DOI matches remain separate. Tests cover transaction rollback, cascade
removal, FTS integrity, read-only SQLite connections, output/source collisions,
hard links/SQLite sidecars, refusing failed attachment diagnostic paths, and refusing unrelated databases without changing their
bytes or permissions.

Synthetic source SHA-256 values were checked before and after indexing. A network-denial
test exercises library ingestion, extraction, search and context construction with
socket connection and DNS entry points blocked. No real BibDesk library was registered,
modified or used as a fixture. No home-directory scan was performed.

## Phase 2: context and MCP

Bounded contexts preserve citation/file/page/sheet/row/chunk fields and report omitted
or unverified evidence. Snippets retain literal source values, including `10-15` and
`Δset-1`; only the search index is normalized. Query text is escaped into literal FTS
terms rather than interpreted as query syntax.

The official MCP Python SDK **2.3.0** completed a real stdio initialize handshake and
calls to all six tools. Source and index hashes stayed unchanged. The Codex CLI
recognized an ephemeral stdio server configuration without altering user settings.
This is not a claim that an actual Codex model conversation invoked the tools.
Details and a reproducible client are in [mcp-validation.md](mcp-validation.md).

## Phase 3: packages and distribution

- `python -m build`: sdist and wheel generated with pinned setuptools/wheel.
- Editable installation with pip in the local pyenv venv: passed.
- Normal wheel installation into a clean Homebrew Python 3.14 venv: passed; full
  115-test suite, dependency consistency and installed CLI/MCP smoke passed.
- Normal sdist installation into a separate Python 3.12 venv: passed; installed CLI/MCP
  smoke and dependency consistency passed.
- Homebrew local-tap source installation, `brew style`, `brew audit --strict`, and
  substantive `brew test`: passed. CLI/MCP also passed with `PATH=/usr/bin:/bin`,
  where pyenv is unavailable. The real revision upgrade and exact user-data hash
  comparison are recorded in [homebrew-validation.md](homebrew-validation.md).
- Final sdist contents were checked for required source/docs and absence of user
  libraries/extracted data; all 17 final wheel modules byte-match the tested
  Python 3.14 installation.

The repository's Formula remains an explicitly disabled unpublished template. The
usable validation Formula refers only to real local archives and their SHA-256 values.
No GitHub push, release publication, remote tap creation, or PyPI upload was performed.

## Remaining validation boundaries

- The initial automated tests used generated data only. Later real-library access
  and actual Codex tool calls are documented separately in the MCP validation record.
- Old native alias records are supported through Apple's conversion API but have no
  authentic legacy fixture; modern bookmark moved-file resolution was exercised.
- Intel backend wheels are included, but an Intel Mac was not available for execution.
- Python 3.11/3.13 and Linux are configured in CI; those CI runs have not run locally.
- Public Release/tap URL availability, `brew audit --online`, and remote CI results
  depend on later authorized publication.
- OCR, embeddings, semantic/hybrid search and advanced figures/tables are future work.
  The interface and embedding model/version/dimension schema are present.

---

<a id="japanese"></a>

# 検証記録

日付：2026-11-01（Asia/Tokyo）。実機：Apple Silicon macOS。アプリ版：0.1.0。

以下の第1〜3段階は初期の生成fixtureによる検証記録です。後日の実ライブラリ読み取り専用検証とCodex確認は [後日のCodexデスクトップ検証](mcp-validation.md#後日のcodexデスクトップ検証) に別記しています。各段階の公開状況はリリース前の記録であり、公開配布については [v0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0) を参照してください。

## 第1段階：取込・索引・CLI

プロジェクトローカルのpyenv Python **3.12.13** と、Homebrew Python **3.14.10** から作った独立venvの両方で **115テスト** が成功しました。後者はeditableインストールではなくビルド済みwheelを使用しました。Ruffと `pip check` も成功しました。

対象にはBibDeskフィールド、LaTeX、文字列マクロ・連結、グループ、複数添付、相対・絶対・日本語パス、欠損原本、DOI正規化・重複、名前変更後の現代macOS bookmark、PDFページ、補足PDF、CSV/TSV/XLSX行・セル、数式保持、ZIP/XLSX安全性、BM25順位、文献ごとの上限、生物学的識別子の正規化を含みます。

差分テストでは、未変更添付を再ハッシュ・再抽出しないこと、mtimeだけの変更はハッシュのみ、内容変更は再抽出、原本削除は古い検索結果を除去、一意なDOIによるキー変更は内部IDを保持、曖昧なDOI対応は別文献を保持することを確認しました。トランザクションのロールバック、連鎖削除、FTS整合性、SQLite読み取り専用接続、出力・原本衝突、ハードリンク・SQLite補助ファイル、失敗した添付の診断パス拒否、無関係なDBをバイト列・権限を変えずに拒否することも検証しました。

合成原本のSHA-256を索引化前後で確認しました。ネットワーク拒否テストではsocket接続・DNS入口を遮断し、ライブラリ取込、抽出、検索、context生成を実行しました。実際のBibDeskライブラリは登録・変更せずfixtureにも使っていません。ホームディレクトリの走査も行っていません。

## 第2段階：contextとMCP

文字数制限付きcontextは引用・ファイル・ページ・シート・行・chunk情報を保持し、省略・未検証の証拠を報告します。抜粋は `10-15` や `Δset-1` を含む原文を保持し、正規化は索引だけに適用します。検索語はクエリ構文として解釈せず、リテラルFTS語句へエスケープします。

公式MCP Python SDK **2.3.0** で実際のstdio初期化と6ツールすべての呼出しに成功し、原本・索引ハッシュは不変でした。Codex CLIは利用者設定を変えず一時的なstdioサーバー設定を認識しました。これは実際のCodexモデル会話がツールを使ったという主張ではありません。詳細と再現用クライアントは [MCP検証](mcp-validation.md#japanese) にあります。

## 第3段階：パッケージと配布

- `python -m build`：固定setuptools/wheelでsdist・wheelを生成。
- ローカルpyenv venvへのpip editableインストール：成功。
- クリーンなHomebrew Python 3.14 venvへの通常wheelインストール：成功。全115テスト、依存整合性、インストール済みCLI/MCP smokeも成功。
- 別のPython 3.12 venvへの通常sdistインストール：成功。インストール済みCLI/MCP smokeと依存整合性も成功。
- Homebrewローカルtapのソースインストール、`brew style`、`brew audit --strict`、実質的な `brew test`：成功。pyenvがない `PATH=/usr/bin:/bin` でもCLI/MCPが成功。実際のrevision upgradeと利用者データの厳密なハッシュ比較は [Homebrew検証](homebrew-validation.md#japanese) に記録。
- 最終sdistの必須ソース・文書と個人ライブラリ・抽出データの不在を確認。最終wheelの全17モジュールが検証済みPython 3.14インストールとバイト単位で一致。

リポジトリ内のFormulaは明示的に無効化した未公開テンプレートのままです。検証用Formulaは実在するローカルアーカイブとSHA-256だけを参照します。GitHub push、Release公開、リモートtap作成、PyPIアップロードは行っていません。

## 検証範囲の残り

- 初期自動テストは生成データのみです。後日の実ライブラリアクセスと実際のCodex呼出しはMCP検証記録に別記しています。
- 古いネイティブaliasはApple変換API経由で対応していますが、真正な旧形式fixtureはありません。現代bookmarkの移動追跡は検証しました。
- Intel用バックエンドwheelは含みますが、Intel Mac実機では実行していません。
- Python 3.11/3.13とLinuxはCIに設定済みですが、そのCI実行をローカルで行ってはいません。
- 公開Release/tap URL、`brew audit --online`、リモートCI結果は後日の許可された公開に依存します。
- OCR、埋め込み、意味・ハイブリッド検索、高度な図表処理は将来項目です。インターフェースと埋め込みモデル・版・次元数スキーマは用意しています。

## Semantic extension validation — 2026-11-05

The earlier sections are historical keyword/fulltext evidence. Title/abstract-only
semantic retrieval is now implemented; hybrid retrieval and OCR remain outside scope.
Generated-fixture tests and the opt-in E5 test are in `tests/test_semantic.py`; fake
embedding results establish mechanics only. The actual multilingual model was downloaded
explicitly into project-local ignored validation data, never the user's library.
Eight English/Japanese queries against four synthetic English references placed every
predefined expected reference in the top two. Socket connections were blocked during
model loading, index construction and retrieval. This is a small relevance check,
not validation on a real bibliography or an M1/16-GB performance benchmark.

意味検索の検証は生成した文献集合だけで実施しました。ダミーモデルの結果と実E5モデルの
結果を区別し、実ライブラリの検索品質やM1のメモリ性能を確認したとは扱いません。
設定・実行方法は [意味検索ガイド](semantic-search.md) を参照してください。

## Unified SQLite/index/setup extension — 2026-11-06

This supersedes the separate semantic-database trial. Paper vectors now reuse the existing
embedding tables, schema migration and all index data share one transaction, and `--index`
manages both retrieval methods. Setup explicitly chooses semantic use/model acquisition.
Apple Silicon Homebrew uses one managed environment with locked offline inference wheels.
See the [current validation report](semantic-validation.md); older dated results above
remain historical evidence, not the current feature boundary.
