"""Evaluation mathematics and frozen judgments; real-model quality is run separately."""
from copy import deepcopy
import json
import math

import pytest

from tools.evaluate_search import metrics as retrieval_metrics
from tools.evaluate_similarity import (
    DATASET, METHODS, aggregate, centroid, evaluate_saved, lexical_vectors,
    load_dataset, offline_network_guard, per_query_metrics,
)
from test_similarity import collection  # noqa: F401


def test_graded_ndcg_recall_and_mrr_are_hand_checked_and_deduplicated():
    ranking = ['wrong', 'B', 'A', 'A']
    relevance = {'A': 2, 'B': 1}
    result = per_query_metrics(ranking, relevance)
    expected = (1/math.log2(3)+3/math.log2(4))/(3+1/math.log2(3))
    assert result == {'recall_at_10': 1, 'mrr_at_10': .5, 'ndcg_at_10': expected}
    assert per_query_metrics(['wrong']*20+['A'], {'A': 2})['recall_at_10'] == 1
    assert per_query_metrics([str(i) for i in range(10)]+['A'], {'A': 2})['recall_at_10'] == 0
    assert all(value is None for value in per_query_metrics(['anything'], {}).values())


def test_no_related_controls_excluded_and_metrics_reuse_issue9_definitions():
    records = [dict(ranking=['wrong','A'], relevance={'A':2}, metrics=per_query_metrics(['wrong','A'],{'A':2})),
               dict(ranking=['B'], relevance={}, metrics=per_query_metrics(['B'],{}))]
    result = aggregate(records)
    shared = retrieval_metrics([dict(ranking=r['ranking'], relevant=list(r['relevance'])) for r in records])
    assert result['recall_at_10'] == shared['recall_at_10'] == 1
    assert result['mrr_at_10'] == shared['mrr_at_10'] == .5
    assert result['no_related_controls'] == result['controls_with_nonempty_results'] == 1


def test_frozen_dataset_design_covers_declared_conditions_and_no_self_judgments():
    data, digest = load_dataset(DATASET)
    assert digest == '47fed5670f3a59a13707945413994c4962e1637dd895ef41e1a6fa62c9b1e68d'
    assert len(data['papers']) == 52 and len(data['seeds']) == 40
    by_key = {p['citekey']:p for p in data['papers']}
    assert sum(not s['relevance'] for s in data['seeds']) == 4
    assert sum(by_key[s['citekey']]['condition']=='long_abstract' for s in data['seeds']) == 8
    assert sum(by_key[s['citekey']]['condition']=='title_only' for s in data['seeds']) == 8
    assert {by_key[s['citekey']]['language'] for s in data['seeds']} == {'en','ja'}
    for case in data['seeds']:
        assert case['citekey'] not in case['relevance']
        for key,grade in case['relevance'].items():
            assert by_key[key]['domain'] == by_key[case['citekey']]['domain']
            assert grade == (2 if by_key[key]['subtopic'] == by_key[case['citekey']]['subtopic'] else 1)


@pytest.mark.parametrize('mutation', ['self', 'unknown', 'boolean', 'duplicate'])
def test_invalid_judgments_are_refused_before_model_loading(tmp_path, mutation):
    data,_ = load_dataset(DATASET)
    data=deepcopy(data)
    case=data['seeds'][0]
    if mutation=='self':
        case['relevance'][case['citekey']]=2
    elif mutation=='unknown':
        case['relevance']['unknown']=2
    elif mutation=='boolean':
        case['relevance'][next(iter(case['relevance']))]=True
    else:
        data['seeds'].append(deepcopy(case))
    path=tmp_path/'bad.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_dataset(path)


def test_lexical_and_centroid_baselines_have_defined_zero_and_normalized_behavior():
    assert centroid([(1.,0.),(0.,1.)]) == pytest.approx([math.sqrt(.5),math.sqrt(.5)])
    assert centroid([(1.,0.),(-1.,0.)]) == [0.,0.]
    papers=[dict(citekey='A',title='DNA 修復',abstract=''),dict(citekey='B',title='DNA 修復',abstract='')]
    vectors=lexical_vectors(papers)
    assert vectors['A'] == vectors['B']
    assert sum(v*v for v in vectors['A'].values()) == pytest.approx(1)


def test_quality_harness_uses_actual_saved_service_and_preserves_generated_sources(collection):  # noqa: F811
    _,config=collection
    data={'papers':[
        dict(citekey=key,title=title,abstract=abstract,language='en',condition='fixture',domain='fixture')
        for key,title,abstract in [('Seed','Repair seed','Repair source abstract'),
                                   ('Zulu','Repair candidate','Repair candidate abstract'),
                                   ('Alpha','Title only candidate',''),('Other','Other topic','Other subject')]],
          'seeds':[dict(citekey='Seed',relevance={'Alpha':2,'Zulu':1})]}
    # The fixture deliberately contains two unembedded records outside this quality corpus.
    from contextlib import closing
    from bibdesk_rag.database import connect
    with closing(connect(config.database)) as db,db:
        db.execute("DELETE FROM papers WHERE citekey IN ('Missing','Empty')")
    report=evaluate_saved(data,config)
    assert report['generated_bib_and_index_unchanged_during_retrieval']
    assert report['methods'][METHODS[2]]['cases'][0]['ranking'] == ['Alpha','Zulu','Other']
    assert report['methods'][METHODS[2]]['overall']['ndcg_at_10'] == 1


def test_offline_guard_rejects_network_and_restores_functions():
    import socket
    original=socket.socket.connect
    with offline_network_guard():
        with socket.socket() as sock, pytest.raises(AssertionError,match='Network access'):
            sock.connect(('127.0.0.1',9))
    assert socket.socket.connect is original


def test_recorded_real_model_report_is_consistent_with_frozen_judgments_and_metrics():
    from pathlib import Path
    data,digest=load_dataset(DATASET)
    report=json.loads((Path(__file__).parents[1]/'docs/similarity-evaluation-results.json').read_text())
    assert report['real_model'] and report['offline_network_guard']
    assert report['dataset_sha256']==digest
    assert report['indexing']['embedded']==52 and report['indexing']['parts']==68
    assert report['reproducibility']['independent_cpu_runs']==3
    judgments={s['citekey']:s['relevance'] for s in data['seeds']}
    for method,results in report['methods'].items():
        assert len(results['cases'])==40
        for case in results['cases']:
            assert case['relevance']==judgments[case['seed']]
            assert case['seed'] not in case['ranking']
            expected = per_query_metrics(case['ranking'],case['relevance'])
            for metric,value in expected.items():
                if value is None:
                    assert case['metrics'][metric] is None
                else:
                    assert case['metrics'][metric]==pytest.approx(value,rel=1e-12,abs=1e-12)
        assert results['overall']==pytest.approx(aggregate(results['cases']),rel=1e-12,abs=1e-12)
    long=[c for c in report['methods'][METHODS[2]]['cases'] if c['condition']=='long_abstract']
    assert len(long)==8
    assert all(c['relevance'].get(c['ranking'][0],0)==0 for c in long)
    assert all(c['top1_winning_pair']['source_part']==1 for c in long)
