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
