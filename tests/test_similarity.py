"""Generated saved vectors only: related metadata, no inference or model download."""
import builtins
from contextlib import closing
from dataclasses import replace
import json
import struct

import pytest

from bibdesk_rag import cli, indexer, web
from bibdesk_rag.cli_arguments import parse_args
from bibdesk_rag.config import init_config, load_config
from bibdesk_rag.database import connect
from bibdesk_rag.mcp_server import MCPServer
from bibdesk_rag.semantic import content_hash
from bibdesk_rag.similarity import SimilarPapersError, similar_papers
from test_mcp import initialize, tool
from test_semantic import FakeBackend
from test_web import running, request


@pytest.fixture
def collection(tmp_path):
    bib = tmp_path / 'refs.bib'
    bib.write_text('''@article{Seed,title={Repair seed},abstract={Repair source abstract},year={2026}}
@article{Zulu,title={Repair candidate},abstract={Repair candidate abstract},author={Example, Alice},year={2026},doi={10.9999/zulu}}
@article{Alpha,title={Title only candidate},author={Other, Bob},year={2025},doi={10.9999/alpha}}
@article{Other,title={Other topic},abstract={Other subject},year={2026}}
@article{Missing,title={Not yet embedded}}
@article{Empty,author={Empty Metadata}}
''')
    path = init_config(bib, tmp_path / 'config.toml', tmp_path / 'data')
    text = path.read_text() + '\n[semantic]\nenabled = true\ndimensions = 4\n'
    path.write_text(text)
    config = load_config(path)
    indexer.index_library(config, config_path=path, backend=FakeBackend(config.semantic))
    with closing(connect(config.database)) as db, db:
        model = int(db.execute("SELECT value FROM settings WHERE key='semantic_model_id'").fetchone()[0])
        db.execute('DELETE FROM embeddings WHERE paper_id IS NOT NULL')
        for key, vectors in {
            'Seed': [(1, 0, 0, 0), (0, 1, 0, 0)],
            'Zulu': [(1, 0, 0, 0), (0, 0, 1, 0)],
            'Alpha': [(0, 1, 0, 0)], 'Other': [(0, 0, 1, 0)],
        }.items():
            paper = db.execute('SELECT * FROM papers WHERE citekey=?', (key,)).fetchone()
            for part, vector in enumerate(vectors):
                db.execute('INSERT INTO embeddings(paper_id,part,model_id,content_hash,vector,embedded_at,title_only) VALUES (?,?,?,?,?,?,?)',
                           (paper['id'], part, model, content_hash(paper['title'], paper['abstract']),
                            struct.pack('<4f', *vector), 'generated-fixture', not bool(paper['abstract'])))
    return path, config


def test_saved_vectors_exclude_source_deduplicate_pool_and_sort_ties_without_optional_imports(collection, monkeypatch):
    path, config = collection
    before = {p: p.read_bytes() for p in (path, config.bib, config.database)}
    original = builtins.__import__
    def forbidden(name, *args, **kwargs):
        if name.split('.')[0] in {'numpy', 'torch', 'sentence_transformers', 'transformers', 'huggingface_hub'}:
            pytest.fail('Saved-vector similarity must not import optional inference/numeric libraries')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', forbidden)
    result = similar_papers(config, 'Seed')
    assert [r['citekey'] for r in result['results']] == ['Alpha', 'Zulu', 'Other']
    assert [r['similarity_score'] for r in result['results']] == [1, 1, 0]
    assert result['source']['embedding_parts'] == 2
    assert result['results'][0]['title_only'] and not result['results'][0]['has_abstract']
    assert result['results'][0]['indexed_fields'] == ['title']
    assert result['candidates'] == {'total': 5, 'indexed': 3, 'missing_vectors': 2, 'empty_metadata': 1}
    assert result['index']['freshness'] == 'unverified'
    assert not config.semantic.cache_dir.exists()
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('filters,expected', [
    ({'year': '2026'}, ['Zulu', 'Other']), ({'author': 'ALICE'}, ['Zulu']),
    ({'doi': 'https://doi.org/10.9999/alpha'}, ['Alpha']),
    ({'citekeys': ['Other', 'Zulu']}, ['Zulu', 'Other']), ({'citekeys': []}, []),
    ({'year': '2025', 'author': 'Alice'}, []), ({'citekeys': ['Seed']}, []),
])
def test_common_filters_are_restrictive(collection, filters, expected):
    _, config = collection
    result = similar_papers(config, 'Seed', **filters)
    assert [r['citekey'] for r in result['results']] == expected


@pytest.mark.parametrize('key,code', [('Unknown', 'unknown_citekey'), ('Missing', 'paper_vectors_missing'),
                                     ('Empty', 'paper_vectors_missing')])
def test_missing_source_states_are_distinct(collection, key, code):
    _, config = collection
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, key)
    assert error.value.code == code
    disabled = replace(config, semantic=replace(config.semantic, enabled=False))
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(disabled, key)
    assert error.value.code == 'semantic_disabled'


