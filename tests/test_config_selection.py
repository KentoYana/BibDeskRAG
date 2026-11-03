"""Selection survives invocations without moving or overwriting user-owned data."""

import hashlib
import json
from pathlib import Path
import stat
import sys

import pytest

from bibdesk_rag import config as configuration
from bibdesk_rag.config import (
    activate_config,
    active_config_path,
    config_selection,
    default_config_path,
    default_data_dir,
    init_config,
    load_config,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    for name in ("BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))


def configured(tmp_path, name="custom", attachment=None):
    source = tmp_path / f"{name}.bib"
    source.write_text(
        "@article{Synthetic,title={Synthetic evidence}"
        + (f",Bdsk-File-1={{{attachment}}}" if attachment else "") + "}\n"
    )
    path = tmp_path / name / "config.toml"
    init_config(source, path)
    return path


def hashes(*paths):
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_default_locations_are_consistent_and_resolution_is_read_only(tmp_path):
    expected = tmp_path / ".config/bibdesk-rag/config.toml"
    before = sorted(tmp_path.rglob("*"))
    assert config_selection() == (expected, "default")
    assert default_config_path() == expected
    assert default_data_dir(expected) == tmp_path / ".local/share/bibdesk-rag"
    assert sorted(tmp_path.rglob("*")) == before


def test_scoped_directories_and_custom_data_preserve_isolation(tmp_path, monkeypatch):
    custom = tmp_path / "independent" / "config.toml"
    assert default_data_dir(custom) == custom.parent
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdgconfig"))
    expected = tmp_path / "xdgconfig/bibdesk-rag/config.toml"
    assert config_selection() == (expected, "default")
    assert default_data_dir(expected) == tmp_path / ".local/share/bibdesk-rag"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdgdata"))
    assert default_data_dir(custom) == tmp_path / "xdgdata/bibdesk-rag"
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(tmp_path / "application"))
    assert default_config_path() == tmp_path / "application/config.toml"
    assert active_config_path() == tmp_path / "application/active-config.json"
    assert default_data_dir(custom) == tmp_path / "application"


def test_default_init_uses_separate_config_and_data_locations(tmp_path):
    source = tmp_path / "source.bib"
    source.write_text("@article{A,title={Synthetic}}")
    path = init_config(source)
    assert path == tmp_path / ".config/bibdesk-rag/config.toml"
    assert load_config(path).database == tmp_path / ".local/share/bibdesk-rag/index.sqlite3"
    assert not active_config_path().exists(), "low-level init must not activate implicitly"


def test_active_selection_preserves_config_source_index_and_permissions(tmp_path):
    path = configured(tmp_path)
    config = load_config(path)
    config.database.write_bytes(b"opaque existing index: activation must not open SQLite")
    before = hashes(path, config.bib, config.database)
    assert activate_config(path) == path
    assert config_selection() == (path, "active")
    assert load_config() == config
    pointer = active_config_path()
    assert json.loads(pointer.read_text()) == {"version": 1, "config": str(path)}
    assert stat.S_IMODE(pointer.stat().st_mode) == 0o600
    stamp = pointer.stat().st_mtime_ns
    assert activate_config(path) == path
    assert pointer.stat().st_mtime_ns == stamp
    assert hashes(*before) == before


def test_explicit_then_environment_then_active_then_default_precedence(tmp_path, monkeypatch):
    active = configured(tmp_path, "active")
    explicit = configured(tmp_path, "explicit")
    env = configured(tmp_path, "environment")
    activate_config(active)
    pointer_before = active_config_path().read_bytes()
    monkeypatch.setenv("BIBDESK_RAG_CONFIG", str(env))
    assert config_selection() == (env, "BIBDESK_RAG_CONFIG")
    assert config_selection(explicit) == (explicit, "explicit")
    assert load_config(explicit).bib == tmp_path / "explicit.bib"
    assert active_config_path().read_bytes() == pointer_before
    monkeypatch.delenv("BIBDESK_RAG_CONFIG")
    assert config_selection() == (active, "active")


def test_active_selection_is_scoped_by_config_directory(tmp_path, monkeypatch):
    first = configured(tmp_path, "first")
    second = configured(tmp_path, "second")
    activate_config(first)
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(tmp_path / "alternate-home"))
    assert config_selection()[1] == "default"
    activate_config(second)
    assert default_config_path() == second
    monkeypatch.delenv("BIBDESK_RAG_HOME")
    assert default_config_path() == first


