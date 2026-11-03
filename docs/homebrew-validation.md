[日本語](#japanese) | [English](#english)

<a id="english"></a>

# Homebrew validation

## Interactive setup: installation and upgrade — 2026-11-02

The unreleased `setup` implementation was built and installed through an actual
local Homebrew Formula, then upgraded from Formula version `0.1.1` to
`0.1.1_1`. The application version remains `0.1.1`; revision 1 exists only in the
local test Formula. No push, GitHub Release, or public Formula update was made.

Validation machine: macOS 26.7.2, Apple Silicon arm64, Homebrew
7.0.11-102-gbb45d71, Homebrew Python 3.14.10.

### Local Formula and build inputs

The generated Formula is
`local/bibdesk-rag-setup-test/bibdesk-rag-setup-test`. It uses the repository's
Formula template with the same install/test methods and fixed resource inputs.
Only the local Formula class/name, a custom `keg_only` reason, and the upgrade's
`revision 1` distinguish its packaging from the generated application Formula.
The separate keg avoids replacing the already linked public `bibdesk-rag`
0.1.1 installation.

- Source sdist SHA-256:
  `e931683866a108eb8ef8682b76e47f419987e8c0c01c00eb6bab672409bc9141`.
- Backend bundle SHA-256:
  `5a4126a9d5bedf696db851154cb8923952aab654e805e69687ca14bd4be6b292`.
- All 29 installed runtime dependency versions matched
  `packaging/homebrew/resources.json`, including `anyio` 4.15.1. This verifies
  the Formula's fixed dependencies rather than a fresh pip dependency resolution.
- All 20 installed application Python modules were byte-for-byte identical to
  `src/bibdesk_rag/`, both before and after the upgrade.
- Each keg contains an isolated Homebrew Python virtual environment with
  `include-system-site-packages = false`. The existing Formula's offline
  `PIP_NO_INDEX=1` backend build mechanism was retained.

The source and backend URLs are local `file://` URLs, and the homepage is the
explicitly non-public `example.invalid` test value. These generated Formulae
must not be published. Archives, checksums, and copies of both Formula revisions
are retained under `.local/setup-homebrew-validation/` and excluded from Git.
Adding this validation record can change a subsequent sdist hash; the installed
application modules were compared separately with the working tree.

### Executed Homebrew operations

The following named operations were executed through the logged runner, with
`HOMEBREW_NO_AUTO_UPDATE=1`, `HOMEBREW_NO_INSTALL_CLEANUP=1`,
`HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1`, `HOMEBREW_NO_ASK=1`, and
`HOMEBREW_NO_ANALYTICS=1`. Homebrew trust settings used the task's isolated
`XDG_CONFIG_HOME`; no global pip or pyenv settings were changed.

```sh
formula=local/bibdesk-rag-setup-test/bibdesk-rag-setup-test
brew install --build-from-source "$formula"
brew style "$formula"
brew audit --strict "$formula"
brew test "$formula"

# After adding revision 1 to the local test Formula only:
brew upgrade --build-from-source "$formula"
brew style "$formula"
brew audit --strict "$formula"
brew test "$formula"
```

| Check | Result |
| --- | --- |
| Actual source installation | Passed; new `0.1.1` test keg |
| `brew style` | Passed before and after upgrade; zero offenses |
| `brew audit --strict` | Passed before and after upgrade |
| `brew test` | Passed before and after upgrade, including installed setup help/non-TTY checks and CLI/MCP smoke |
| Actual `brew upgrade --build-from-source` | Passed; `0.1.1` → `0.1.1_1` |
| Fixed dependencies and installed application modules | All 29 versions and all 20 modules matched before and after upgrade |
| Existing public installation | Command/opt links and checked public Formula bytes unchanged |

### Interactive setup and data preservation

A standard-library PTY harness ran the installed command at the stable path
`/opt/homebrew/opt/bibdesk-rag-setup-test/bin/bibdesk-rag`, with both stdin and
stderr attached to a terminal. Its PATH contained only that Formula's `bin`,
`/usr/bin`, and `/bin`; Codex CLI and pyenv were unavailable. The harness supplied
an explicit `--config` under
`.local/setup-homebrew-validation/setup-fixture/data/`. The synthetic `.bib`,
two-page PDF, and CSV used Japanese filenames and directories containing spaces.
All source files, configuration, and index were outside Homebrew's Cellar and
installation prefix.

The first setup selected the library, confirmed configuration creation, and
confirmed the initial index. It completed with 1 paper, 2 attachments, 3 text
chunks, 2 successful extractions, and no extraction failures. It displayed the
manual Codex registration information and successfully verified the installed
local MCP server using `initialize` and `tools/list`. Separate CLI checks passed
`doctor` and retrieved synthetic evidence with PDF page 2 and CSV row 2
provenance. The three source-file SHA-256 hashes were unchanged.

After Homebrew upgrade, the same stable CLI and MCP paths resolved to the
`0.1.1_1` keg. Before starting any post-upgrade application command, the harness
verified that all five SHA-256 hashes—the `.bib`, PDF, CSV, configuration, and
SQLite index—still matched the pre-upgrade baseline. It then reran `setup`,
accepting the defaults to continue using the existing configuration and retain
the existing index. The five hashes remained identical after setup, status,
doctor, and search checks. Counts and extraction results remained 1/2/3 and two
successful extractions, and the new keg's local MCP handshake succeeded.

Machine-readable reports and terminal transcripts are retained locally:

- `setup-create.json`, `setup-create.transcript.txt`, and `setup-baseline.json`
  under `.local/setup-homebrew-validation/` record first setup and source hashes.
- `setup-reuse.json` and `setup-reuse.transcript.txt` record the changed executable
  target and unchanged data before and after default setup reuse.
- `logs/installed-install.json` and `logs/installed-upgrade.json` record the
  interpreter, module comparison, pinned dependencies, and public-install checks.
- `logs/brew-*-install.log`, `logs/brew-*-upgrade.log`, `logs/brew-install.log`,
  and `logs/brew-upgrade.log` contain the Homebrew results.

Both local test kegs are retained for inspection; the test Formula's `opt` link
points to `0.1.1_1`. The ordinary `bibdesk-rag` command remains the previously
installed public 0.1.1 command. The checked-in unreleased template and public tap
Formula were not changed by this validation.

### Scope and limits

This run verifies actual Homebrew source installation, the Formula's fixed
resource set, a revision upgrade, installed interactive setup, and preservation
of synthetic source/configuration/index data. The local Formula is keg-only,
so conflict handling when linking executables into Homebrew's shared `bin`
was not exercised. The upgrade kept the same application source and dependencies;
it does not establish behavior for a future schema or dependency migration.

No real BibDesk library was opened, and no user Codex registration was changed.
A local MCP handshake is distinct from registration or an actual search from
Codex; those Codex-side operations were not tested. Intel hardware, hosted CI,
`brew audit --online`, and public installation from release URLs were not tested.
No new release or public tap update was published.

## Initial release validation — 2026-11-01

This is the pre-publication local-tap validation record. Statements about an
unpublished release below describe that initial run. The public release is
tracked at [v0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0),
and the distribution Formula is maintained in
[KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap).

Validation machine: macOS 26.7.2, Apple Silicon arm64, Homebrew
7.0.11-75-gfcdfa04, Homebrew Python 3.14.10. No global pip or pyenv settings
were changed. A local-only tap `local/bibdesk-rag-test` was created; nothing was
published to GitHub. Native build dependencies libxml2 2.15.4 and libxslt 1.1.45
were installed by Homebrew.

### Reproducible build inputs

- 29 runtime sdist resources: `packaging/homebrew/resources.json`, each source
  archive downloaded and SHA-256 verified against its PyPI release metadata.
- 23 build backend wheels: `packaging/homebrew/build-resources.json`, verified
  against PyPI and bundled reproducibly, including macOS arm64 and x86_64 inputs.
- Backend bundle SHA-256:
  `5a4126a9d5bedf696db851154cb8923952aab654e805e69687ca14bd4be6b292`.
  Two separate bundle runs produced identical bytes.
- All PEP 517 build steps use `PIP_NO_INDEX=1` and the verified local backend
  bundle. Runtime dependencies and the application are built from explicit sdists.
- Socksio's old flit 2 backend cannot run on Python 3.14 (`ast.Str` was removed).
  Formula staging updates only its build metadata to pinned flit 3.12.0;
  the socksio runtime source remains unchanged.

### Executed checks

| Check | Result |
| --- | --- |
| `brew style local/bibdesk-rag-test/bibdesk-rag` | Passed, zero offenses |
| `brew audit --strict local/bibdesk-rag-test/bibdesk-rag` | Passed |
| `brew install --build-from-source local/bibdesk-rag-test/bibdesk-rag` | Passed |
| `brew test local/bibdesk-rag-test/bibdesk-rag` | Passed: synthetic library/CSV, CLI, read-only MCP |
| `bibdesk-rag --version`, `--help` | Passed within package smoke |
| CLI/MCP with `PATH=/usr/bin:/bin` | Passed; pyenv is unavailable on this PATH |
| Actual `brew upgrade --build-from-source` from 0.1.0 to 0.1.0_1 | Passed |
| Final corrected source upgrade from 0.1.0_1 to 0.1.0_2 | Passed; style/audit/test repeated successfully |
| Source, config, and index preservation across upgrade | All four SHA-256 digests identical before any post-upgrade command |
| All 17 installed Python modules compared with final workspace source | Byte-for-byte identical |

The smoke test exercises init, index, fulltext JSON search, BibTeX output, doctor,
update, source hash immutability, MCP initialize/tools-list/search, and reads the
existing index before update when checking preservation. `BIBDESK_RAG_CONFIG`
is removed from the child environment to ensure synthetic isolation. Existing
fixture/index directories are never overwritten unless explicitly reopening them
with `--verify-existing`.

The virtual environment lives in Homebrew's Cellar, has
`include-system-site-packages = false`, and the CLI shebang points to its
Homebrew-managed Python. User data remained outside the Cellar under the local
synthetic test directory. Both the original .bib and CSV were unchanged.

Final installed version: `bibdesk-rag 0.1.0`, local Formula revision 2 at
`/opt/homebrew/Cellar/bibdesk-rag/0.1.0_2`. The final tested source archive is
preserved under `.local/releases/homebrew-validation-rev2/` with SHA-256
`45dbbd41b9016d885ac38eff2abfac5ad97ec89006b4ba49e1a7fb2a75d5731c`.
Later distribution rebuilds that add this validation report may have a different
archive hash; the installed application modules were compared with the final
source independently. The ordinary committed Formula has no test revision.

### Scope and remaining release work

The generated local Formula uses stable local archive paths and an explicitly
non-public `example.invalid` homepage. These values must not be published. The
committed Formula remains an unreleased template; generate a release Formula
from the actual owner/repository, fixed release URLs, and verified SHA-256 values.
`brew audit --online` requires those real published URLs and has not been claimed.

Intel-compatible backend inputs are provided, but Intel hardware and the hosted
GitHub Actions matrix were not executed here. No GitHub Release or public tap
has been created. The local tap and installed application are left available for
inspection; synthetic fixtures/immutable test release snapshots are under `.local/`
and are excluded from Git.

---

<a id="japanese"></a>

# Homebrew検証

## 対話型セットアップ：インストールとアップグレード — 2026-11-02

未公開の `setup` 実装を実際のローカルHomebrew Formulaでビルド・導入し、Formula版 `0.1.1` から `0.1.1_1` へ更新しました。アプリ版は `0.1.1` のままで、revision 1はローカル検証用だけです。push、GitHub Release、公開Formula更新は行っていません。

検証実機：macOS 26.7.2、Apple Silicon arm64、Homebrew 7.0.11-102-gbb45d71、Homebrew Python 3.14.10。

### ローカルFormulaとビルド入力

生成Formulaは `local/bibdesk-rag-setup-test/bibdesk-rag-setup-test` です。本リポジトリのテンプレートと同じinstall/test処理・固定resourceを使い、異なるのはローカルのクラス・名前、独自の `keg_only` 理由、更新時の `revision 1` だけです。別kegにより、リンク済みの公開 `bibdesk-rag` 0.1.1を置き換えません。

- ソースsdist SHA-256：`e931683866a108eb8ef8682b76e47f419987e8c0c01c00eb6bab672409bc9141`。
- バックエンドbundle SHA-256：`5a4126a9d5bedf696db851154cb8923952aab654e805e69687ca14bd4be6b292`。
- 全29実行時依存が `packaging/homebrew/resources.json` と一致（`anyio` 4.15.1を含む）。新規pip解決ではなく、Formulaの固定依存を検証しました。
- 更新前後とも、全20アプリPythonモジュールが `src/bibdesk_rag/` とバイト単位で一致しました。
- 各kegの隔離Homebrew Python環境は `include-system-site-packages = false`。既存の `PIP_NO_INDEX=1` オフラインバックエンドビルドを保持しました。

ソース・バックエンドURLはローカル `file://`、homepageは明示的な非公開テスト値 `example.invalid` です。生成Formulaを公開してはいけません。アーカイブ、チェックサム、両revisionのFormulaはGit管理外の `.local/setup-homebrew-validation/` に保持しています。この記録の追加で後続sdistハッシュは変わり得るため、インストール済みモジュールと作業ツリーは別途比較しました。

### 実行したHomebrew操作

ログ付きrunnerから以下を実行しました。環境は `HOMEBREW_NO_AUTO_UPDATE=1`、`HOMEBREW_NO_INSTALL_CLEANUP=1`、`HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1`、`HOMEBREW_NO_ASK=1`、`HOMEBREW_NO_ANALYTICS=1`。Homebrew trust設定は作業専用 `XDG_CONFIG_HOME` を使い、global pip/pyenv設定は変更していません。

```sh
formula=local/bibdesk-rag-setup-test/bibdesk-rag-setup-test
brew install --build-from-source "$formula"
brew style "$formula"
brew audit --strict "$formula"
brew test "$formula"

# ローカル検証Formulaだけにrevision 1を追加した後：
brew upgrade --build-from-source "$formula"
brew style "$formula"
brew audit --strict "$formula"
brew test "$formula"
```

| 検査 | 結果 |
| --- | --- |
| 実際のソースインストール | 成功。新規 `0.1.1` 検証keg |
| `brew style` | 更新前後で成功、違反0件 |
| `brew audit --strict` | 更新前後で成功 |
| `brew test` | 更新前後で成功。導入済みsetupヘルプ・非TTY・CLI/MCP smokeを含む |
| 実際の `brew upgrade --build-from-source` | 成功。`0.1.1` → `0.1.1_1` |
| 固定依存とアプリモジュール | 更新前後で全29版・全20モジュールが一致 |
| 既存の公開インストール | command/optリンクと確認した公開Formulaのバイト列が不変 |

### 対話型セットアップとデータ保持

標準ライブラリのPTYハーネスで、安定パス `/opt/homebrew/opt/bibdesk-rag-setup-test/bin/bibdesk-rag` をstdin・stderrとも端末につないで実行しました。PATHは検証Formulaの `bin`、`/usr/bin`、`/bin` だけで、Codex CLI・pyenvは利用不可でした。明示的な `--config` を `.local/setup-homebrew-validation/setup-fixture/data/` 配下へ指定しました。合成 `.bib`、2ページPDF、CSVは日本語名と空白入りディレクトリを使い、原本・設定・索引はすべてHomebrew Cellar/prefixの外です。

初回setupでライブラリを選び、設定作成と初回索引を確認しました。1文献、2添付、3チャンク、抽出成功2件・失敗0件で完了し、手動Codex登録情報を表示しました。インストール済みローカルMCPの `initialize`・`tools/list` も成功しました。別のCLI検査では `doctor` と、PDFの2ページ目・CSVの2行目を示す合成証拠の取得が成功しました。3原本のSHA-256は不変でした。

Homebrew更新後、同じ安定CLI/MCPパスは `0.1.1_1` kegを指しました。更新後のアプリコマンドを実行する前に、`.bib`、PDF、CSV、設定、SQLiteの全5ハッシュが更新前と一致することを確認しました。その後、既定の選択で既存設定・索引を再利用してsetupを再実行し、setup・status・doctor・検索後も全5ハッシュが不変でした。件数1/2/3・抽出成功2件を保持し、新kegのMCP初期化も成功しました。

機械可読レポートと端末記録はローカルに保持しています。

- `.local/setup-homebrew-validation/` の `setup-create.json`、`setup-create.transcript.txt`、`setup-baseline.json`：初回setupと原本ハッシュ。
- `setup-reuse.json`、`setup-reuse.transcript.txt`：実行先の変更と、既定の再利用前後のデータ不変。
- `logs/installed-install.json`、`logs/installed-upgrade.json`：Python、モジュール比較、固定依存、公開インストール検査。
- `logs/brew-*-install.log`、`logs/brew-*-upgrade.log`、`logs/brew-install.log`、`logs/brew-upgrade.log`：Homebrew結果。

両検証kegを確認用に保持し、検証Formulaの `opt` は `0.1.1_1` を指します。通常の `bibdesk-rag` は以前の公開0.1.1のままです。この検証でリポジトリ内の未公開テンプレートや公開tap Formulaを変更していません。

### 範囲と制約

実際のHomebrewソース導入、固定resource、revision更新、導入済み対話型setup、合成原本・設定・索引の保持を検証しました。検証Formulaはkeg-onlyなので、共用 `bin` へリンクする際の競合処理は未検証です。更新は同じアプリソース・依存を使ったため、将来のスキーマ・依存移行の挙動は証明しません。

実BibDeskライブラリは開かず、利用者のCodex登録も変更していません。ローカルMCP初期化は登録やCodex実検索と別であり、Codex側操作は未検証です。Intel実機、ホストCI、`brew audit --online`、公開Release URLからの導入は未検証で、新規Release/tap公開もありません。

## 初回リリース検証 — 2026-11-01

これは公開前のローカルtap検証記録です。以下の未公開という記述は当時の状態です。公開リリースは [v0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0)、配布Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap) で管理しています。