@pytest.mark.parametrize('mutation,code', [
    ("UPDATE embeddings SET content_hash='stale' WHERE paper_id=(SELECT id FROM papers WHERE citekey='Zulu')", 'stale_vectors'),
    ("UPDATE embeddings SET vector=x'00000000' WHERE paper_id=(SELECT id FROM papers WHERE citekey='Seed')", 'invalid_vectors'),
    ("UPDATE embeddings SET part=3 WHERE paper_id=(SELECT id FROM papers WHERE citekey='Alpha')", 'invalid_vectors'),
    ("UPDATE embeddings SET title_only=0 WHERE paper_id=(SELECT id FROM papers WHERE citekey='Alpha')", 'invalid_vectors'),
    ("UPDATE embedding_models SET version='different'", 'model_mismatch'),
    ("DELETE FROM settings WHERE key='semantic_model_id'", 'semantic_index_missing'),
])
def test_stale_or_inconsistent_vectors_are_not_compared(collection, mutation, code):
    _, config = collection
    with closing(connect(config.database)) as db, db:
        db.execute(mutation)
    before = config.database.read_bytes()
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, 'Seed')
    assert error.value.code == code
    assert config.database.read_bytes() == before


def test_wrong_model_same_dimensions_and_nonfinite_vectors_are_rejected(collection):
    _, config = collection
    with closing(connect(config.database)) as db, db:
        db.execute("INSERT INTO embedding_models SELECT 100,name,'different',dimensions,config_json FROM embedding_models LIMIT 1")
        db.execute("UPDATE embeddings SET model_id=100 WHERE paper_id=(SELECT id FROM papers WHERE citekey='Zulu')")
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, 'Seed')
    assert error.value.code == 'model_mismatch'
    with closing(connect(config.database)) as db, db:
        db.execute("UPDATE embeddings SET model_id=(SELECT value FROM settings WHERE key='semantic_model_id')")
        db.execute("UPDATE embeddings SET vector=? WHERE paper_id=(SELECT id FROM papers WHERE citekey='Other')", (struct.pack('<4f', float('nan'), 0, 0, 0),))
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, 'Seed')
    assert error.value.code == 'invalid_vectors'


def test_config_model_change_rejected_without_loading_a_model(collection):
    _, config = collection
    config.semantic.query_prefix = 'different: '
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, 'Seed')
    assert error.value.code == 'model_mismatch'


def test_cli_mcp_web_share_ranking_filters_and_read_only_snapshot(collection, capsys):
    path, config = collection
    before = {p: p.read_bytes() for p in (path, config.bib, config.database)}
    assert cli.main(['--temp', str(path), '--paper', 'similar', 'Seed', '--top', '2',
                     '--year', '2026', '--format', 'json']) == 0
    command = json.loads(capsys.readouterr().out)
    server = MCPServer(path)
    initialize(server)
    mcp = tool(server, 'similar_papers', citekey='Seed', top=2, year='2026')
    app = web.WebApp(config, path)
    gui = app.similar({'citekey': 'Seed', 'top': 2, 'year': '2026'})
    expected = ['Zulu', 'Other']
    assert [r['citekey'] for r in command['results']] == expected
    assert [r['citekey'] for r in mcp['results']] == expected
    assert [r['paper']['citekey'] for r in gui['papers']] == expected
    assert command['filters'] == mcp['filters'] == gui['filters']
    assert command['embedding_model'] == mcp['embedding_model'] == gui['embedding_model']
    with running(app) as http:
        code, _, payload = request(http, app, '/api/similar', {'citekey': 'Seed', 'top': 2})
        assert code == 200 and json.loads(payload)['paper_count'] == 2
        code, _, payload = request(http, app, '/api/similar', {'citekey': 'Unknown'})
        assert code == 400 and json.loads(payload)['error_code'] == 'unknown_citekey'
        assert request(http, app, '/api/similar', {'citekey': 'Seed'}, headers={'Origin': None})[0] == 403
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('args', [
    ['--paper', 'similar', 'Seed', '--scope', 'all'],
    ['--paper', 'similar', 'Seed', '--mode', 'semantic'],
    ['--paper', 'similar', 'Seed', '--per-paper', '2'],
    ['--paper', 'similar', 'Seed', '--top', '101'],
    ['--paper', 'similar', '', '--year', '2026'],
])
def test_cli_similar_rejects_irrelevant_options_before_loading_config(args):
    with pytest.raises(SystemExit):
        parse_args(args)


def test_similarity_uses_one_snapshot_during_concurrent_metadata_commit(collection, monkeypatch):
    import bibdesk_rag.similarity as module
    _, config = collection
    with closing(connect(config.database)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("UPDATE settings SET value=value WHERE key='last_indexed'")
        writer.commit()
        original = module._vectors
        calls = 0
        def concurrent_update(rows, paper, model):
            nonlocal calls
            result = original(rows, paper, model)
            calls += 1
            if calls == 1:
                writer.execute("UPDATE papers SET title='Changed after snapshot' WHERE citekey='Zulu'")
                writer.commit()
            return result
        monkeypatch.setattr(module, '_vectors', concurrent_update)
        result = similar_papers(config, 'Seed')
        assert next(r for r in result['results'] if r['citekey'] == 'Zulu')['title'] == 'Repair candidate'
    with pytest.raises(SimilarPapersError) as error:
        similar_papers(config, 'Seed')
    assert error.value.code == 'stale_vectors'
