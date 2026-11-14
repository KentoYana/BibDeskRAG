# Single-version local validation — 2026-11-14

The user installed and authorized pyenv Python **3.14.10**. It is now the only
interpreter used for this checkout's development and local validation.
`.python-version`, the existing `.venv` path, the separate SDK venv and every
new clean validation environment select that exact pyenv interpreter.
No Python installation or global pyenv/pip setting was changed by this migration.

The 76 existing development package versions were preserved exactly while their
compatible Python 3.14 wheels replaced the Python 3.12 installations. The
validation-only MCP SDK remains 2.3.0 with its existing dependency versions;
its bootstrap pip is supplied by the new interpreter. Old Python 3.12 venvs
used in this task and the temporary migration backups were removed.
Historical logs/results remain as records, not executable environments.

The project's README and bundled manual now specify 3.14.10. Package CI uses
3.14.10 too; the established remote compatibility matrix remains separate
from the sole local execution version. Homebrew continues to manage its own
Python for distributed installations; local validation does not execute it.

| Check using pyenv Python 3.14.10 only | Result |
| --- | --- |
| Development dependency versions | All 76 preserved |
| `pip check` | Passed |
| Full `python -m pytest` | 541 passed, 1 explicit real-model test skipped |
| `ruff check src tests tools` | Passed |
| Isolated sdist and wheel build | Passed |
| Two clean installations and `pip check` | Passed |
| Installed wheel/sdist package smoke | Passed, including generated CFF/AES PDFs |
| Official MCP SDK against both installations | Passed, seven tools including disabled semantic error; no model download |
| Actual public v0.5.0 index → both candidate installations | Passed, old-index reads, source/configuration hashes and incremental reuse retained |
| New PDF dependencies built from source | fontTools, CFFI, pycparser and cryptography passed using cached pinned Python build inputs and offline locked Cargo |
| Source-built PDF dependencies with installed application | Generated CFF/AES extraction and unchanged source bytes passed |
| Release archive/notices/backend-lock checks | Passed |

Generated fixtures only. No user bibliography, attachments, index, configuration
or model cache was migrated or updated. Hosted CI and a complete Homebrew
installation of the candidate remain publication-time checks; Intel hardware
was not tested.

Reports, exact dependency manifests and build/install logs are retained under
the Git-ignored `.local/python314-migration/` directory.

## 日本語

利用者が導入・許可したpyenvのPython **3.14.10**に、開発venv・SDK検証venv・
配布検証用venvを統一しました。既存の開発依存76件の版を保ち、今回使っていた
3.12の環境と移行用バックアップは削除しました。今後のローカル作業で別の
PythonやHomebrewのPythonを流用しません。全体541件成功・1件スキップ、
ruff・配布smoke・SDK・正式版からの更新・PDF依存のソースビルドが成功しました。
