# Third-party notices

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
