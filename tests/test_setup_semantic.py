"""Real setup transcripts with generated bibliography and isolated model doubles."""
from contextlib import closing
from io import StringIO
import json

import pytest

from bibdesk_rag import embeddings, indexer, setup
from bibdesk_rag.config import init_config, load_config, set_semantic_enabled
from bibdesk_rag.database import connect, status
from test_semantic import FakeBackend, synthetic_bib


class Terminal(StringIO):
    def __init__(self, events=()):
        super().__init__()
        self.events = iter(events)
    def isatty(self):
        return True
    def readline(self, *args):
        event = next(self.events, None)
        if isinstance(event, BaseException):
            raise event
        return '' if event is None else event + '\n'


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv('BIBDESK_RAG_HOME', str(tmp_path / 'app'))
    monkeypatch.setattr(setup, 'discover_executable', lambda name: None)
    source = tmp_path / 'sources/refs.bib'
    source.parent.mkdir()
    source.write_text(synthetic_bib())
    path = tmp_path / 'config/settings.toml'
    init_config(source, path)
    path.write_text(path.read_text() + '\n# Preserve user comments\n[semantic]\ndimensions=4\n')
    return path, source


def run(path, *answers):
    err = Terminal()
    code = setup.run_setup(path, stdin=Terminal(answers), stderr=err)
    return code, err.getvalue()


def model_doubles(monkeypatch, *, cached):
    calls = []
    monkeypatch.setattr(embeddings, 'model_is_cached', lambda options: cached)
    def download(options):
        calls.append('download')
    def backend(options):
        calls.append('load')
        return FakeBackend(options)
    monkeypatch.setattr(embeddings, 'download_model', download)
    monkeypatch.setattr(embeddings, 'SentenceTransformerBackend', backend)
    return calls


def test_new_setup_declining_never_loads_or_downloads_model(configured, monkeypatch, tmp_path):
    path, bib = configured
    # Use a new config so the entire initial-setup transcript is covered.
    path = tmp_path / 'fresh/config.toml'
    before = bib.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail('Declining semantic search must not inspect/load/download a model')
    for name in ('model_is_cached', 'download_model', 'SentenceTransformerBackend'):
        monkeypatch.setattr(embeddings, name, forbidden)
    code, out = run(path, str(bib), 'y', '', 'y')
    assert code == 0, out
    cfg = load_config(path)
    assert not cfg.semantic.enabled and bib.read_bytes() == before
    with closing(connect(cfg.database, readonly=True)) as db:
        assert status(db, cfg)['semantic']['indexed'] == 0
    assert 'Use semantic search? [y/N]' in out


def test_setup_explicit_download_then_builds_one_index(configured, monkeypatch):
    path, source = configured
    original = source.read_bytes()
    calls = model_doubles(monkeypatch, cached=False)
    code, out = run(path, '1', 'y', 'y', 'y')
    assert code == 0, out
    assert calls == ['download', 'load']
    cfg = load_config(path)
    assert cfg.semantic.enabled
    assert '# Preserve user comments' in path.read_text()
    with closing(connect(cfg.database, readonly=True)) as db:
        summary = status(db, cfg)
        assert summary['counts']['papers'] == summary['semantic']['indexed'] == 4
    assert source.read_bytes() == original
    assert not cfg.database.with_name('index-semantic.sqlite3').exists()
    assert 'no bibliography text is uploaded' in out


def test_existing_enabled_setup_reuses_cache_config_and_database(configured, monkeypatch):
    path, _ = configured
    cfg = set_semantic_enabled(path, True)
    indexer.index_library(cfg, backend=FakeBackend(cfg.semantic))
    before = path.read_bytes(), cfg.database.read_bytes()
    calls = model_doubles(monkeypatch, cached=True)
    code, out = run(path, '', '', '1')
    assert code == 0, out
    assert calls == ['load']
    assert (path.read_bytes(), cfg.database.read_bytes()) == before
    assert 'Cached model found' in out


def test_setup_disable_preserves_existing_vectors(configured, monkeypatch):
    path, _ = configured
    cfg = set_semantic_enabled(path, True)
    indexer.index_library(cfg, backend=FakeBackend(cfg.semantic))
    before = cfg.database.read_bytes()
    calls = model_doubles(monkeypatch, cached=False)
    code, out = run(path, '1', 'n', '1')
    assert code == 0, out
    assert calls == []
    assert not load_config(path).semantic.enabled
    assert cfg.database.read_bytes() == before
    with closing(connect(cfg.database, readonly=True)) as db:
        assert status(db, load_config(path))['semantic']['indexed'] == 4


