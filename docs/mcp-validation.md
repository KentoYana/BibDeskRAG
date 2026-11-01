# MCP interoperability validation

Validated locally on 2026-11-01 (Asia/Tokyo), macOS 26.7.2, Apple Silicon,
Python 3.12.13, bibdesk-rag 0.1.0.

## Official SDK client

The official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
2.3.0 and `mcp-types` 2.3.0 were installed with pip into the isolated,
Git-ignored `.venv-mcp-client`. They are validation dependencies only; neither
was added to the application's runtime environment or package requirements.
The SDK's installed `Client`, `StdioServerParameters`, and transport/negotiation
implementation were inspected alongside its [official documentation](https://py.sdk.modelcontextprotocol.io/).

Run the reproducible check from the repository root after the ordinary app
development installation:

```sh
.venv/bin/python -m venv .venv-mcp-client
.venv-mcp-client/bin/python -m pip install "mcp==2.3.0"
.venv-mcp-client/bin/python tools/validate_mcp_sdk.py --app-python .venv/bin/python
```

The helper generates a temporary `.bib`, supplementary CSV, configuration and
index; launches the installed application in a real stdio subprocess; and uses
the SDK's default `auto` negotiation. It succeeded with protocol `2025-06-18`.
The client automatically fell back from modern discovery to the server's
supported initialize handshake; no forced legacy mode was necessary.

| Check | Result |
| --- | --- |
| Initialization and six tool descriptors | Passed; all tools marked read-only |
| `search_papers` | Exact DOI returned the expected citekey |
| `search_fulltext` | Returned supplementary CSV path, row 2 and chunk ID |
| `get_paper` | Returned the expected DOI and metadata |
| `get_attachments` | Returned the correct local file path |
| `get_chunk` | Returned source text and matching citation |
| `build_context` | Returned bounded evidence and source locations |
| Invalid `max_chars` | Returned a tool error accepted by the SDK |
| Source/index SHA-256 before and after calls | Identical |

No LLM or external content API was called. Package installation used PyPI;
the interoperability calls themselves used local subprocess stdin/stdout.

## Codex configuration recognition

The installed `codex-cli 0.166.0-alpha.5.1` successfully recognized the server
through temporary command-line `-c` overrides and `codex mcp list --json`.
The reported entry was enabled with transport type `stdio`, the absolute
`bibdesk-rag-mcp` executable, and the temporary app configuration argument.
`auth_status: unsupported` refers to OAuth support, which this local stdio
server does not require.

The invocation had this form, substituting the actual executable and temporary
application config paths:

```sh
codex \
  -c 'mcp_servers.bibdesk-rag-validation.command="/absolute/path/to/bibdesk-rag-mcp"' \
  -c 'mcp_servers.bibdesk-rag-validation.args=["--config","/temporary/config.toml"]' \
  mcp list --json
```

This was a configuration-recognition check, not an end-to-end Codex model tool
call. `mcp list` lists configured servers; it does not establish a successful
tool invocation. The actual stdio handshake and calls were verified with the
official SDK above. See the [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for the distinction between configured servers and active connections.

No Codex user/project config was written, no `CODEX_HOME` override was used,
and the SHA-256 of the existing global config was unchanged. No Codex model
request, login, or persistent MCP registration was performed.

## Response and parser bounds

Regression tests verify that MCP context results retain citation fields but
omit the duplicate excerpt already contained in `context`. A 90,000-character
synthetic context fits within the 120,000-character JSON content limit. List
truncation in `get_paper` is explicitly identified in `truncated_fields`.
Outputs beyond the final response limit produce a valid JSON tool error;
serialized JSON is never cut in the middle.

The supplementary BibTeX macro evaluator was separately exercised with cyclic
definitions, a 40-level reference chain and a concatenated value exceeding
1,000,000 characters. All three were rejected with clear `ValueError`s. The
code limits recursive expansion to 32 levels, performs only string parsing,
and never executes TeX or Python. A regression test confirms that `\\input`
inside an abstract does not read an unrelated file; the LaTeX decoder's file
input facility remains disabled.

The focused `test_bibdesk.py` and `test_mcp.py` suites passed 29 tests after
these checks. This initial SDK run did not establish a Codex desktop session
connection, an Intel Mac run, or an installed Homebrew build. The subsequent
Codex check is recorded below; Homebrew evidence is in
[homebrew-validation.md](homebrew-validation.md).

## Subsequent Codex desktop verification

Later on 2026-11-01, the installed Homebrew executable was registered as the
`bibdesk-rag` stdio MCP server in Codex. An actual Codex conversation invoked
`search_papers` for `RecQ`, then `search_fulltext` restricted to the returned
paper. The result contained the matching citekey, original PDF path, PDF page
number and chunk ID. This was a real tool invocation, not just `codex mcp list`
or a standalone SDK client. No model request was initiated by the package itself.

The user's library, linked attachments, application configuration and index were
checked with SHA-256 before and after the connection work and were unchanged.
These real-library checks are separate from the generated-fixture tests; no
personal library, PDF excerpt, local configuration or index is shipped in the
distribution. A local plugin was also tested, but it is not required for the
documented direct Codex MCP connection.

Ordinary Chat mode in the ChatGPT Mac app is outside the supported setup in
this release. The tested local plugin did not appear there in the user's check,
and no successful ordinary-Chat tool invocation is claimed. Intel Mac execution
also remains unverified.
