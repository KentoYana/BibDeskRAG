# PDF dependency validation — 2026-11-14

Current local execution policy: use only pyenv Python 3.14.10, explicitly
authorized by the user after the earlier Python 3.12.13 restriction.
`.python-version` and the development venv now select that interpreter.
The tables below retain the earlier execution history; the current rerun is
recorded in [Python 3.14 validation](python314-validation.md). Homebrew
distribution definitions do not authorize a different local interpreter.

Unreleased changes on `codex/p0-index-integrity`, based on v0.5.0 plus the
local P0 implementation. No user bibliography, attachment, configuration or
index was used or updated.

Direct runtime requirements now include `fonttools==4.68.0` and
`cryptography==50.0.2`; Homebrew additionally locks CFFI 2.1.1 and pycparser
3.12. All four upstream sdists were downloaded and checked against PyPI SHA-256
metadata. Their source licenses, including the Apache/BSD alternatives for
cryptography, were inspected; see [third-party notices](../THIRD_PARTY_NOTICES.md).
The existing 31 semantic runtime wheel records remain unchanged.

PDF extraction version is now 2. The next explicit index update retries PDFs
and ZIPs once, including earlier cached failures; unrelated unchanged formats
remain reusable. No automatic update of the user's real index was run.

| Check | Result |
| --- | --- |
| Project Python 3.12 full suite | 541 passed, 1 real-model test skipped |
| `ruff check src tests tools`, `git diff --check` | Passed |
| Generated embedded CFF with custom byte encoding and no ToUnicode | Decoded as CFF; simulated missing fontTools yields ABB and the dependency warning |
| Generated AES-128/AES-256 with empty user password | Text and page provenance extracted; source hashes unchanged |
| Generated password-required AES PDFs | Remain encrypted with no extracted text; sources unchanged |
| Generated cached PDF/ZIP failure → PDF version 2 | PDF and ZIP retried, CSV reused, subsequent update reused all |
| Isolated sdist/wheel build and two clean Python 3.12 installs | Passed, both `pip check` passed |
| Installed package smoke, wheel and sdist | Passed, including generated CFF and AES-256 PDFs |
| Official MCP SDK and public v0.5.0 index upgrade, both installs | Passed; P0 checks retained |
| Homebrew Python 3.14 source builds of all four new packages | Passed using pinned Python build wheels |
| Cryptography rebuild with `--locked` and cached Cargo offline | Passed, OpenSSL 3.5.9 from Homebrew |
| Source-built Python 3.14 dependencies with pypdf | Both generated CFF and AES-256 decoded correctly |
| Native linkage | `otool -L` confirmed the source-built crypto extension links Homebrew libssl/libcrypto |
| Local generated Formula syntax/style | Passed after using a unique local class and ordinary Ruby header comments; template remains unreleased |
| Release archive/backend-lock checks | Passed, licenses and complete original backend-wheel notices retained |

The Python build bundle adds Maturin 1.16.0 and CFFI/pycparser wheels for the
isolated cryptography build, with verified arm64/x86_64 inputs. Formula builds
use Homebrew Rust/OpenSSL/libffi and a build-local Cargo cache; `--locked`
preserves upstream Cargo.lock checksums. Cargo may acquire those fixed crates
at build time. Application runtime never invokes pip/Cargo or downloads models.

This run validates focused native source builds, not a complete new Homebrew
installation or hosted CI. The public Homebrew installation/tap was not changed.
[Upstream cryptography 49+ dropped Intel macOS support](https://cryptography.io/en/50.0.2/changelog/);
the current dependency was tested on Apple Silicon, not Intel hardware.

Logs, source/build artifacts, and SDK/upgrade JSON reports are under the
Git-ignored `.local/pdf-dependencies/` directory. Runtime source locks contain
35 packages; the shared build/semantic bundle contains 56 original wheel files.

## 日本語

現在の作業方針：利用者が導入・許可したpyenvのPython 3.14.10だけを開発・
ローカル検証に使います。以前の3.12.13指定を置き換え、`.python-version` と
開発venvも統一します。以下の表は従来の実行記録であり、移行後の再検証結果は
[Python 3.14検証](python314-validation.md)に記録します。Homebrewの別Pythonを
ローカル検証に流用しません。

fontTools・cryptographyの追加と間接依存、Homebrewの固定ソース・ビルド入力、
Rust/OpenSSL/libffi要件をそろえました。生成PDFでCFFの独自文字コードとAESを
検証し、パスワード必須文書の拒否と原本不変を維持しています。次回updateでは
PDF/ZIPだけを一度再抽出します。実ライブラリの索引更新や公開版の変更は未実施です。
全体541件成功・1件スキップ、wheel/sdistの配布smokeとPython 3.14ソースビルドが
成功しました。Homebrew全体の再導入・ホストCI・Intel実機は未検証です。