def test_obsolete_mac_config_is_ignored_without_migration_or_deletion(tmp_path, monkeypatch):
    monkeypatch.setattr(configuration.sys, "platform", "darwin")
    legacy = tmp_path / "Library/Application Support/bibdesk-rag/config.toml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('bib = "library.bib"\ndatabase = "index.sqlite3"\n')
    before = hashes(legacy)
    modern = tmp_path / ".config/bibdesk-rag/config.toml"
    assert config_selection() == (modern, "default")
    with pytest.raises(FileNotFoundError):
        load_config()
    assert hashes(legacy) == before
    assert not active_config_path().parent.exists()
    # An explicit path still supports any user-owned configuration location.
    assert config_selection(legacy) == (legacy, "explicit")
    assert load_config(legacy).database == legacy.parent / "index.sqlite3"
    modern.parent.mkdir(parents=True)
    modern.write_text("invalid config, do not fall back")
    assert config_selection() == (modern, "default")
    with pytest.raises(ValueError):
        load_config()
    assert hashes(legacy) == before


def test_modern_config_is_selected_despite_distinct_obsolete_config(tmp_path, monkeypatch):
    monkeypatch.setattr(configuration.sys, "platform", "darwin")
    modern = tmp_path / ".config/bibdesk-rag/config.toml"
    legacy = tmp_path / "Library/Application Support/bibdesk-rag/config.toml"
    modern.parent.mkdir(parents=True)
    modern.write_text('bib = "library.bib"\ndatabase = "index.sqlite3"\n')
    legacy.parent.mkdir(parents=True)
    legacy.write_text('bib = "old.bib"\ndatabase = "old.sqlite3"\n')
    before = hashes(modern, legacy)
    assert config_selection() == (modern, "default")
    assert load_config().database == modern.parent / "index.sqlite3"
    assert hashes(modern, legacy) == before


@pytest.mark.parametrize("override", ["BIBDESK_RAG_HOME", "XDG_CONFIG_HOME"])
def test_obsolete_config_does_not_override_explicit_directory(tmp_path, monkeypatch, override):
    monkeypatch.setattr(configuration.sys, "platform", "darwin")
    legacy = tmp_path / "Library/Application Support/bibdesk-rag/config.toml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("not used")
    monkeypatch.setenv(override, str(tmp_path / "isolated"))
    assert config_selection()[1] == "default"
    assert default_config_path().is_relative_to(tmp_path / "isolated")


def test_missing_active_never_falls_back_and_explicit_use_repairs_it(tmp_path):
    first = configured(tmp_path, "first")
    replacement = configured(tmp_path, "replacement")
    activate_config(first)
    first.unlink()
    with pytest.raises(ValueError, match="Saved configuration is missing"):
        default_config_path()
    assert config_selection(replacement) == (replacement, "explicit")
    activate_config(replacement)
    assert default_config_path() == replacement


@pytest.mark.parametrize("broken", ["configuration", "library", "malformed_library"])
def test_switch_away_from_unusable_previous_configuration(tmp_path, broken):
    first = configured(tmp_path, "first")
    replacement = configured(tmp_path, "replacement")
    activate_config(first)
    if broken == "configuration":
        first.write_text("broken previous configuration")
    elif broken == "library":
        load_config(first).bib.unlink()
    else:
        load_config(first).bib.write_text("@article{Duplicate,title={A}}\n"
                                         "@article{Duplicate,title={B}}\n")
    activate_config(replacement)
    assert default_config_path() == replacement


@pytest.mark.parametrize("content", [
    b"{", b"[]", b'{"version":true,"config":"/somewhere"}',
    b'{"version":2,"config":"/somewhere"}', b'{"version":1,"config":"relative"}',
    b'{"version":1,"config":"/somewhere","extra":0}',
    b"x" * 16385, b"\xff", b'{"version":1,"config":"/bad\\u0000name"}',
])
def test_invalid_selector_is_not_overwritten_or_silently_ignored(tmp_path, content):
    path = configured(tmp_path)
    pointer = active_config_path()
    pointer.parent.mkdir(parents=True)
    pointer.write_bytes(content)
    with pytest.raises(ValueError, match="selection"):
        config_selection()
    with pytest.raises(ValueError, match="selection"):
        activate_config(path)
    assert pointer.read_bytes() == content
    assert config_selection(path) == (path, "explicit")


@pytest.mark.parametrize("link_type", ["symlink", "hardlink"])
def test_linked_selection_file_is_never_replaced(tmp_path, link_type):
    path = configured(tmp_path)
    target = tmp_path / "source.json"
    target.write_text(json.dumps({"version": 1, "config": str(path)}))
    pointer = active_config_path()
    pointer.parent.mkdir(parents=True)
    getattr(pointer, "symlink_to" if link_type == "symlink" else "hardlink_to")(target)
    before = hashes(target)
    with pytest.raises(ValueError, match="owned, unlinked"):
        activate_config(path)
    assert hashes(target) == before
    assert pointer.exists()