実機：macOS 26.7.2、Apple Silicon arm64、Homebrew 7.0.11-75-gfcdfa04、Homebrew Python 3.14.10。global pip/pyenv設定は変更せず、ローカル専用tap `local/bibdesk-rag-test` を作成しました。GitHub公開は行わず、ネイティブ依存libxml2 2.15.4・libxslt 1.1.45はHomebrewで導入しました。

### 再現可能なビルド入力

- 実行時sdist 29件：`packaging/homebrew/resources.json`。全アーカイブを取得しPyPIメタデータのSHA-256と照合。
- ビルドバックエンドwheel 23件：`packaging/homebrew/build-resources.json`。PyPIと照合して再現可能にbundle化し、macOS arm64/x86_64を含む。
- bundle SHA-256：`5a4126a9d5bedf696db851154cb8923952aab654e805e69687ca14bd4be6b292`。独立した2回の生成で同一バイト列。
- 全PEP 517ビルドで `PIP_NO_INDEX=1` と検証済みローカルbundleを使用。実行時依存・アプリは明示sdistからビルド。
- socksioの旧flit 2はPython 3.14で削除された `ast.Str` により動作しません。Formulaはビルドメタデータだけを固定flit 3.12.0へ変え、実行時原文は保持します。

### 実行した検査

