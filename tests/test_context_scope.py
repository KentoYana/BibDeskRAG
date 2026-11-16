"""Generated sources only: explicit broad context, strict filters and evaluation."""
from collections import Counter
from contextlib import closing
import hashlib
import json

import pytest

from bibdesk_rag import cli
from bibdesk_rag.config import init_config, load_config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import connect
from bibdesk_rag.indexer import index_library
from bibdesk_rag.mcp_server import MCPServer
from bibdesk_rag.search import SQLiteSearch
from test_mcp import initialize, tool
from tools.evaluate_search import DATASET, evaluate, load_dataset, metrics
from tools.package_smoke import synthetic_pdf


@pytest.fixture
def collection(tmp_path):
    entries = []
    for i in range(25):
        path = tmp_path / f'decoy{i}.pdf'
        path.write_bytes(synthetic_pdf('Unrelated synthetic background.'))
        entries.append('@article{Decoy' + str(i) + ',title={CrowdNeedle},Bdsk-File-1={' + path.name + '}}')
    target = tmp_path / 'target.pdf'
    target.write_bytes(synthetic_pdf('CrowdNeedle bodyonlyprobe target observation.'))
    entries.extend([
        '@article{Target,title={CrowdNeedle},doi={10.9999/target},Bdsk-File-1={target.pdf}}',
        '@article{BodyDecoy,title={bodyonlyprobe},doi={10.9999/decoy}}',
        '@article{ExactOnly,title={Metadata identity},doi={10.9999/exact}}',
    ])
    bib = tmp_path / 'refs.bib'
    bib.write_text('\n'.join(entries))
    config_path = init_config(bib, tmp_path / 'settings/config.toml', tmp_path / 'derived')
    config = load_config(config_path)
    index_library(config)
    return config_path, config


def test_broad_context_reaches_body_only_and_26th_candidate_without_changing_default(collection):
    _, config = collection
    before = config.database.read_bytes()
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        for query in ('CrowdNeedle', 'bodyonlyprobe'):
            baseline = build_context(engine, query, top=10, max_chars=100000)
            broad = build_context(engine, query, top=10, max_chars=100000, scope='fulltext')
            assert 'Target' not in [r['citekey'] for r in baseline['results']]
            assert broad['results'][0]['citekey'] == 'Target'
            assert broad['results'][0]['page_start'] == broad['results'][0]['page_end'] == 2
            assert broad['results'][0]['content_hash'] == hashlib.sha256((config.bib.parent/'target.pdf').read_bytes()).hexdigest()
            assert broad['search_scope']['fulltext_scope'] == 'all_indexed_papers'
            assert broad['search_scope']['metadata_limits_fulltext'] is False
        scope = build_context(engine, 'CrowdNeedle')['search_scope']
        assert scope['metadata_candidate_count'] == scope['metadata_candidate_limit'] == 20
        assert scope['metadata_match_count'] == 26
        assert scope['metadata_candidates_omitted'] and scope['metadata_omitted_count'] == 6
        assert scope['fulltext_status'] == 'no_matches'
        assert scope['fulltext_scope'] == 'selected_papers'
    assert config.database.read_bytes() == before


@pytest.mark.parametrize('scope', ['all', 'fulltext'])
def test_explicit_filters_never_expand_and_unsearched_differs_from_no_matches(collection, scope):
    _, config = collection
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        def context(**kwargs):
            return build_context(engine, 'CrowdNeedle', scope=scope, **kwargs)
        for options in ({'metadata_query': 'NoSuchCandidate'}, {'citekeys': []},
                        {'citekeys': ['Target'], 'metadata_query': 'BodyDecoy'}):
            result = context(**options)
            assert result['returned'] == 0
            assert result['search_scope']['fulltext_status'] == 'not_searched'
            assert result['search_scope']['fulltext_citekeys'] == []
        no_matches = context(citekeys=['Decoy0'])
        assert no_matches['returned'] == 0
        assert no_matches['search_scope']['fulltext_status'] == 'no_matches'
        assert no_matches['search_scope']['fulltext_scope'] == 'selected_papers'
        selected = context(citekeys=['Target'])
        assert [r['citekey'] for r in selected['results']] == ['Target']
        assert selected['search_scope']['metadata_candidate_count'] == 0
        strict = context(metadata_query='CrowdNeedle')
        assert 'Target' not in [r['citekey'] for r in strict['results']]
        assert strict['search_scope']['fulltext_scope'] == 'selected_papers'
        intersection = context(metadata_query='Target', citekeys=['Target', 'Decoy0'])
        assert [r['citekey'] for r in intersection['results']] == ['Target']


