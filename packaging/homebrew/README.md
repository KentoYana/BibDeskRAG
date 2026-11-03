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

29 の実行時 Python 依存の sdist は `resources.json` と Formula 内に URL・
バージョン・SHA-256 を固定しています。lxml は Homebrew の libxml2/libxslt を使って
ソースからビルドします。Python 本体やネイティブライブラリの patch 更新は
Homebrew の管理対象です。Python minor を変更するときは後述の backend bundle も更新します。

PEP 517 ビルドには異なる setuptools の版が必要です。公開 PyPI wheel を
`build-resources.json` で固定し、独立した `bibdesk-rag-build-wheels.tar.gz` にまとめます。
macOS arm64 / x86_64 用を含み、各ファイルと bundle 全体の SHA-256 を検証します。
Formula は `PIP_NO_INDEX=1` とローカル `PIP_FIND_LINKS` でビルドし、ビルド中に
未固定の依存を取得しません。標準ヘルパーの `--no-binary` のみを解除するのは
この backend wheel を使用するためです。アプリ本体・実行時依存は明示した sdist
からビルドします。BibDeskParser の upstream backend 名は `uv_build` ですが、
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