| 検査 | 結果 |
| --- | --- |
| `brew style local/bibdesk-rag-test/bibdesk-rag` | 成功、違反0件 |
| `brew audit --strict local/bibdesk-rag-test/bibdesk-rag` | 成功 |
| `brew install --build-from-source local/bibdesk-rag-test/bibdesk-rag` | 成功 |
| `brew test local/bibdesk-rag-test/bibdesk-rag` | 合成ライブラリ・CSV、CLI、読み取り専用MCPで成功 |
| `bibdesk-rag --version`、`--help` | package smoke内で成功 |
| `PATH=/usr/bin:/bin` でのCLI/MCP | pyenvなしで成功 |
| 実際の `brew upgrade --build-from-source`（0.1.0 → 0.1.0_1） | 成功 |
| 修正後ソースの最終更新（0.1.0_1 → 0.1.0_2） | 成功、style/audit/test再実行も成功 |
| 更新を跨ぐ原本・設定・索引保持 | 更新後コマンド実行前に全4ハッシュが一致 |
| 導入済み全17 Pythonモジュールと最終ソース | バイト単位で一致 |

smokeはinit、index、fulltext JSON検索、BibTeX出力、doctor、update、原本ハッシュ不変、MCP初期化・一覧・検索を実行し、保持確認時には更新前に既存索引を読みます。合成データを隔離するため子環境から `BIBDESK_RAG_CONFIG` を除外します。既存fixture・索引ディレクトリは `--verify-existing` で明示的に再利用しない限り上書きしません。

