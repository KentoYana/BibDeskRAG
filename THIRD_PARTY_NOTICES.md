[日本語](#japanese) | [English](#english)

<a id="english"></a>

# Third-party notices

## PDF dependencies added after 0.5.0

- `fonttools==4.68.0`: MIT; used by pypdf to decode embedded CFF Type1 fonts.
- `cryptography==50.0.2`: Apache-2.0 OR BSD-3-Clause; used by pypdf for AES PDF decryption.
- `cffi==2.1.1`: MIT-0, with upstream per-file notices retained.
- `pycparser==3.12`: BSD-3-Clause.

The four source archives were checked against PyPI SHA-256 metadata on
2026-11-14 and their complete top-level LICENSE files were inspected, including
cryptography's LICENSE.APACHE and LICENSE.BSD. Source URLs/hashes are in
`packaging/homebrew/resources.json`; upstream code and notices remain in their
separate pip/Homebrew distributions, not in the application's own wheel.

Homebrew builds cryptography from source with Rust and Homebrew OpenSSL
(Apache-2.0); CFFI uses libffi (MIT). The upstream Cargo.lock pins Rust crates
and checksums; preserve their individual licenses when redistributing the
resulting dependency. Pip's upstream cryptography wheels bundle their own
OpenSSL and retain its license. Do not describe the full crypto binary as
uniformly BSD-licensed.

Build isolation additionally uses verified CFFI/pycparser wheels and
`maturin==1.16.0` (MIT OR Apache-2.0), with macOS arm64/x86_64 inputs in
`build-resources.json`. Their original wheel LICENSE/NOTICE files are retained
intact in the offline bundle. They are build inputs, not a new package manager
or an application-time download.

## Document readers added in 0.5.0

- `olefile==0.47`: BSD-2-Clause plus the retained PIL-derived permission notice. No image decoding is used.
- `xlrd==2.0.2`: BSD-3-Clause plus its earlier advertising/acknowledgment license. **This product includes software developed by David Giffin <david@giffin.org>.**

Both upstream sdists were verified against PyPI SHA-256 metadata on 2026-11-14; their complete LICENSE files were inspected. Keep both packages’ complete notices on redistribution, including the xlrd acknowledgment in advertising materials mentioning its features/use. The application wheel does not vendor their code; pip/Homebrew retain upstream distributions and licenses. Source locks and the unreleased Formula template include both readers. Existing build backends suffice; no runtime download is added.

## Optional semantic extra

The optional `semantic` extra adds NumPy and SentenceTransformers; pip keeps it separate from the base dependency set. Homebrew Apple Silicon installs
a fixed runtime wheel set in its existing managed environment, with checksums in
`packaging/homebrew/build-resources.json` (`semantic_runtime` records). On macOS arm64, the implementation was exercised with
NumPy 2.5.4, SentenceTransformers 5.7.0, PyTorch 2.15.0, Transformers 5.22.1,
Hugging Face Hub 2.4.0, safetensors 0.8.0, SciPy 1.18.1 and scikit-learn 1.9.1.
Installed license metadata/files were inspected for these packages. SentenceTransformers,
Transformers, Hugging Face Hub and safetensors provide Apache-2.0 notices; scikit-learn
uses BSD-3-Clause. NumPy's installed license expression includes BSD-3-Clause, 0BSD,
MIT, Zlib and CC0-1.0. PyTorch's expression includes Apache-2.0 (also with LLVM exception),
BSD-2-Clause, BSD-3-Clause, BSL-1.0, ISC, MIT and Zlib. Preserve all installed LICENSE,
NOTICE and third-party files when redistributing these dependencies.

SciPy includes BSD notices and notices for bundled OpenBLAS/LAPACK and compiler
runtimes (including GCC runtime exceptions and LGPL libquadmath where present).
Do not describe a bundled scientific Python environment as uniformly MIT/BSD licensed.
Pip retains upstream distribution metadata and licenses; the BibDeskRAG wheel/sdist
contains no copies of model weights or these optional libraries. The offline Homebrew bundle retains each original wheel intact, including its upstream
license/notice files. Its 31 runtime wheel files were verified against PyPI SHA-256 metadata.
The fixed target is Python 3.14/macOS 14+ arm64. No Intel semantic-runtime coverage is claimed.
Any changed binary set must be audited and its full notices preserved before release.

The default model is `intfloat/multilingual-e5-small`, fixed to revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98`. Its model card declares MIT licensing.
The explicit model-download command retains model-card/license files alongside the
cache where supplied by upstream. Model weights are downloaded separately, never
bundled with BibDeskRAG or fetched automatically during retrieval.

The table below describes the original base runtime lock, separately from the
optional semantic environment.

BibDeskRAG application code is MIT-licensed. Dependencies retain their own licenses;
this project does not relicense them. The table below records the exact tested
runtime set. `packaging/homebrew/resources.json` contains immutable source URLs,
versions, SHA-256 checksums, and the public PyPI metadata URL for each package.
The lock was verified by downloading every source archive on 2026-11-01.
Installed distribution LICENSE/NOTICE files were also inspected where metadata
was absent or ambiguous (PySocks, socksio, tomli-w, lxml, tqdm).

| Package | Version | License |
| --- | --- | --- |
| [anyio](https://pypi.org/project/anyio/4.15.1/) | 4.15.1 | MIT |
| [arxiv](https://pypi.org/project/arxiv/4.0.2/) | 4.0.2 | MIT |
| [bibdeskparser](https://pypi.org/project/bibdeskparser/0.8.1/) | 0.8.1 | MIT |
| [bibtexparser](https://pypi.org/project/bibtexparser/2.0.0b9/) | 2.0.0b9 | MIT |
| [certifi](https://pypi.org/project/certifi/2026.10.23/) | 2026.10.23 | MPL-2.0 |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.5.2/) | 3.5.2 | MIT |
| [click](https://pypi.org/project/click/8.5.0/) | 8.5.0 | BSD-3-Clause |
| [defusedxml](https://pypi.org/project/defusedxml/0.7.1/) | 0.7.1 | PSF-2.0 |
| [et-xmlfile](https://pypi.org/project/et-xmlfile/2.0.0/) | 2.0.0 | MIT |
| [h11](https://pypi.org/project/h11/0.16.0/) | 0.16.0 | MIT |
| [habanero](https://pypi.org/project/habanero/2.9.2/) | 2.9.2 | MIT |
| [httpcore](https://pypi.org/project/httpcore/1.0.9/) | 1.0.9 | BSD-3-Clause |
| [httpcore2](https://pypi.org/project/httpcore2/2.16.0/) | 2.16.0 | BSD-3-Clause |
| [httpx](https://pypi.org/project/httpx/0.28.1/) | 0.28.1 | BSD-3-Clause |
| [httpx2](https://pypi.org/project/httpx2/2.16.0/) | 2.16.0 | BSD-3-Clause |
| [idna](https://pypi.org/project/idna/3.20/) | 3.20 | BSD-3-Clause |
| [lxml](https://pypi.org/project/lxml/6.1.3/) | 6.1.3 | BSD-3-Clause |
| [openpyxl](https://pypi.org/project/openpyxl/3.1.5/) | 3.1.5 | MIT |
| [packaging](https://pypi.org/project/packaging/26.3/) | 26.3 | Apache-2.0 OR BSD-2-Clause |
| [pylatexenc](https://pypi.org/project/pylatexenc/2.11/) | 2.11 | MIT |
| [pypdf](https://pypi.org/project/pypdf/6.21.4/) | 6.21.4 | BSD-3-Clause |
| [pysocks](https://pypi.org/project/pysocks/1.7.1/) | 1.7.1 | BSD-3-Clause |
| [requests](https://pypi.org/project/requests/2.34.2/) | 2.34.2 | Apache-2.0 |
| [socksio](https://pypi.org/project/socksio/1.0.0/) | 1.0.0 | MIT |
| [tomli-w](https://pypi.org/project/tomli-w/1.2.0/) | 1.2.0 | MIT |
| [tqdm](https://pypi.org/project/tqdm/4.70.1/) | 4.70.1 | MPL-2.0 AND MIT |
| [truststore](https://pypi.org/project/truststore/0.10.5/) | 0.10.5 | MIT |
| [typing-extensions](https://pypi.org/project/typing-extensions/4.16.0/) | 4.16.0 | PSF-2.0 |
| [urllib3](https://pypi.org/project/urllib3/2.8.0/) | 2.8.0 | MIT |

The MIT, BSD, Apache, and PSF licenses permit redistribution alongside MIT
application code, subject to retaining their notices. Certifi and parts of tqdm
are MPL-2.0: retain upstream license/source information and make any modifications
to covered files available under MPL. No upstream covered files are modified by
this project. Pip/Homebrew installations retain each distribution's metadata and
license files. Anyone distributing a bundled binary must retain those notices
and fulfill the dependencies' source/notice obligations; the MIT license applies
only to BibDeskRAG's own code.

## Native and bundled components

Lxml's `LICENSES.txt` additionally documents ElementTree and CPython-derived code,
ISO Schematron resources, and a GPL-licensed upstream test runner (separate
aggregation, not application code). It also identifies extraction XSL resources
without separate license declarations. Preserve lxml's complete upstream notices;
do not describe its entire source tree as exclusively BSD-licensed. Homebrew
builds lxml from source against Homebrew libxml2/libxslt (MIT). Binary lxml wheels
installed by pip may also bundle zlib (Zlib), iconv (LGPL-2.1), and libexslt (MIT);
the wheel retains its upstream notices. BibDeskRAG's own wheel contains no copies
of those libraries. Review these upstream exceptions if redistributing a merged
binary or modified dependency, rather than the normal source/wheel package.

The installed Homebrew libexslt additionally links to libgcrypt and libgpg-error;
their library licenses are LGPL-2.1 (verified in the installed `COPYING.LIB`
files). These remain separate, dynamically linked Homebrew dependencies with
their upstream notices/source obligations. They are not copied into the
BibDeskRAG wheel. `otool -L` confirmed the library links; Homebrew's broader
formula dependency tree also includes command-line tools whose licenses do not
describe the linked libraries themselves.

No PyMuPDF dependency is used. CPython/SQLite are provided by the interpreter;
CPython is PSF licensed and SQLite is public domain.

## Build-only inputs

`packaging/homebrew/build-resources.json` locks all wheels placed in the offline
Homebrew build bundle (including both macOS architectures where necessary).
The bundle is a separate release asset; these backend wheels are not installed
as application runtime dependencies. They are pip's isolated PEP 517 backends,
including the upstream `uv_build` backend used by BibDeskParser. The `uv` package
manager is neither installed nor invoked by this project. Development and
installation use pip exclusively.

| Build package | Version(s) | License |
| --- | --- | --- |
| cython | 3.2.9 | Apache-2.0 |
| dunamai | 1.26.3 | MIT |
| flit-core | 3.12.0 | BSD-3-Clause; vendored tomli MIT in 3.12 |
| hatch-fancy-pypi-readme | 25.1.0 | MIT |
| hatch-vcs | 0.5.0 | MIT |
| hatchling | 1.33.0 | MIT |
| jinja2 | 3.1.6 | BSD-3-Clause |
| markupsafe | 3.0.4 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pathspec | 1.1.1 | MPL-2.0 |
| pluggy | 1.7.0 | MIT |
| setuptools | 84.0.0, 84.2.1 | MIT |
| setuptools-scm | 10.3.4 | MIT |
| tomlkit | 0.15.2 | MIT |
| trove-classifiers | 2026.9.21.13 | Apache-2.0 |
| uv-build | 0.12.24 | MIT OR Apache-2.0 |
| uv-dynamic-versioning | 0.14.1 | MIT |
| vcs-versioning | 2.6.0 | MIT |
| wheel | 0.48.0 | MIT |

Backend wheels retain their original LICENSE/NOTICE files without modification.
Their verified hashes and source project identities are preserved in the bundled
manifest. Refresh these notices whenever the runtime/build locks change.

Build license conclusions above were verified from wheel LICENSE files.
The tagged flit source LICENSE was also inspected because old metadata classifiers
were inconsistent with the BSD-3-Clause license text. Pathspec is MPL-2.0 and is
redistributed unmodified with its license/source identity. Socksio's temporary
build requirement is updated from flit 2 to pinned flit 3.12.0 for Python 3.14;
its runtime source is unchanged. This is an MIT-licensed package.

## Development/test tools (not shipped in application wheels)

The installed development environment was checked separately: build 1.6.1,
pytest 9.2.0, ruff 0.17.3, iniconfig 2.3.1, pluggy 1.7.0, and
pyproject-hooks 1.3.3 are MIT; Pygments 2.21.0 is BSD-2-Clause;
ReportLab 4.5.1 is BSD licensed; Pillow 13.0.0 is MIT-CMU.
Their remaining Python requirements are listed in the runtime/build tables above.
These tools generate synthetic test fixtures or validate packages and are not
vendored into BibDeskRAG's source/wheel or its runtime environment.

---

<a id="japanese"></a>

# 第三者ライセンスと依存一覧

## 0.5.0以降に追加したPDF依存

fonttools 4.68.0（MIT）、cryptography 50.0.2（Apache-2.0 OR BSD-3-Clause）と、
間接依存cffi 2.1.1（MIT-0）・pycparser 3.12（BSD-3-Clause）を追加しました。
2026-11-14にソースのPyPI SHAと上流LICENSEを確認しています。Homebrewの
Rust/OpenSSL/libffi、隔離ビルド用maturin 1.16.0と関連wheelも、上記英語節の
ライセンス・原本notice保持方針に従います。アプリ本体への依存コード同梱や
実行時の自動取得は行いません。

## 0.5.0で追加した文書読み取り依存

olefile 0.47（BSD-2-ClauseおよびPIL由来の許諾通知）とxlrd 2.0.2（BSD-3-Clauseおよび旧広告・謝辞条項）を追加します。2026-11-14にsdistのPyPI SHA-256と完全なLICENSEを確認しました。再配布時は上記英語節を含む全通知とxlrdの謝辞を保持してください。アプリ本体へのコード同梱や実行時ダウンロードは行いません。

BibDeskRAG本体はMITライセンスです。依存はそれぞれのライセンスを保持し、本プロジェクトは再ライセンスしません。以下は検証した正確な実行時依存です。`packaging/homebrew/resources.json` に各パッケージの固定ソースURL、版、SHA-256、公開PyPIメタデータURLがあります。2026-11-01に全ソースをダウンロードしてlockを検証しました。メタデータが不足・曖昧なPySocks、socksio、tomli-w、lxml、tqdmはインストール済みLICENSE/NOTICEも確認しました。

| パッケージ | 版 | ライセンス |
| --- | --- | --- |
| [anyio](https://pypi.org/project/anyio/4.15.1/) | 4.15.1 | MIT |
| [arxiv](https://pypi.org/project/arxiv/4.0.2/) | 4.0.2 | MIT |
| [bibdeskparser](https://pypi.org/project/bibdeskparser/0.8.1/) | 0.8.1 | MIT |
| [bibtexparser](https://pypi.org/project/bibtexparser/2.0.0b9/) | 2.0.0b9 | MIT |
| [certifi](https://pypi.org/project/certifi/2026.10.23/) | 2026.10.23 | MPL-2.0 |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.5.2/) | 3.5.2 | MIT |
| [click](https://pypi.org/project/click/8.5.0/) | 8.5.0 | BSD-3-Clause |
| [defusedxml](https://pypi.org/project/defusedxml/0.7.1/) | 0.7.1 | PSF-2.0 |
| [et-xmlfile](https://pypi.org/project/et-xmlfile/2.0.0/) | 2.0.0 | MIT |
| [h11](https://pypi.org/project/h11/0.16.0/) | 0.16.0 | MIT |
| [habanero](https://pypi.org/project/habanero/2.9.2/) | 2.9.2 | MIT |
| [httpcore](https://pypi.org/project/httpcore/1.0.9/) | 1.0.9 | BSD-3-Clause |
| [httpcore2](https://pypi.org/project/httpcore2/2.16.0/) | 2.16.0 | BSD-3-Clause |
| [httpx](https://pypi.org/project/httpx/0.28.1/) | 0.28.1 | BSD-3-Clause |
| [httpx2](https://pypi.org/project/httpx2/2.16.0/) | 2.16.0 | BSD-3-Clause |
| [idna](https://pypi.org/project/idna/3.20/) | 3.20 | BSD-3-Clause |
| [lxml](https://pypi.org/project/lxml/6.1.3/) | 6.1.3 | BSD-3-Clause |
| [openpyxl](https://pypi.org/project/openpyxl/3.1.5/) | 3.1.5 | MIT |
| [packaging](https://pypi.org/project/packaging/26.3/) | 26.3 | Apache-2.0 OR BSD-2-Clause |
| [pylatexenc](https://pypi.org/project/pylatexenc/2.11/) | 2.11 | MIT |
| [pypdf](https://pypi.org/project/pypdf/6.21.4/) | 6.21.4 | BSD-3-Clause |
| [pysocks](https://pypi.org/project/pysocks/1.7.1/) | 1.7.1 | BSD-3-Clause |
| [requests](https://pypi.org/project/requests/2.34.2/) | 2.34.2 | Apache-2.0 |
| [socksio](https://pypi.org/project/socksio/1.0.0/) | 1.0.0 | MIT |
| [tomli-w](https://pypi.org/project/tomli-w/1.2.0/) | 1.2.0 | MIT |
| [tqdm](https://pypi.org/project/tqdm/4.70.1/) | 4.70.1 | MPL-2.0 AND MIT |
| [truststore](https://pypi.org/project/truststore/0.10.5/) | 0.10.5 | MIT |
| [typing-extensions](https://pypi.org/project/typing-extensions/4.16.0/) | 4.16.0 | PSF-2.0 |
| [urllib3](https://pypi.org/project/urllib3/2.8.0/) | 2.8.0 | MIT |

MIT、BSD、Apache、PSFはnotice保持などの条件の下でMIT本体と併せた再配布を認めます。Certifiとtqdmの一部はMPL-2.0で、上流のライセンス・ソース情報を保持し、対象ファイルの変更をMPLで利用可能にする必要があります。本プロジェクトはその対象ファイルを変更していません。pip/Homebrew導入では各配布のメタデータ・ライセンスを保持します。統合バイナリの配布者はnoticeと依存のソース提供・通知義務を満たす必要があり、MITはBibDeskRAG自身のコードだけに適用されます。

## ネイティブ・同梱コンポーネント

lxmlの `LICENSES.txt` はElementTree・CPython由来コード、ISO Schematron資源、GPLの上流テストrunner（別途集約されたものでアプリコードではありません）も説明します。個別ライセンス宣言がない抽出用XSL資源も記載されています。上流notice全体を保持し、ソースツリー全体をBSDだけと説明しないでください。HomebrewはMITのlibxml2/libxsltに対しlxmlをソースビルドします。pipのバイナリwheelはzlib（Zlib）、iconv（LGPL-2.1）、libexslt（MIT）を含む場合があり、上流noticeを保持します。BibDeskRAG wheelはこれらを同梱しません。通常のソース・wheel配布を超えて統合バイナリや変更依存を配布する場合は上流の例外を確認してください。

導入済みHomebrew libexsltはlibgcrypt・libgpg-errorにもリンクし、各ライブラリはLGPL-2.1です（導入済み `COPYING.LIB` で確認）。別の動的リンクHomebrew依存として上流notice・ソース義務を保持し、BibDeskRAG wheelにはコピーしません。`otool -L` でリンクを確認しました。Homebrew依存ツリーのCLIツールのライセンスは、リンク先ライブラリ自体のライセンスを表すものではありません。

PyMuPDFは依存に使いません。CPython/SQLiteはインタープリターが提供し、CPythonはPSF、SQLiteはパブリックドメインです。

## ビルド専用入力

`packaging/homebrew/build-resources.json` はオフラインHomebrew bundle内の全wheelを固定し、必要に応じ両macOSアーキテクチャを含みます。bundleは別のRelease成果物で、バックエンドwheelはアプリ実行時依存として導入しません。BibDeskParserのupstream `uv_build` を含むpipの隔離PEP 517バックエンドです。`uv` パッケージマネージャーを導入・実行せず、開発・導入ともpipだけを使います。

| ビルド用パッケージ | 版 | ライセンス |
| --- | --- | --- |
| cython | 3.2.9 | Apache-2.0 |
| dunamai | 1.26.3 | MIT |
| flit-core | 3.12.0 | BSD-3-Clause; 3.12に同梱するtomliはMIT |
| hatch-fancy-pypi-readme | 25.1.0 | MIT |
| hatch-vcs | 0.5.0 | MIT |
| hatchling | 1.33.0 | MIT |
| jinja2 | 3.1.6 | BSD-3-Clause |
| markupsafe | 3.0.4 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pathspec | 1.1.1 | MPL-2.0 |
| pluggy | 1.7.0 | MIT |
| setuptools | 84.0.0, 84.2.1 | MIT |
| setuptools-scm | 10.3.4 | MIT |
| tomlkit | 0.15.2 | MIT |
| trove-classifiers | 2026.9.21.13 | Apache-2.0 |
| uv-build | 0.12.24 | MIT OR Apache-2.0 |
| uv-dynamic-versioning | 0.14.1 | MIT |
| vcs-versioning | 2.6.0 | MIT |
| wheel | 0.48.0 | MIT |

バックエンドwheelの元LICENSE/NOTICEを変更せず保持し、確認済みハッシュとソースプロジェクト情報をbundle manifestに保存します。実行時・ビルドlockを更新するたびにnoticeも更新してください。

上記のビルド用ライセンスはwheel内LICENSEで確認しました。古い分類メタデータがBSD-3-Clause本文と不一致だったため、flitのタグ付きソースLICENSEも確認しました。pathspecはMPL-2.0で、ライセンス・ソース情報とともに未変更で再配布します。socksioはPython 3.14対応のため一時ビルド要件をflit 2から固定3.12.0へ変えますが、実行時ソースは未変更のMITパッケージです。

## 開発・テストツール（アプリwheelに同梱しないもの）

導入済み開発環境を別途確認しました。build 1.6.1、pytest 9.2.0、ruff 0.17.3、iniconfig 2.3.1、pluggy 1.7.0、pyproject-hooks 1.3.3はMIT、Pygments 2.21.0はBSD-2-Clause、ReportLab 4.5.1はBSD、Pillow 13.0.0はMIT-CMUです。残るPython要件は上記実行時・ビルド表にあります。これらは合成fixture生成・パッケージ検証用で、BibDeskRAGソース・wheel・実行環境に同梱しません。
