"""Configuration inspection and remembered selection through the public CLI."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from bibdesk_rag import bibdesk, cli
from bibdesk_rag.config import active_config_path, load_config
from bibdesk_rag.extractors import ExtractionOptions
from bibdesk_rag.mcp_server import MCPServer


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path):
    for name in ("BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def invoke(capsys, *args):
    code = cli.main([str(arg) for arg in args])
    output = capsys.readouterr()
    return code, output.out, output.err


def success(capsys, *args):
    code, output, error = invoke(capsys, *args)
    assert code == 0, error
    return output


def fingerprints(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def write_config(path, bib, database, extra=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"bib = {json.dumps(str(bib))}\ndatabase = {json.dumps(str(database))}\n" + extra,
        encoding="utf-8",
    )
    return path


def synthetic_library(root, citekey="Synthetic2026"):
    root.mkdir(parents=True)
    attachment = root / "supplement.csv"
    attachment.write_text("gene,observation\nRecQ,originalmarker\n", encoding="utf-8")
    bib = root / "references.bib"
    bib.write_text(
        f"@article{{{citekey},title={{RecQ synthetic paper}},"
        "doi={10.1234/config-test},Bdsk-File-1={supplement.csv}}\n",
        encoding="utf-8",
    )
    return bib, attachment


def test_show_resolves_effective_values_without_library_or_index_access(
    tmp_path, monkeypatch, capsys
):
    config = write_config(
        tmp_path / "custom settings" / "設定.toml", "../absent.bib", "absent/index.sqlite3",
        "\n[extraction]\nchunk_size = 900\n",
    )
    before = fingerprints(tmp_path)
    directories = {p for p in tmp_path.rglob("*") if p.is_dir()}

    def forbidden(*args, **kwargs):
        pytest.fail("Configuration inspection must not access bibliography or database")

    monkeypatch.setattr(bibdesk, "read_library", forbidden)
    monkeypatch.setattr(cli, "connect", forbidden)
    monkeypatch.setattr(cli, "index_library", forbidden)
    result = json.loads(success(capsys, "--temp", config, "--config", "show", "--format", "json"))
    semantic = result.pop("semantic")
    assert semantic["enabled"] is False
    assert "database" not in semantic
    assert result == {
        "config": str(config), "source": "explicit",
        "bib": str(tmp_path / "absent.bib"),
        "database": str(config.parent / "absent/index.sqlite3"),
        "extraction": asdict(ExtractionOptions(chunk_size=900)),
    }
    text = success(capsys, "--temp", config, "--config", "show")
    assert "[extraction]" in text
    assert "chunk_size = 900" in text and "chunk_overlap = 200" in text
    assert "設定.toml" in text
    assert fingerprints(tmp_path) == before
    assert {p for p in tmp_path.rglob("*") if p.is_dir()} == directories


def test_path_reports_missing_default_without_creating_anything(tmp_path, capsys):
    expected = tmp_path / "home/.config/bibdesk-rag/config.toml"
    assert success(capsys, "--config", "path").strip() == str(expected)
    assert json.loads(success(capsys, "--config", "path", "--format", "json")) == {
        "config": str(expected), "source": "default",
    }
    assert not (tmp_path / "home").exists()
    code, output, error = invoke(capsys, "--config", "show")
    assert code == 1 and not output and str(expected) in error
    assert not (tmp_path / "home").exists()


def test_custom_create_persists_for_update_inspection_and_mcp(tmp_path, monkeypatch, capsys):
    bib, attachment = synthetic_library(tmp_path / "source")
    config = tmp_path / "custom settings/設定.toml"
    database = tmp_path / "derived/index.sqlite3"
    source_before = fingerprints(bib.parent)
    monkeypatch.setenv("BIBDESK_RAG_CONFIG", str(config))
    result = json.loads(success(
        capsys, "--config", "create", "--bib", bib, "--data-dir", database.parent,
        "--format", "json"
    ))
    monkeypatch.delenv("BIBDESK_RAG_CONFIG")
    assert result["config"] == str(config)
    assert fingerprints(bib.parent) == source_before
    assert success(capsys, "--config", "path").strip() == str(config)
    index = json.loads(success(capsys, "--index", "rebuild", "--format", "json"))
    assert index["papers_added"] == 1 and index["files_extracted"] == 1
    config_before = config.read_bytes()
    bib_before = bib.read_bytes()
    attachment.write_text("gene,observation\nRecQ,updatedmarkerwithnewlength\n", encoding="utf-8")
    edited_source = fingerprints(bib.parent)
    update = json.loads(success(capsys, "--index", "update", "--format", "json"))
    assert update["files_extracted"] == 1
    assert fingerprints(bib.parent) == edited_source
    assert config.read_bytes() == config_before and bib.read_bytes() == bib_before
    assert load_config().database == database

    before_reads = fingerprints(tmp_path)
    settings = json.loads(success(capsys, "--config", "show", "--format", "json"))
    assert settings["config"] == str(config) and settings["source"] == "active"
    assert settings["database"] == str(database)
    assert json.loads(success(capsys, "--index", "status", "--format", "json"))["counts"]["papers"] == 1
    assert json.loads(success(capsys, "--index", "check", "--format", "json"))["ok"] is True
    hits = json.loads(success(
        capsys, "--paper", "search", "updatedmarkerwithnewlength", "--scope", "fulltext", "--format", "json"
    ))
    assert hits[0]["citekey"] == "Synthetic2026"
    assert hits[0]["file_path"] == str(attachment)
    mcp = MCPServer().call_tool("search_fulltext", {
        "query": "updatedmarkerwithnewlength", "citekeys": ["Synthetic2026"],
    })
    assert mcp["isError"] is False
    assert json.loads(mcp["content"][0]["text"])["data"][0]["citekey"] == "Synthetic2026"
    assert fingerprints(tmp_path) == before_reads
    repeated = json.loads(success(capsys, "--index", "update", "--format", "json"))
    assert repeated["files_extracted"] == 0 and repeated["files_reused"] == 1


def test_use_persists_but_explicit_inspection_and_failed_switch_do_not(tmp_path, capsys):
    bib, _ = synthetic_library(tmp_path / "source")
    first = write_config(tmp_path / "first/config.toml", bib, tmp_path / "first/index.sqlite3")
    second = write_config(tmp_path / "second/config.toml", bib, tmp_path / "second/index.sqlite3")
    result = json.loads(success(capsys, "--config", "use", first, "--format", "json"))
    assert result["active_config"] == result["config"] == str(first)
    before = fingerprints(tmp_path)
    assert json.loads(success(
        capsys, "--temp", second, "--config", "show", "--format", "json"
    ))["source"] == "explicit"
    assert success(capsys, "--config", "path").strip() == str(first)
    assert fingerprints(tmp_path) == before

    with pytest.raises(SystemExit) as stopped:
        cli.main(["--temp", str(first), "--config", "use", str(second)])
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "--temp" in error
    assert fingerprints(tmp_path) == before
    second.write_text("not valid TOML \n", encoding="utf-8")
    pointer_before = active_config_path().read_bytes()
    code, _, _ = invoke(capsys, "--config", "use", second)
    assert code == 1
    assert active_config_path().read_bytes() == pointer_before
    assert success(capsys, "--config", "path").strip() == str(first)


def test_environment_override_is_reported_without_discarding_saved_selection(
    tmp_path, monkeypatch, capsys
):
    bib, _ = synthetic_library(tmp_path / "source")
    saved = write_config(tmp_path / "saved/config.toml", bib, tmp_path / "saved/index.sqlite3")
    override = write_config(tmp_path / "override/config.toml", bib,
                            tmp_path / "override/index.sqlite3")
    monkeypatch.setenv("BIBDESK_RAG_CONFIG", str(override))
    code, output, error = invoke(capsys, "--config", "use", saved, "--format", "json")
    assert code == 0 and "BIBDESK_RAG_CONFIG overrides" in error
    result = json.loads(output)
    assert result["active_config"] == str(saved)
    assert result["config"] == str(override)
    assert result["source"] == "BIBDESK_RAG_CONFIG"
    temporary = json.loads(success(capsys, "--temp", saved, "--config", "show", "--format", "json"))
    assert temporary["config"] == str(saved) and temporary["source"] == "explicit"
    assert json.loads(success(capsys, "--config", "show", "--format", "json"))["config"] == str(override)
    monkeypatch.delenv("BIBDESK_RAG_CONFIG")
    assert success(capsys, "--config", "path").strip() == str(saved)


def test_missing_saved_config_does_not_fall_back_to_default(tmp_path, capsys):
    bib, _ = synthetic_library(tmp_path / "source")
    saved = write_config(tmp_path / "saved/config.toml", bib, tmp_path / "saved/index.sqlite3")
    success(capsys, "--config", "use", saved)
    default = Path.home() / ".config/bibdesk-rag/config.toml"
    write_config(default, bib, tmp_path / "fallback/index.sqlite3")
    saved.unlink()
    before = fingerprints(tmp_path)
    code, output, error = invoke(capsys, "--index", "update", "--format", "json")
    assert code == 1 and not output and str(saved) in error
    assert fingerprints(tmp_path) == before
    assert not (tmp_path / "fallback").exists()


@pytest.mark.parametrize("has_saved_selection", [False, True])
def test_create_rejects_temporary_selection_before_writing(tmp_path, capsys, has_saved_selection):
    bib, _ = synthetic_library(tmp_path / "source")
    if has_saved_selection:
        saved = write_config(tmp_path / "saved/config.toml", bib,
                             tmp_path / "saved/index.sqlite3")
        success(capsys, "--config", "use", saved)
    before = fingerprints(tmp_path)
    temporary = tmp_path / "temporary settings/config.toml"
    database = tmp_path / "temporary data/index.sqlite3"
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--temp", str(temporary), "--config", "create", "--bib", str(bib),
                  "--data-dir", str(database.parent)])
    assert stopped.value.code == 2
    assert "--temp" in capsys.readouterr().err
    assert fingerprints(tmp_path) == before
    assert not temporary.parent.exists() and not database.parent.exists()
    assert active_config_path().exists() == has_saved_selection


def test_old_config_path_syntax_fails_without_changing_selection(tmp_path, capsys):
    bib, _ = synthetic_library(tmp_path / "source")
    saved = write_config(tmp_path / "saved/config.toml", bib, tmp_path / "saved/index.sqlite3")
    success(capsys, "--config", "use", saved)
    before = fingerprints(tmp_path)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--config", str(saved), "config", "show"])
    assert stopped.value.code == 2
    capsys.readouterr()
    assert fingerprints(tmp_path) == before
    assert success(capsys, "--config", "path").strip() == str(saved)


def test_temporary_update_changes_only_requested_library(tmp_path, capsys):
    first_bib, _ = synthetic_library(tmp_path / "first source", "SavedPaper")
    second_bib, second_attachment = synthetic_library(tmp_path / "second source", "TempPaper")
    first = write_config(tmp_path / "first/config.toml", first_bib,
                         tmp_path / "first/index.sqlite3")
    second_database = tmp_path / "second/index.sqlite3"
    second = write_config(tmp_path / "second/config.toml", second_bib, second_database)
    success(capsys, "--config", "use", first, "--format", "json")
    success(capsys, "--index", "rebuild", "--format", "json")
    success(capsys, "--temp", second, "--index", "rebuild", "--format", "json")
    second_attachment.write_text("gene,observation\nRecQ,temporarychangedmarker\n")
    before = fingerprints(tmp_path)

    updated = json.loads(success(capsys, "--temp", second, "--index", "update", "--format", "json"))
    assert updated["files_extracted"] == 1
    after = fingerprints(tmp_path)
    assert set(after) == set(before)
    assert all(after[name] == value for name, value in before.items()
               if name != str(second_database.relative_to(tmp_path)))
    found = json.loads(success(
        capsys, "--temp", second, "--paper", "search", "temporarychangedmarker", "--format", "json"
    ))
    assert {hit["citekey"] for hit in found} == {"TempPaper"}

    assert success(capsys, "--config", "path").strip() == str(first)
    saved_update = json.loads(success(capsys, "--index", "update", "--format", "json"))
    assert saved_update["files_extracted"] == 0 and saved_update["files_reused"] == 1
    saved_found = json.loads(success(capsys, "--paper", "search", "originalmarker", "--format", "json"))
    assert {hit["citekey"] for hit in saved_found} == {"SavedPaper"}


def test_text_retrieval_keeps_bibliography_and_attachment_provenance(tmp_path, capsys):
    bib, attachment = synthetic_library(tmp_path / "source")
    config = write_config(tmp_path / "settings/config.toml", bib,
                          tmp_path / "derived/index.sqlite3")
    success(capsys, "--config", "use", config)
    success(capsys, "--index", "update", "--format", "json")
    before = fingerprints(tmp_path)
    hits = json.loads(success(
        capsys, "--paper", "search", "originalmarker", "--scope", "fulltext",
        "--format", "json",
    ))
    assert hits[0]["chunk_id"] and hits[0]["row_start"] == 2
    text = success(capsys, "--paper", "search", "originalmarker", "--scope", "fulltext")
    assert "Synthetic2026" in text and "originalmarker" in text
    assert str(attachment) in text and "10.1234/config-test" in text
    assert "chunk" in text.lower() and "row" in text.lower()
    paper = success(capsys, "--paper", "show", "Synthetic2026")
    assert "Synthetic2026" in paper and "RecQ synthetic paper" in paper
    assert "10.1234/config-test" in paper
    files = success(capsys, "--paper", "attachments", "Synthetic2026")
    assert str(attachment) in files
    context = success(capsys, "--paper", "context", "originalmarker")
    assert "Synthetic2026" in context and "originalmarker" in context
    assert str(attachment) in context
    assert fingerprints(tmp_path) == before
