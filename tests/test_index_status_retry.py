"""Issue #8: generated sources, bounded read-only status and explicit retry."""
from contextlib import closing
import hashlib
import json

import pytest

from bibdesk_rag import cli, indexer
from bibdesk_rag.cli_arguments import parse_args
from bibdesk_rag.config import init_config, load_config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import connect, index_state
from bibdesk_rag.extractors.common import ExtractionResult
from bibdesk_rag.mcp_server import MCPServer
from bibdesk_rag.search import SQLiteSearch
from test_mcp import initialize, tool


def hashes(paths):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.fixture
def sources(tmp_path, monkeypatch):
    files = {name: tmp_path / (name + '.csv') for name in ('failed', 'good', 'partial')}
    for name, path in files.items():
        path.write_text(f'gene,value\nRecQ,{name}\n')
    media = tmp_path / 'movie.mp4'
    media.write_bytes(b'generated excluded media')
    files['media'] = media
    bib = tmp_path / 'refs.bib'
    bib.write_text(
        '@article{A,title={RecQ},Bdsk-File-1={failed.csv},Bdsk-File-2={movie.mp4}}\n'
        '@article{B,title={Other},Bdsk-File-1={good.csv},Bdsk-File-2={partial.csv}}\n'
        '@article{Shared,title={Shared},Bdsk-File-1={failed.csv}}\n')
    config_path = init_config(bib, tmp_path / 'app/config.toml')
    config = load_config(config_path)
    real = indexer.extract_file

    def initially_failing(path, options):
        if path == files['failed']:
            return ExtractionResult(status='error', error='generated transient failure')
        result = real(path, options)
        if path == files['partial']:
            result.status = 'partial'
            result.error = 'generated partial failure'
        return result

    monkeypatch.setattr(indexer, 'extract_file', initially_failing)
    indexer.index_library(config)
    monkeypatch.setattr(indexer, 'extract_file', real)
    return config_path, config, files


def states(config):
    with closing(connect(config.database, readonly=True)) as db:
        return {row['path']: dict(row) for row in db.execute('SELECT * FROM attachments')}


@pytest.mark.parametrize('selector', ['citekey', 'id', 'path', 'status'])
def test_retry_unchanged_failure_only_and_shared_attachment_once(sources, monkeypatch, selector):
    config_path, config, files = sources
    before = hashes([config_path, config.bib, *files.values()])
    saved = states(config)
    with closing(connect(config.database, readonly=True)) as db:
        old_generation = index_state(db)['index_generation']
        good_chunks = [tuple(row) for row in db.execute(
            'SELECT * FROM chunks WHERE attachment_id=?', (saved[str(files['good'])]['id'],))]
    # Hash verification alone must not force extraction of identical failed content.
    checked = indexer.index_library(config, verify_hashes=True)
    assert checked['files_extracted'] == 0 and checked['files_reused'] == 4
    assert checked['remaining_issues'] == {'error': 1, 'partial': 1}
    calls = []
    real = indexer.extract_file

    def record(path, options):
        calls.append(path)
        return real(path, options)

    monkeypatch.setattr(indexer, 'extract_file', record)
    options = {
        'citekey': {'retry_citekeys': ['A', 'Shared']},
        'id': {'retry_attachment_ids': [saved[str(files['failed'])]['id']]},
        'path': {'retry_paths': [str(files['failed'])]},
        'status': {'retry_statuses': ['error']},
    }[selector]
    report = indexer.index_library(config, **options)
    assert calls == [files['failed']]
    assert report['retry'] == {'selected': 1, 'attempted': 1}
    assert report['files_extracted'] == 1 and report['files_reused'] == 3
    assert report['resolved_issues'] == 1 and report['new_issues'] == 0
    assert report['remaining_issues'] == {'partial': 1} and not report['errors']
    assert hashes(before) == before
    with closing(connect(config.database, readonly=True)) as db:
        assert index_state(db)['index_generation'] != old_generation
        assert [tuple(row) for row in db.execute(
            'SELECT * FROM chunks WHERE attachment_id=?',
            (saved[str(files['good'])]['id'],))] == good_chunks
        hits = SQLiteSearch(db).search_fulltext('failed')
        assert {h['citekey'] for h in hits} == {'A', 'Shared'}
        assert all(h['row_start'] == 2 and h['content_hash'] == before[files['failed']] for h in hits)
    assert indexer.index_library(config)['files_extracted'] == 0


def test_identity_union_and_status_intersection(sources):
    _, config, files = sources
    report = indexer.index_library(config, retry_citekeys=['A'], retry_paths=[str(files['partial'])],
                                   retry_statuses=['partial'])
    assert report['retry']['selected'] == 1
    assert states(config)[str(files['failed'])]['extraction_status'] == 'error'
    assert report['remaining_issues'] == {'error': 1}


@pytest.mark.parametrize('options', [
    {'retry_citekeys': ['unknown']}, {'retry_attachment_ids': [99999]},
    {'retry_paths': ['/not/linked.csv']}, {'retry_statuses': ['excluded']},
    {'retry_attachment_ids': [True]}, {'retry_attachment_ids': [0]},
    {'rebuild': True, 'retry_statuses': ['error']},
])
def test_bad_selection_keeps_index_and_sources(sources, options):
    config_path, config, files = sources
    before = hashes([config_path, config.bib, config.database, *files.values()])
    with pytest.raises(ValueError):
        indexer.index_library(config, **options)
    assert hashes(before) == before


