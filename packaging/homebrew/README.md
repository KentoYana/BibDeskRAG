[日本語](#japanese) | [English](#english)

<a id="japanese"></a>

# Homebrew 配布

このリポジトリの `Formula/bibdesk-rag.rb` は生成用の未公開テンプレートです。
`@@...@@` を含む状態ではインストール対象ではありません。実在する公開
リポジトリ、Release URL、SHA-256 が確定するまでは公開用として扱わないでください。
`tools/generate_formula.py` が実ファイルのハッシュを検証して使用可能な Formula を生成します。

利用者向けの導入・Codex 接続は [README](../../README.md) を参照してください。
この文書は配布担当者向けです。本体は [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG)、
インストール用Formulaは [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap)、
初回リリースは [v0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0) です。
v0.3.0以降では、インストール後に `bibdesk-rag --setup` を実行すると、
ライブラリ登録・索引作成・任意のCodex接続を案内します。Homebrewへの
インストールだけでCodexの設定を変更することはなく、`--setup` でも利用者が
承認した場合だけMCPを登録します。Codex CLIがなくても手動接続情報を表示します。

## 公開前にそろえるもの

- 本体の公開リポジトリ、配布用 tap、リリース版番号。
- その版の sdist、wheel、固定ビルド依存 bundle と `SHA256SUMS`。
- クリーンな環境での通常インストールと、登録したローカル tap からの Homebrew 検証結果。
- README に記載した tap `KentoYana/tap` を実際の公開先と照合した利用手順。

このリポジトリには生成用テンプレートを保持します。架空の URL や `file://` を
公開 Formula に入れず、GitHub への push・タグ・Release・tap 公開は個別に許可を得てください。

## 配布環境

Formula は Homebrew の `python@3.14` と `Language::Python::Virtualenv` を使用し、
`libexec` 内に独立した環境を作ります。`system_site_packages: false` により
ユーザーのグローバル pip パッケージを参照せず、pyenv も必要としません。
実行時に pip、外部API、モデルダウンロードを呼びません。

Apple Silicon版では、NumPy/SentenceTransformers/PyTorchと追加の推論依存を
既存のFormula環境へ導入します。`build-resources.json` の `semantic_runtime` 行を
同じ `bibdesk-rag-build-wheels.tar.gz` に同梱し、`PIP_NO_INDEX=1` でインストールします。
別venvや実行時pipは使いません。モデル本体は含まず、`--setup` の選択時だけ取得します。
推論wheelはPython 3.14・macOS 14以上のarm64用です。Intelは基本検索の構成ですが、
新しい暗号依存を含むソースビルドは未検証です。
`tools/lock_semantic_resources.py` はテスト済み `.venv` から追加依存を辿り、
明示的にwheelを取得してPyPIのSHA-256と照合します。モデルは取得しません。
変更前後のライセンスとネイティブ依存を確認し、Formula導入・import・実推論を検証してください。

```sh
.venv/bin/python -m pip install -e '.[dev,semantic]'
.venv/bin/python tools/lock_semantic_resources.py
.venv/bin/python tools/bundle_build_resources.py --output dist/bibdesk-rag-build-wheels.tar.gz
```

基本の依存resourceやbackendを更新した場合は、semantic lockも再生成してください。
設定と統合SQLite・モデルキャッシュはFormulaの更新・再導入でも削除しません。
手順は [意味検索ガイド](../../docs/semantic-search.md) を参照してください。

35 の実行時 Python 依存の sdist は `resources.json` と Formula 内に URL・
バージョン・SHA-256 を固定しています。lxml は Homebrew の libxml2/libxslt を使って
ソースからビルドします。Python 本体やネイティブライブラリの patch 更新は
Homebrew の管理対象です。Python minor を変更するときは後述の backend bundle も更新します。

PDF用fontTools・cryptographyと、その間接依存CFFI・pycparserも基本依存です。
cryptographyはRust（ビルド時）とHomebrew OpenSSL、CFFIはlibffiを使って
ソースから構築します。Pythonの隔離ビルド用maturin・CFFI・pycparser wheelは
同じ固定bundleに含めます。Rust crateは上流Cargo.lockの版・SHAに従うビルド入力で、
アプリ実行時には取得しません。cryptography 49以降は上流のIntel macOS対応が
終了しているため、この最新依存でのIntelソースビルド動作は未検証です。

PEP 517 ビルドには異なる setuptools の版が必要です。公開 PyPI wheel を
`build-resources.json` で固定し、独立した `bibdesk-rag-build-wheels.tar.gz` にまとめます。
macOS arm64 / x86_64 用を含み、各ファイルと bundle 全体の SHA-256 を検証します。
Formula は `PIP_NO_INDEX=1` とローカル `PIP_FIND_LINKS` でビルドし、ビルド中に
未固定の依存を取得しません。標準ヘルパーの `--no-binary` のみを解除するのは
固定backendとarm64推論wheelを使用するためです。アプリ本体・基本の実行時依存は明示したsdistからビルドします。BibDeskParser の upstream backend 名は `uv_build` ですが、
uv パッケージマネージャーは使用せず、pip から backend を呼びます。
socksio の古い flit 2 は Python 3.14 で廃止された ast.Str を使用するため、
Formula は一時的なビルド要件のみ flit 3.12.0 に修正します。実行時コードは変更しません。

## 公開前のローカル検証

以下はローカル tap と Homebrew のインストール先に書き込みます。
GitHub への push、リポジトリ作成、公開は行いません。
先に README の開発環境を作成してください。古い配布物を混ぜないため、毎回
新しい出力ディレクトリを作成し、以降のコマンドは同じターミナルから実行します。

```sh
mkdir -p dist
release_dir="$(mktemp -d "$PWD/dist/preflight.XXXXXX")"
release_version="$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
.venv/bin/python -m build --outdir "$release_dir"
.venv/bin/python tools/bundle_build_resources.py --output "$release_dir/bibdesk-rag-build-wheels.tar.gz"
.venv/bin/python tools/check_release.py --dist-dir "$release_dir"
```

`check_release.py` はネットワークに接続せず、sdist と wheel の版番号・ライセンス類、
アーカイブ内の危険なパスや個人ライブラリ・索引・ローカル設定の混入、backend bundle と
固定 lock の一致を検査します。古い版など余分なファイルがあるディレクトリを拒否し、
検査に通った **3 成果物だけ** の `SHA256SUMS` を生成します。元の成果物は変更しません。
ソース本文に埋め込まれた秘密情報まで判定するものではないため、公開 diff の確認も必要です。

ローカル tap の作成は初回のみです。既にある場合は `brew tap-new` を省略します。

```sh
brew tap-new local/bibdesk-rag-test
.venv/bin/python tools/generate_formula.py \
  --version "$release_version" \
  --homepage https://example.invalid/bibdesk-rag-local-test \
  --local-sdist "$release_dir/bibdesk_rag-$release_version.tar.gz" \
  --local-build-wheels "$release_dir/bibdesk-rag-build-wheels.tar.gz" \
  --output "$(brew --repository local/bibdesk-rag-test)/Formula/bibdesk-rag.rb"
brew trust --formula local/bibdesk-rag-test/bibdesk-rag
brew style local/bibdesk-rag-test/bibdesk-rag
brew install --build-from-source local/bibdesk-rag-test/bibdesk-rag
brew audit --strict local/bibdesk-rag-test/bibdesk-rag
brew test local/bibdesk-rag-test/bibdesk-rag
bibdesk-rag --version
bibdesk-rag --help
.venv/bin/python tools/package_smoke.py --workdir /tmp/bibdesk-rag-brew-smoke
```

`example.invalid` はこの公開前テストだけの明示的な仮値です。生成済みのローカル
Formula の `file://` URL とともに公開しないでください。`brew audit --online`
による公開URLの検証は、公開URLができてから実施します。
`brew style/audit` の結果は Homebrew の版によって変わるため、公開直前にも再実行します。

`test do` はライブラリ・2 ページ PDF・補足 CSV を合成し、登録、索引、本文検索、
BibTeX 出力、診断、差分更新、元ファイルのハッシュ不変、stdio MCP 初期化と検索を検証します。
PDF の書誌検索から本文取得へ進み、citekey・DOI・元パス・ページ番号・chunk ID の
一致と MCP 利用中の設定・DB のハッシュ不変も確認します。
実ライブラリを使用しません。
上記の smoke 出力先は新しい空のパスを使います。古い CSV のみの検証ディレクトリは
今回の PDF 検証の代わりにしないでください。既にインストール済みの場合は
`brew install` の代わりに次の `reinstall` を使います。

再インストール後のデータ保持:

```sh
brew reinstall --build-from-source local/bibdesk-rag-test/bibdesk-rag
.venv/bin/python tools/package_smoke.py --verify-existing --workdir /tmp/bibdesk-rag-brew-smoke
```

実際の `brew upgrade` を公開前に試すには、生成した **ローカル Formula のみ** に
`revision 1` を追加し、`brew upgrade --build-from-source local/bibdesk-rag-test/bibdesk-rag`
を実行したあと、同じ `--verify-existing` 検証を実行します。ソース版番号の変更は不要です。
利用者の設定・SQLite は既定で `~/.config/bibdesk-rag/` と
`~/.local/share/bibdesk-rag/` にあり、Cellar 外に保持します。
`BIBDESK_RAG_HOME`・XDGの指定にも対応します。
アンインストールにもデータ削除フックはありません。

## リリース手順

外部公開は所有者の明示的な許可を得て実行してください。CIは自動公開せず、
許可された範囲の公開操作を配布担当者が行います。

1. `pyproject.toml` と `src/bibdesk_rag/__init__.py` の版番号を SemVer でそろえて更新し、
   変更履歴とテストを確認します。
2. `.venv/bin/python -m pytest`、`.venv/bin/ruff check src tests tools` を実行します。
3. 上記の新しい出力ディレクトリで 3 成果物を生成し、`check_release.py` を実行します。
   別々の空の venv に sdist/wheel を通常インストールし、それぞれ `pip check` と
   `tools/package_smoke.py` を実行します。backend bundle は同じ lock/notice から同じ SHA-256 になります。
4. 生成したローカル Formula で style/audit、ソースからのインストール、Formula test、
   再インストール・upgrade 時の合成ユーザーデータ保持を確認します。MIT と依存 notice、
   README の公開先・公開状況、実機と CI の検証範囲を確認し、レビュー用の成果物を確定します。
5. 許可後に `v0.3.0` のような Git タグと GitHub Release を作成し、sdist、wheel、
   backend bundle、`SHA256SUMS` を添付します。タグ名と版番号を一致させてください。
   この段階で再ビルドせず、検証済みの同じバイト列を公開します。
6. 実際の URL と SHA-256 を指定して Formula を生成します。例中の変数には確定した値を入れます。
   本体のhomepageは `https://github.com/KentoYana/BibDeskRAG`、Release添付ファイルのURLは
   `https://github.com/KentoYana/BibDeskRAG/releases/download/vVERSION/FILENAME` の形式です。
   バージョンとファイル名を置き換え、添付ファイルが実際に公開されていることを確認してから実行します。

```sh
.venv/bin/python tools/generate_formula.py \
  --version "$release_version" --homepage "$project_homepage" \
  --url "$sdist_url" --sha256 "$sdist_sha256" \
  --build-wheels-url "$backend_bundle_url" --build-wheels-sha256 "$backend_bundle_sha256" \
  --output /path/to/homebrew-tap/Formula/bibdesk-rag.rb
```

生成ツールは sdist の公開 URL から実ファイルを取得して SHA-256 を確認し、
`PKG-INFO` と `pyproject.toml` の名前・版番号、ライセンス同梱も確認します。
誤った版の sdist からは Formula を生成しません。

7. `brew style`、`brew audit --strict`、`brew audit --online`、
   `brew install --build-from-source`、`brew test` を実行します。
8. 許可後に `KentoYana/homebrew-tap` リポジトリへ反映します。
9. 利用者の `brew upgrade KentoYana/tap/bibdesk-rag` と
   更新前の索引・設定が残ることを検証します。

一般ユーザーのインストールコマンド:

```sh
brew install KentoYana/tap/bibdesk-rag
```

## 依存の更新

開発用 venv で対象の版をインストール・テストしたあと、以下を実行します。

```sh
python tools/lock_homebrew_resources.py
brew update-python-resources KentoYana/tap/bibdesk-rag --print-only
```

最初のコマンドは pyproject の依存から再帰的にたどり、実際にインストールされた版の
PyPI sdist をダウンロードし SHA-256 を検証、JSON とテンプレートを更新します。
`--print-only` は公開済み Formula の確認用で、backend bundle resource は手動維持します。

backend の更新は別作業です。`.build-wheels/` を新しい空ディレクトリとして用意し、
対象 sdist の `pyproject.toml` / `setup.py` のビルド要件を調べて pip で wheel を取得します。
Python 3.14 の arm64 と x86_64 の両方が必要です。現行セットは以下で再取得できます
（互換タグの解決が変わる場合は `build-resources.json` の固定URLを使用してください）。

```sh
python tools/bundle_build_resources.py --output dist/bibdesk-rag-build-wheels.tar.gz
```

新しい wheel セットを選定した場合は `python tools/lock_build_resources.py .build-wheels`
で PyPI SHA-256 を検証して lock を更新し、ライセンス表・同梱 notice を更新します。
Formula の完全なオフライン build と `brew test` を再実行してください。

## CI

`test.yml` は Python 3.11–3.14 の Linux/macOS テストを実行します。
`package.yml` は配布アーカイブ検査・SHA256SUMS 生成、macOS で wheel/sdist の通常インストールとローカル Homebrew Formula
の style/audit/source install/機能テスト/データ保持を実行し、配布物を artifact として保存します。
GitHub Release や tap を自動公開する権限は持たせていません。
Intel の backend wheel は用意していますが、Intel 実機での検証結果は別途記録してください。

公式参照: [Python Formula](https://docs.brew.sh/Language-Specific-Formulae#python)、
[Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)。

---

<a id="english"></a>

# Homebrew distribution

`Formula/bibdesk-rag.rb` in this repository is an unpublished generation template. It is not installable while it contains `@@...@@`. Do not treat it as a release Formula until the actual public repository, release URLs and SHA-256 values are established. `tools/generate_formula.py` verifies archive hashes and generates a usable Formula.

For user installation/Codex connection, see the [README](../../README.md#english). This document is for maintainers. Application: [KentoYana/BibDeskRAG](https://github.com/KentoYana/BibDeskRAG); installable Formula: [KentoYana/homebrew-tap](https://github.com/KentoYana/homebrew-tap); initial release: [v0.1.0](https://github.com/KentoYana/BibDeskRAG/releases/tag/v0.1.0). From v0.3.0, `bibdesk-rag --setup` guides library registration, indexing and optional Codex connection. Installation alone never changes Codex settings; setup registers MCP only after approval. Without Codex CLI, it displays manual connection details.

## Prerequisites for publication

- Public application repository, distribution tap and release version.
- That version's sdist, wheel, fixed build-dependency bundle and `SHA256SUMS`.
- Normal installation results from clean environments and Homebrew validation through a registered local tap.
- User instructions checked against the actual publication target, including the README's `KentoYana/tap` name.

Keep the generation template in this repository. Never publish fictitious or `file://` URLs in a release Formula. Obtain explicit authorization for GitHub pushes, tags, releases and tap publication.

## Distribution environment

The Formula uses Homebrew `python@3.14` and `Language::Python::Virtualenv`, creating a separate environment in `libexec`. `system_site_packages: false` isolates it from global pip packages; pyenv is unnecessary. It invokes no pip, external API or model downloads at runtime.

The 35 runtime dependency sdists have fixed URLs, versions and SHA-256 values in `resources.json` and the Formula. lxml builds from source against Homebrew libxml2/libxslt. Python/native-library patch updates are managed by Homebrew. Changing Python minor versions also requires updating the backend bundle below.

PDF decoding includes fontTools/cryptography and indirect CFFI/pycparser.
Cryptography builds from source with Rust (build-only) and Homebrew OpenSSL;
CFFI uses libffi. Pinned maturin/CFFI/pycparser wheels satisfy isolated Python
build requirements. Rust crates follow upstream Cargo.lock versions/checksums
at build time; application runtime performs no downloads. Upstream cryptography
49+ no longer supports Intel macOS; this dependency's Intel source build remains
unverified. See [upstream release notes](https://cryptography.io/en/50.0.2/changelog/).

PEP 517 builds need different setuptools versions. Public PyPI wheels are locked in `build-resources.json` and packaged separately as `bibdesk-rag-build-wheels.tar.gz`, including macOS arm64/x86_64 inputs. Each file and the whole bundle are SHA-256 checked. The Formula builds with `PIP_NO_INDEX=1` and local `PIP_FIND_LINKS`, avoiding unpinned dependency downloads during builds. Only the standard helper's `--no-binary` restriction is lifted to allow backend wheels; application/runtime dependencies still build from explicit sdists. BibDeskParser's backend is named `uv_build`; pip invokes it without the uv package manager. Since socksio's old flit 2 uses `ast.Str`, removed in Python 3.14, the Formula temporarily changes only its build requirement to flit 3.12.0. Runtime code is unchanged.

## Local pre-publication validation

These steps write to a local tap and the Homebrew installation. They do not push, create repositories or publish to GitHub. First prepare the README's development environment. Use a fresh output directory for every run to avoid mixing old artifacts, and run subsequent commands in the same terminal.

```sh
mkdir -p dist
release_dir="$(mktemp -d "$PWD/dist/preflight.XXXXXX")"
release_version="$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
.venv/bin/python -m build --outdir "$release_dir"
.venv/bin/python tools/bundle_build_resources.py --output "$release_dir/bibdesk-rag-build-wheels.tar.gz"
.venv/bin/python tools/check_release.py --dist-dir "$release_dir"
```

`check_release.py` works offline. It checks sdist/wheel versions and license files, unsafe archive paths, accidental personal libraries/indexes/local configuration, and backend-bundle agreement with the fixed lock. It rejects extra files such as older versions and generates `SHA256SUMS` for **only the three validated artifacts**, without modifying them. It cannot detect every secret embedded in source text; also review the publication diff.

Create the local tap once; skip `brew tap-new` if it exists.

```sh
brew tap-new local/bibdesk-rag-test
.venv/bin/python tools/generate_formula.py \
  --version "$release_version" \
  --homepage https://example.invalid/bibdesk-rag-local-test \
  --local-sdist "$release_dir/bibdesk_rag-$release_version.tar.gz" \
  --local-build-wheels "$release_dir/bibdesk-rag-build-wheels.tar.gz" \
  --output "$(brew --repository local/bibdesk-rag-test)/Formula/bibdesk-rag.rb"
brew trust --formula local/bibdesk-rag-test/bibdesk-rag
brew style local/bibdesk-rag-test/bibdesk-rag
brew install --build-from-source local/bibdesk-rag-test/bibdesk-rag
brew audit --strict local/bibdesk-rag-test/bibdesk-rag
brew test local/bibdesk-rag-test/bibdesk-rag
bibdesk-rag --version
bibdesk-rag --help
.venv/bin/python tools/package_smoke.py --workdir /tmp/bibdesk-rag-brew-smoke
```

`example.invalid` is an explicit placeholder for this pre-publication test only. Never publish it or the generated local Formula's `file://` URLs. Run `brew audit --online` after actual public URLs exist. Style/audit results depend on Homebrew version; rerun shortly before publication.

The Formula's `test do` generates a library, two-page PDF and supplementary CSV. It checks registration, indexing, full-text search, BibTeX output, diagnostics, incremental updates, unchanged source hashes, stdio MCP initialization and search. Starting with PDF metadata search, it verifies selected-paper evidence, citekey, DOI, original path, page, chunk ID and unchanged configuration/database hashes during MCP use. It uses no real library. Use a new empty smoke-test destination; an old CSV-only fixture is not a substitute for this PDF check. If already installed, use reinstall below instead of install.

Check data preservation after reinstall:

```sh
brew reinstall --build-from-source local/bibdesk-rag-test/bibdesk-rag
.venv/bin/python tools/package_smoke.py --verify-existing --workdir /tmp/bibdesk-rag-brew-smoke
```

To test a real `brew upgrade` before release, add `revision 1` **only to the generated local Formula**, run `brew upgrade --build-from-source local/bibdesk-rag-test/bibdesk-rag`, then repeat `--verify-existing`. No source-version change is needed. User configuration/SQLite default to `~/.config/bibdesk-rag/` and `~/.local/share/bibdesk-rag/`, outside the Cellar. `BIBDESK_RAG_HOME` and XDG overrides are supported. Uninstall has no data-deletion hook.

## Release procedure

External publication requires the owner's explicit authorization. CI never publishes automatically; maintainers perform only authorized publication steps.

1. Update matching SemVer versions in `pyproject.toml` and `src/bibdesk_rag/__init__.py`; review changelog/tests.
2. Run `.venv/bin/python -m pytest` and `.venv/bin/ruff check src tests tools`.
3. Generate the three artifacts in a fresh directory and run `check_release.py`. Normally install sdist/wheel in separate empty venvs; run `pip check` and `tools/package_smoke.py` in each. The same backend lock/notices produce the same bundle SHA-256.
4. Use the generated local Formula for style/audit, source installation, Formula tests and synthetic-data retention across reinstall/upgrade. Check MIT/dependency notices, README targets/publication status and machine/CI validation boundaries. Finalize reviewable artifacts.
5. After authorization, create a matching Git tag/GitHub Release such as `v0.3.0`; attach sdist, wheel, backend bundle and `SHA256SUMS`. Publish the tested bytes without rebuilding at this stage.
6. Generate the Formula using actual URLs/hashes. Set the example variables to confirmed values. The homepage is `https://github.com/KentoYana/BibDeskRAG`; release asset URLs follow `https://github.com/KentoYana/BibDeskRAG/releases/download/vVERSION/FILENAME`. Replace version/filename and confirm assets really exist before running:

```sh
.venv/bin/python tools/generate_formula.py \
  --version "$release_version" --homepage "$project_homepage" \
  --url "$sdist_url" --sha256 "$sdist_sha256" \
  --build-wheels-url "$backend_bundle_url" --build-wheels-sha256 "$backend_bundle_sha256" \
  --output /path/to/homebrew-tap/Formula/bibdesk-rag.rb
```

The generator downloads the actual sdist from its public URL and verifies SHA-256, name/version in `PKG-INFO` and `pyproject.toml`, and included licenses. It refuses an sdist for the wrong version.

7. Run `brew style`, `brew audit --strict`, `brew audit --online`, `brew install --build-from-source` and `brew test`.
8. After authorization, publish to `KentoYana/homebrew-tap`.
9. Verify user `brew upgrade KentoYana/tap/bibdesk-rag` and preservation of pre-upgrade configuration/index.

User installation command:

```sh
brew install KentoYana/tap/bibdesk-rag
```

## Updating dependencies

Install/test the target versions in the development venv, then run:

```sh
python tools/lock_homebrew_resources.py
brew update-python-resources KentoYana/tap/bibdesk-rag --print-only
```

After backend changes, run `tools/lock_semantic_resources.py` to restore the semantic wheel lock.
The first command recursively resolves base pyproject dependencies, downloads the installed versions' PyPI sdists, verifies SHA-256 and updates JSON/template. `--print-only` inspects the published Formula; maintain its backend-bundle resource manually.

Backend updates are separate. Prepare a new empty `.build-wheels/` directory, inspect build requirements in target sdists' `pyproject.toml` / `setup.py`, and obtain wheels with pip. Both Python 3.14 arm64 and x86_64 are required. Retrieve the current set with the following; if compatibility-tag resolution changes, use the fixed URLs in `build-resources.json`.

```sh
python tools/bundle_build_resources.py --output dist/bibdesk-rag-build-wheels.tar.gz
```

For a newly selected wheel set, run `python tools/lock_build_resources.py .build-wheels` to verify PyPI SHA-256 and update the lock, then update license tables/bundled notices. Repeat a fully offline Formula build and `brew test`.

## Continuous integration

`test.yml` runs Python 3.11–3.14 tests on Linux/macOS. `package.yml` checks archives, generates `SHA256SUMS`, and on macOS performs normal wheel/sdist installation plus local Homebrew style/audit/source install/functional tests/data-retention checks. It retains artifacts without permission to publish GitHub releases or the tap. Intel backend wheels are included; record actual Intel-machine validation separately.

Official references: [Python Formula](https://docs.brew.sh/Language-Specific-Formulae#python), [Formula Cookbook](https://docs.brew.sh/Formula-Cookbook).

## Semantic inference wheels (Apple Silicon)

The existing offline bundle now also contains 31 PyPI-verified runtime wheels, marked
`semantic_runtime` in `build-resources.json`. Some overlap build backends. The Formula
installs them into its one managed venv on arm64, without dependencies/network resolution,
then checks dependency consistency. Base runtime sdists remain locked separately. This
keeps pip extras optional while Homebrew Apple Silicon supports the setup choice without
a companion venv. The model cache is acquired only by an explicit setup/download action.
The binary runtime lock targets Python 3.14/macOS 14+ arm64; Intel has the base
retrieval configuration, with the new cryptography source build unverified.
Run the semantic lock tool after changing either backend or base/runtime dependency locks.
