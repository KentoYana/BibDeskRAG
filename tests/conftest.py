"""Keep application discovery isolated from the developer's real configuration."""

import pytest


@pytest.fixture(autouse=True)
def isolated_application_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("BIBDESK_RAG_CONFIG", "BIBDESK_RAG_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