def test_retry_failure_rollback_preserves_generation_and_chunks(sources, monkeypatch):
    config_path, config, files = sources
    before = hashes([config_path, config.bib, config.database, *files.values()])

    def crash(*args):
        raise RuntimeError('generated interruption')

    monkeypatch.setattr(indexer, 'extract_file', crash)
    with pytest.raises(RuntimeError, match='generated interruption'):
        indexer.index_library(config, retry_citekeys=['B'])
    assert hashes(before) == before


def test_mcp_status_never_reads_sources_and_legacy_generation_is_unknown(sources):
    config_path, config, files = sources
    with closing(connect(config.database)) as db, db:
        db.execute("DELETE FROM settings WHERE key='index_generation'")
    files['failed'].unlink()
    config.bib.write_text('changed since indexing')
    before = hashes([config_path, config.bib, config.database, files['good']])
    server = MCPServer(config_path)
    initialize(server)
    result = tool(server, 'get_index_status')
    assert result['library']['bib_path'] == str(config.bib)
    assert result['library']['indexed_bib_hash'] != before[config.bib]
    assert result['index_generation'] is None and result['last_successful_update']
    assert result['freshness'] == 'unverified'
    assert result['counts']['papers'] == 3
    assert result['extraction_status'] == {'error': 1, 'excluded': 1, 'ok': 1, 'partial': 1}
    assert hashes(before) == before


def test_context_provenance_and_actual_scope(sources):
    config_path, config, files = sources
    before = hashes([config_path, config.bib, config.database, *files.values()])
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        metadata = build_context(engine, 'RecQ')
        assert metadata['search_scope']['fulltext_citekeys'] == ['A']
        assert metadata['results'][0]['source_type'] == 'metadata'
        assert metadata['results'][0]['content_hash'] is None
        selected = build_context(engine, 'RecQ', citekeys=['B'])
        assert selected['search_scope']['fulltext_citekeys'] == ['B']
        result = selected['results'][0]
        assert result['content_hash'] == before[files['good']]
        assert result['index_generation'] == selected['index']['index_generation']
        assert result['indexed_bib_hash'] == before[config.bib]
        assert selected['index']['freshness'] == 'unverified'
        assert build_context(engine, 'good')['search_scope']['fulltext_scope'] == 'all_indexed_papers'
        empty = build_context(engine, 'RecQ', metadata_query='NoSuchMetadata')
        assert empty['returned'] == 0 and empty['search_scope']['fulltext_scope'] == 'not_searched'
        empty = build_context(engine, 'RecQ', citekeys=[])
        assert empty['returned'] == 0 and empty['search_scope']['fulltext_citekeys'] == []
    assert hashes(before) == before


def test_cli_retry_and_remaining_issues(sources, capsys):
    config_path, config, _ = sources
    assert cli.main(['--temp', str(config_path), '--index', 'update', '--retry-citekey', 'A',
                     '--retry-status', 'error', '--format', 'json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['resolved_issues'] == 1 and report['remaining_issues'] == {'partial': 1}
    assert cli.main(['--temp', str(config_path), '--index', 'status', '--format', 'json']) == 0
    assert json.loads(capsys.readouterr().out)['index_generation']


@pytest.mark.parametrize('arguments', [
    ['--index', 'status', '--retry-status', 'error'],
    ['--index', 'rebuild', '--retry-citekey', 'A'],
    ['--index', 'update', '--retry-attachment', '0'],
    ['--index', 'update', '--retry-status', 'excluded'],
    ['--paper', 'show', 'A', '--retry-path', 'file.csv'],
])
def test_retry_flags_are_update_only(arguments):
    with pytest.raises(SystemExit):
        parse_args(arguments)


def test_repeated_failure_reports_this_run_and_reused_remaining_separately(sources, monkeypatch):
    _, config, files = sources

    def still_failing(path, options):
        assert path == files['failed']
        return ExtractionResult(status='error', error='generated second failure')

    monkeypatch.setattr(indexer, 'extract_file', still_failing)
    report = indexer.index_library(config, retry_statuses=['error'])
    assert report['errors'] == [{'path': str(files['failed']), 'error': 'generated second failure'}]
    assert report['remaining_issues'] == {'error': 1, 'partial': 1}
    assert report['new_issues'] == report['resolved_issues'] == 0
    assert report['files_reused'] == 3


def test_excluded_media_is_not_a_retry_target(sources, monkeypatch):
    _, config, files = sources
    saved = states(config)

    def no_extraction(*args):
        pytest.fail('No unchanged attachment should be extracted')

    monkeypatch.setattr(indexer, 'extract_file', no_extraction)
    report = indexer.index_library(config, retry_attachment_ids=[saved[str(files['media'])]['id']])
    assert report['retry'] == {'selected': 0, 'attempted': 0}
    assert report['files_extracted'] == 0
    assert states(config)[str(files['media'])]['extraction_status'] == 'excluded'
