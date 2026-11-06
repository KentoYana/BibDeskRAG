"""Single-index transactions, schema-v1 migration and offline diagnostics."""
from contextlib import closing
import builtins
import hashlib
import json
import struct

import pytest

from bibdesk_rag import cli, database, indexer, semantic
from bibdesk_rag.config import Config
from bibdesk_rag.search import SQLiteSearch
from bibdesk_rag.semantic_config import SemanticOptions
from test_semantic import FakeBackend, synthetic_bib

LEGACY_EMBEDDINGS = """
CREATE TABLE embeddings (
 chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
 model_id INTEGER NOT NULL REFERENCES embedding_models(id) ON DELETE CASCADE,
 content_hash TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY(chunk_id,model_id)
);
"""


@pytest.fixture
def legacy(tmp_path):
    source = tmp_path / 'sources' / 'refs.bib'
    source.parent.mkdir()
    source.write_text(synthetic_bib().replace('author={Synthetic',
                                            'Bdsk-File-1={evidence.csv},author={Synthetic'))
    (source.parent / 'evidence.csv').write_text('gene,result\nRecQ,observed\n')
    cfg = Config(source, tmp_path / 'data/index.sqlite3',
                 semantic=SemanticOptions(dimensions=4))
    indexer.index_library(cfg)
    with closing(database.connect(cfg.database)) as db, db:
        db.executescript('DROP TABLE embeddings;' + LEGACY_EMBEDDINGS + 'PRAGMA user_version=1;')
        chunk = db.execute('SELECT id FROM chunks LIMIT 1').fetchone()[0]
        db.execute('INSERT INTO embedding_models VALUES (1,?,?,?,?)',
                   ('legacy-chunk-model', 'original', 4, '{}'))
        db.execute('INSERT INTO embeddings VALUES (?,?,?,?)',
                   (chunk, 1, 'original-chunk-hash', struct.pack('<4f', 1, 0, 0, 0)))
    return cfg, FakeBackend(cfg.semantic)


def dump(cfg):
    with closing(database.connect(cfg.database, readonly=True)) as db:
        return db.execute('PRAGMA user_version').fetchone()[0], list(db.iterdump())


def test_v1_readonly_and_successful_migration_preserve_legacy_and_fts(legacy):
    cfg, backend = legacy
    before = hashlib.sha256(cfg.database.read_bytes()).hexdigest()
    with closing(database.connect(cfg.database, readonly=True)) as db:
        assert database.status(db, cfg)['semantic']['schema_upgrade_required']
        assert database.doctor(db, cfg)['ok']
    assert hashlib.sha256(cfg.database.read_bytes()).hexdigest() == before
    cfg.semantic.enabled = True
    result = indexer.index_library(cfg, backend=backend)
    assert result['semantic']['embedded'] == 4
    with closing(database.connect(cfg.database)) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
        row = db.execute('SELECT * FROM embeddings WHERE chunk_id IS NOT NULL').fetchone()
        assert row['content_hash'] == 'original-chunk-hash'
        assert row['vector'] == struct.pack('<4f', 1, 0, 0, 0)
        assert db.execute('SELECT count(*) FROM embeddings').fetchone()[0] == 5
        assert SQLiteSearch(db).search_fulltext('RecQ')
        assert database.doctor(db, cfg)['ok']
        database.initialize(db)
        assert db.execute('SELECT count(*) FROM embeddings').fetchone()[0] == 5
    assert semantic.semantic_search(cfg, 'repair', 1, backend=backend)[0]['citekey'] == 'Repair'


def test_failed_embedding_rolls_back_schema_metadata_text_and_vectors(legacy):
    cfg, backend = legacy
    before = dump(cfg)
    cfg.bib.write_text(cfg.bib.read_text().replace('Synthetic, Researcher', 'Changed, Author'))
    cfg.semantic.enabled = True
    def fail(texts):
        raise RuntimeError('Generated inference failure')
    backend.embed_documents = fail
    with pytest.raises(RuntimeError, match='inference failure'):
        indexer.index_library(cfg, backend=backend, rebuild=True)
    assert dump(cfg) == before


def test_missing_model_preflight_does_not_migrate_or_write(legacy, monkeypatch):
    cfg, _ = legacy
    cfg.semantic.enabled = True
    before = cfg.database.read_bytes()
    def missing(options):
        raise ValueError('Model missing; use --setup')
    monkeypatch.setattr(semantic, 'SentenceTransformerBackend', missing)
    with pytest.raises(ValueError, match='Model missing'):
        indexer.index_library(cfg)
    assert cfg.database.read_bytes() == before