virtualenvはHomebrew Cellar内で `include-system-site-packages = false`、CLI shebangはHomebrew Pythonを指します。利用者データはCellar外のローカル合成検証ディレクトリにあり、元 `.bib` とCSVは不変でした。

最終導入版は `bibdesk-rag 0.1.0`、ローカルFormula revision 2、場所は `/opt/homebrew/Cellar/bibdesk-rag/0.1.0_2` です。最終検証アーカイブは `.local/releases/homebrew-validation-rev2/` に保持し、SHA-256は `45dbbd41b9016d885ac38eff2abfac5ad97ec89006b4ba49e1a7fb2a75d5731c`。この記録を追加した後の再ビルドではハッシュが変わり得ますが、導入済みモジュールは最終ソースと独立に比較しました。通常のコミット済みFormulaに検証revisionはありません。

### 範囲と残る公開作業

生成したローカルFormulaは固定ローカルアーカイブと非公開homepage `example.invalid` を使います。公開してはいけません。コミット済みFormulaは未公開テンプレートであり、実際の所有者・リポジトリ、固定Release URL、検証済みSHA-256から公開版を生成してください。`brew audit --online` は実公開URLが必要で、実施済みとはしていません。

Intel用入力はありますが、Intel実機とホストGitHub Actions matrixは実行していません。この時点でGitHub Release・公開tapは未作成です。ローカルtapと導入済みアプリは確認用に残し、合成fixture・不変の検証リリースはGit管理外 `.local/` に保持しています。
