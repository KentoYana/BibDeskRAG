# Homebrew validation — 2026-11-01

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

## Reproducible build inputs

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

## Executed checks

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

## Scope and remaining release work

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
