# P0 implementation validation — 2026-11-14

Historical P0 validation before the development interpreter migration.
Current development/local validation uses only pyenv Python 3.14.10;
see [the migration validation](python314-validation.md).

Scope: local working tree based on v0.5.0 commit
`d1771942b034bcd5b31e9277d17d9107f0b0f954`, branch
`codex/p0-index-integrity`. This is not a published release.

Generated fixtures only. No user library, attachment, configuration, index,
model cache or global Python settings were used or changed.

The implementation covers issue #4's shared binding checks, #5's context
truncation and read snapshots, #6's per-format/normalization versions, and
#7's compatibility contract and automated release checks. The contract and
publication-time gates are in [compatibility.md](compatibility.md).

The focused regressions include all CLI read/update/rebuild routes and all seven
MCP tools rejecting library mismatch, unchanged source/database hashes and
permissions on refusal, empty first-build recovery, missing identity rejection,
normal source edits versus explicit moved-library rebuild, source versus budget
truncation, an actual SQLite WAL commit between context SELECTs, selective parser
updates including ZIP, FTS refresh without re-extraction, and rollback on failure.

Local full-suite result:
**535 passed, 1 skipped**; `ruff check src tests tools` passed.
The skipped test requires an explicitly supplied real model and was not enabled.

| Local check | Result |
| --- | --- |
| Isolated pip sdist + wheel build | Passed, pinned setuptools/wheel from the existing offline cache |
| Wheel/sdist installation in two new Python 3.12 venvs | Passed; both `pip check` passed |
| `tools/package_smoke.py` for both installations | Passed, generated PDF/CSV/document-format evidence and source/config/index preservation |
| Official MCP SDK 2.3.0 for both installations | Passed, seven tools including disabled semantic error, protocol 2025-06-18, bounds/invalid arguments, metadata/runtime/CLI/serverInfo version agreement and hashes |
| Public v0.5.0 → working-tree wheel and sdist | Passed, both `tools/validate_upgrade.py` runs |
| Archive metadata/literal runtime/tag agreement and notices | Passed, local `check_release.py --tag v0.5.0`; no tag was created |
| `git diff --check` | Passed |

The prior wheel was downloaded from the actual v0.5.0 GitHub Release; SHA-256
`188d84f90581d293a5317e60339af827dd1e831d73dd4eecedee1aca8106f5e9`
matched the release asset digest. Old and candidate environments are separate.
The candidate retains the unreleased working-tree version 0.5.0; this is a test
of different application builds, not a claim that a new numbered release exists.

Upgrade validation checked the original index before any candidate update,
retained the old MCP `--config PATH` spelling and 2024-11-05 negotiation, reused
unchanged attachments, preserved logical paper/chunk results and source/config/
selection hashes, then observed an intentional generated attachment change.
Schema-1 migration/rollback are separately exercised in the full suite.

Logs and JSON reports are in the Git-ignored `.local/p0-validation/` directory:
`sdk-wheel.json`, `sdk-sdist.json`, `upgrade-wheel.json`,
`upgrade-sdist.json`, installation/build logs, and the checked release artifacts.
Runtime dependencies were downloaded only for these isolated validation
environments; application dependencies and user installation were not changed.

Hosted CI, Homebrew installation of this candidate, real-model SDK success and
live Codex reconnection were not run. Before v1.0 publication, execute the hosted
workflow on the actual candidate commit and compare the published artifacts to
that run's SHA256SUMS. Issues must not be closed merely because local checks pass.