def test_disabled_update_status_check_require_no_inference_dependencies(legacy, monkeypatch):
    cfg, _ = legacy
    original = builtins.__import__
    def forbidden(name, *args, **kwargs):
        if name.split('.')[0] in {'numpy', 'torch', 'sentence_transformers', 'huggingface_hub'}:
            pytest.fail(f'Disabled/diagnostic operations imported {name}')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', forbidden)
    assert indexer.index_library(cfg)['semantic'] == {'enabled': False}
    with closing(database.connect(cfg.database, readonly=True)) as db:
        assert database.status(db, cfg)['semantic']['indexed'] == 0
        assert database.doctor(db, cfg)['ok']
        cfg.semantic.enabled = True
        assert not database.doctor(db, cfg)['ok']


@pytest.mark.parametrize('statement,value,expected', [
    ('UPDATE embeddings SET vector=? WHERE paper_id IS NOT NULL', b'bad', 'dimensions'),
    ('UPDATE embeddings SET vector=? WHERE paper_id IS NOT NULL', b'\0' * 16, 'unnormalized'),
    ('UPDATE embeddings SET content_hash=? WHERE paper_id IS NOT NULL', 'wrong', 'hash'),
    ('UPDATE embeddings SET part=? WHERE paper_id IS NOT NULL', 8, 'contiguous'),
    ('UPDATE embedding_models SET dimensions=? WHERE id=2', 8, 'inconsistent'),
])
def test_check_detects_vector_integrity_without_loading_model(legacy, statement, value, expected):
    cfg, backend = legacy
    cfg.semantic.enabled = True
    indexer.index_library(cfg, backend=backend)
    with closing(database.connect(cfg.database)) as db, db:
        db.execute(statement, (value,))
    before = cfg.database.read_bytes()
    with closing(database.connect(cfg.database, readonly=True)) as db:
        result = database.doctor(db, cfg)
        assert not result['ok']
        assert expected in json.dumps(result['issues'])
    assert cfg.database.read_bytes() == before


def test_index_cli_manages_all_data_and_readonly_diagnostics(legacy, monkeypatch, capsys, tmp_path):
    cfg, backend = legacy
    path = tmp_path / 'settings.toml'
    path.write_text(f'bib={json.dumps(str(cfg.bib))}\ndatabase={json.dumps(str(cfg.database))}\n'
                    '[semantic]\nenabled=true\ndimensions=4\n')
    monkeypatch.setattr(semantic, 'SentenceTransformerBackend', lambda options: backend)
    for action in ('update', 'rebuild'):
        assert cli.main(['--temp', str(path), '-i', action, '--format', 'json']) == 0
        assert json.loads(capsys.readouterr().out)['semantic']['embedded'] == 4
    before = cfg.database.read_bytes()
    for action in ('status', 'check'):
        assert cli.main(['--temp', str(path), '--index', action, '--format', 'json']) == 0
        result = json.loads(capsys.readouterr().out)
        summary = result['semantic']['status'] if action == 'check' else result['semantic']
        assert summary['indexed'] == 4
    assert cfg.database.read_bytes() == before


def test_disabled_metadata_updates_report_stale_vectors_then_reuse_on_enable(legacy):
    cfg, backend = legacy
    cfg.semantic.enabled = True
    indexer.index_library(cfg, backend=backend)
    cfg.semantic.enabled = False
    cfg.bib.write_text(cfg.bib.read_text().replace('DNA damage repair mechanisms', 'New repair'))
    indexer.index_library(cfg)
    with closing(database.connect(cfg.database, readonly=True)) as db:
        checked = database.doctor(db, cfg)
        assert checked['ok']
        assert checked['semantic']['warnings']
        assert checked['semantic']['status']['stale'] == 1
    cfg.semantic.enabled = True
    result = indexer.index_library(cfg, backend=backend)
    assert result['semantic']['embedded'] == 1 and result['semantic']['reused'] == 3


def test_check_handles_missing_model_record_without_crashing(legacy):
    cfg, backend = legacy
    cfg.semantic.enabled = True
    indexer.index_library(cfg, backend=backend)
    with closing(database.connect(cfg.database)) as db, db:
        db.execute("UPDATE settings SET value='999999' WHERE key='semantic_model_id'")
    with closing(database.connect(cfg.database, readonly=True)) as db:
        assert not database.doctor(db, cfg)['ok']
    indexer.index_library(cfg, backend=backend, rebuild=True)
    with closing(database.connect(cfg.database, readonly=True)) as db:
        assert database.doctor(db, cfg)['ok']