def test_exact_doi_and_citekey_bypass_ranking_and_report_true_population(collection):
    _, config = collection
    with closing(connect(config.database, readonly=True)) as db:
        engine = SQLiteSearch(db)
        for query in ('ExactOnly', '10.9999/exact', 'https://doi.org/10.9999/exact'):
            result = build_context(engine, query)
            assert [r['citekey'] for r in result['results']] == ['ExactOnly']
            assert result['results'][0]['source_type'] == 'metadata'
            assert result['search_scope']['metadata_match_count'] == 1
            assert not result['search_scope']['metadata_candidates_omitted']
        broad = build_context(engine, '10.9999/exact', scope='fulltext')
        assert broad['returned'] == 0 and broad['search_scope']['fulltext_status'] == 'no_matches'


def test_cli_mcp_scope_parity_bounds_and_invalid_scope(collection, capsys):
    config_path, config = collection
    before = config.database.read_bytes()
    args = ['--temp', str(config_path), '--paper', 'context', 'CrowdNeedle',
            '--scope', 'fulltext', '--top', '10', '--max-chars', '10000', '--format', 'json']
    assert cli.main(args) == 0
    cli_result = json.loads(capsys.readouterr().out)
    server = MCPServer(config_path)
    initialize(server)
    mcp_result = tool(server, 'build_context', query='CrowdNeedle', scope='fulltext', top=10,
                      max_chars=10000)
    assert cli_result['search_scope'] == mcp_result['search_scope']
    assert [r['citekey'] for r in mcp_result['results']] == ['Target']
    assert len(mcp_result['context']) <= 10000
    assert server.call_tool('build_context', {'query': 'x', 'scope': 'metadata'})['isError']
    assert server.call_tool('build_context', {'query': 'x', 'scope': True})['isError']
    for maximum in (256, 1000, 100000):
        result = tool(server, 'build_context', query='CrowdNeedle', scope='fulltext', max_chars=maximum)
        assert len(result['context']) <= maximum
        assert max(Counter(r['citekey'] for r in result['results']).values(), default=0) <= 2
    assert config.database.read_bytes() == before


def test_fixed_40_query_evaluation_has_declared_limits_and_preserves_provenance(tmp_path):
    data, digest = load_dataset(DATASET)
    assert len(data['queries']) == 40 and len(digest) == 64
    report = evaluate(data, tmp_path)
    baseline, broad = report['modes']['baseline'], report['modes']['current_fulltext']
    assert baseline['overall'] == report['modes']['current_default']['overall']
    assert baseline['by_category']['beyond_candidate_20']['recall_at_10'] == 0
    assert broad['by_category']['beyond_candidate_20']['recall_at_10'] == 1
    assert broad['by_category']['body_only']['mrr_at_10'] == 1
    assert broad['overall']['correct_empty_queries'] == 5
    assert broad['by_category']['exact_identifiers']['recall_at_10'] == 0
    assert baseline['by_category']['exact_identifiers']['recall_at_10'] == 1
    assert report['source_configuration_index_hashes_unchanged']
    assert broad['citation_checks']['fulltext'] > 0


def test_metrics_use_unique_papers_and_exclude_no_match_from_positive_denominators():
    result = metrics([dict(relevant=['A', 'B'], ranking=['Other', 'Other', 'B']),
                      dict(relevant=[], ranking=[])])
    assert result['recall_at_10'] == .5 and result['mrr_at_10'] == .5
    assert result['correct_empty_queries'] == 1