def test_selector_cannot_replace_linked_attachment(tmp_path):
    pointer = active_config_path()
    path = configured(tmp_path)
    source = load_config(path).bib
    source.write_text(f"@article{{Synthetic,title={{Synthetic}},Bdsk-File-1={{{pointer}}}}}")
    pointer.parent.mkdir(parents=True)
    pointer.write_text(json.dumps({"version": 1, "config": str(path)}))
    before = hashes(pointer, path, load_config(path).bib)
    with pytest.raises(ValueError, match="overlaps"):
        activate_config(path)
    assert hashes(*before) == before


def test_switch_cannot_replace_attachment_linked_by_previous_library(tmp_path):
    first = configured(tmp_path, "first")
    second = configured(tmp_path, "second")
    activate_config(first)
    pointer = active_config_path()
    source = load_config(first).bib
    source.write_text(f"@article{{Synthetic,title={{Synthetic}},Bdsk-File-1={{{pointer}}}}}")
    before = hashes(pointer, first, second, source, load_config(second).bib)
    with pytest.raises(ValueError, match="overlaps"):
        activate_config(second)
    assert hashes(*before) == before
    assert default_config_path() == first


def test_init_cannot_occupy_reserved_selector_path(tmp_path):
    source = tmp_path / "source.bib"
    source.write_text("@article{A,title={Synthetic}}")
    pointer = active_config_path()
    with pytest.raises(ValueError, match="overlaps"):
        init_config(source, pointer)
    assert not pointer.exists()


def test_init_does_not_leave_config_when_existing_selector_is_invalid(tmp_path):
    source = tmp_path / "source.bib"
    source.write_text("@article{A,title={Synthetic}}")
    pointer = active_config_path()
    pointer.parent.mkdir(parents=True)
    pointer.write_text("invalid selector")
    path = tmp_path / "new config.toml"
    with pytest.raises(ValueError, match="selection"):
        init_config(source, path)
    assert not path.exists()
    assert pointer.read_text() == "invalid selector"


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_selector_cannot_replace_database_or_sidecar(tmp_path, suffix):
    path = configured(tmp_path)
    pointer = active_config_path()
    database = str(pointer)[:-len(suffix)] if suffix else str(pointer)
    if suffix:
        # Pick the application directory so its fixed selector name matches a sidecar.
        database = str(tmp_path / "database")
        pointer = Path(database + suffix)
    original = path.read_text()
    path.write_text(original.replace(str(load_config(path).database), database))
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(configuration, "active_config_path", lambda: pointer)
        with pytest.raises(ValueError, match="overlaps"):
            activate_config(path)
    assert not pointer.exists()


def test_selection_cannot_be_stored_in_python_installation(tmp_path, monkeypatch):
    path = configured(tmp_path)
    installation = tmp_path / "python"
    monkeypatch.setattr(sys, "prefix", str(installation))
    monkeypatch.setenv("BIBDESK_RAG_HOME", str(installation / "state"))
    with pytest.raises(ValueError, match="Python or Homebrew"):
        activate_config(path)
    assert not installation.exists()


@pytest.mark.parametrize("output", ["config", "database"])
def test_init_refuses_application_state_inside_python(tmp_path, monkeypatch, output):
    source = tmp_path / "source.bib"
    source.write_text("@article{A,title={Synthetic}}")
    installation = tmp_path / "python"
    monkeypatch.setattr(sys, "prefix", str(installation))
    path = (installation if output == "config" else tmp_path / "state") / "config.toml"
    data = installation if output == "database" else tmp_path / "derived"
    with pytest.raises(ValueError, match="Python or Homebrew"):
        init_config(source, path, data)
    assert not path.exists()
    assert not installation.exists()


@pytest.mark.parametrize("output", ["config", "database"])
def test_use_refuses_existing_state_inside_python(tmp_path, monkeypatch, output):
    path = configured(tmp_path)
    config = load_config(path)
    installation = path.parent if output == "config" else tmp_path / "python"
    if output == "database":
        path.write_text(path.read_text().replace(str(config.database), str(installation / "index")))
    monkeypatch.setattr(sys, "prefix", str(installation))
    with pytest.raises(ValueError, match="Python or Homebrew"):
        activate_config(path)
    assert not active_config_path().exists()


def test_atomic_write_failure_retains_previous_selection_and_cleans_temporary(tmp_path, monkeypatch):
    first = configured(tmp_path, "first")
    second = configured(tmp_path, "second")
    activate_config(first)
    pointer = active_config_path()
    before = hashes(pointer, first, second)

    def fail_replace(*args):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(configuration.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        activate_config(second)
    assert hashes(*before) == before
    assert default_config_path() == first
    assert not list(pointer.parent.glob(".active-config-*.tmp"))