def test_setup_declined_download_keeps_disabled_without_loading(configured, monkeypatch):
    path, _ = configured
    calls = model_doubles(monkeypatch, cached=False)
    before = path.read_bytes()
    code, out = run(path, '1', 'y', 'n', 'y')
    assert code == 0, out
    assert calls == []
    assert path.read_bytes() == before
    assert not load_config(path).semantic.enabled


@pytest.mark.parametrize('failure', [OSError('offline'), KeyboardInterrupt()])
def test_failed_or_interrupted_download_keeps_config_and_index(configured, monkeypatch, failure):
    path, source = configured
    cfg = load_config(path)
    indexer.index_library(cfg)
    before = path.read_bytes(), cfg.database.read_bytes(), source.read_bytes()
    model_doubles(monkeypatch, cached=False)
    def fail(options):
        raise failure
    monkeypatch.setattr(embeddings, 'download_model', fail)
    code, out = run(path, '1', 'y', 'y')
    assert code == (130 if isinstance(failure, KeyboardInterrupt) else 1), out
    assert (path.read_bytes(), cfg.database.read_bytes(), source.read_bytes()) == before
    assert 'Traceback' not in out


def test_missing_dependencies_produce_install_guidance_without_changing_config(configured, monkeypatch):
    path, _ = configured
    before = path.read_bytes()
    def missing(options):
        raise ValueError('pip install semantic')
    monkeypatch.setattr(embeddings, 'model_is_cached', missing)
    code, out = run(path, '1', 'y')
    assert code == 1
    assert path.read_bytes() == before
    assert 'dependencies are missing' in out and 'Cellar/libexec' in out


@pytest.mark.parametrize('layout', [
    '\n[semantic]\n# Keep this\nenabled = false # comment\ndimensions=4\n',
    '\n["semantic"]\nenabled=false\ndimensions=4\n',
    '\nsemantic = { enabled = false, dimensions = 4 }\n',
    '\nsemantic.enabled = false\nsemantic.dimensions = 4\n',
    '\n[semantic]\ndimensions=4\n',
])
def test_config_toggle_preserves_all_other_values_and_comments(configured, layout):
    path, bib = configured
    cfg = load_config(path)
    text = f'# enabled=false in a comment must remain\nbib={json.dumps(str(bib))}\n'
    text += f'database={json.dumps(str(cfg.database))}\n' + layout
    path.write_text(text)
    enabled = set_semantic_enabled(path, True)
    assert enabled.semantic.enabled
    assert enabled.semantic.dimensions == 4
    assert '# enabled=false in a comment must remain' in path.read_text()
    assert enabled.bib == bib and enabled.database == cfg.database
    disabled = set_semantic_enabled(path, False)
    assert not disabled.semantic.enabled
    assert disabled.semantic.dimensions == 4


def test_linked_config_is_never_overwritten(configured):
    path, _ = configured
    alias = path.with_name('linked.toml')
    alias.hardlink_to(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='linked'):
        set_semantic_enabled(path, True)
    assert path.read_bytes() == alias.read_bytes() == before


def test_enabling_with_retained_keyword_index_reports_pending_vectors(configured, monkeypatch):
    path, _ = configured
    cfg = load_config(path)
    indexer.index_library(cfg)
    before = cfg.database.read_bytes()
    model_doubles(monkeypatch, cached=True)
    code, out = run(path, '1', 'y', '1')
    assert code == 0, out
    assert 'Semantic vectors are not ready' in out and '--index update' in out
    assert cfg.database.read_bytes() == before
    assert load_config(path).semantic.enabled


def test_setup_resumes_first_embedding_failure_without_partial_index(configured, monkeypatch):
    path, _ = configured
    cfg = set_semantic_enabled(path, True)
    broken = FakeBackend(cfg.semantic)
    def failure(texts):
        raise RuntimeError('Generated first-build failure')
    broken.embed_documents = failure
    with pytest.raises(RuntimeError):
        indexer.index_library(cfg, backend=broken)
    model_doubles(monkeypatch, cached=True)
    code, out = run(path, '1', '', '2')
    assert code == 0, out
    with closing(connect(cfg.database, readonly=True)) as db:
        assert status(db, cfg)['semantic']['indexed'] == 4
