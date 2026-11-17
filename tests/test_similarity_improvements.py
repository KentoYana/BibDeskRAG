"""Generated mechanics tests and independently recomputed recorded quality metrics."""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import math

import pytest

from bibdesk_rag import similarity_ranking as ranking
from bibdesk_rag.database import connect
from bibdesk_rag.embeddings import embedding_passages, ModelInfo
from bibdesk_rag.semantic import content_hash
from bibdesk_rag.similarity import similar_papers, SimilarPapersError
from test_similarity import collection  # noqa: F401
from tools.evaluate_similarity import load_dataset, aggregate, per_query_metrics
from tools.evaluate_similarity_improvements import gates

ROOT = Path(__file__).resolve().parents[1]


def test_title_anchor_retains_all_original_passages_and_token_bounds():
    class Backend:
        info = ModelInfo('fixture','1',4,'passage: ','query: ',60,'fixture')
        def count_tokens(self,text):
            return len(text)
    backend = Backend()
    title,abstract = 'A long title '*10,'Original abstract '*20
    parts = embedding_passages(title,abstract,backend)
    from bibdesk_rag.embeddings import split_passages
    anchors = split_passages(title,'',backend)
    assert parts[:len(anchors)] == anchors
    assert parts[len(anchors):] == split_passages(title,abstract,backend)
    assert all(backend.count_tokens('passage: '+p)<=60 for p in parts)
    assert embedding_passages(title,'',backend)==anchors


def test_boilerplate_cannot_win_over_independent_title_anchor():
    papers = [{'citekey':k,'title':k,'abstract':'different abstract'} for k in ['Seed','Related','Boilerplate']]
    vectors = {'Seed':[(1.,0.,0.),(0.,0.,1.),(0.,0.,1.)],
               'Related':[(1.,0.,0.),(0.,1.,0.)],
               'Boilerplate':[(0.,1.,0.),(0.,0.,1.),(0.,0.,1.)]}
    scores,cosines,_,decision = ranking.rank('Seed',papers,vectors)
    assert scores['Related'] > scores['Boilerplate']
    assert cosines == {'Boilerplate':0.,'Related':1.}
    assert decision['decision']=='insufficient_evidence'  # small background cannot be calibrated


def test_rejection_and_lexical_support_do_not_treat_high_raw_cosine_as_confidence():
    papers = [{'citekey':str(i),'title':f'unique{i}','abstract':''} for i in range(12)]
    vectors = {str(i):[(1.,0.)] for i in range(12)}
    _,_,_,assessment = ranking.rank('0',papers,vectors)
    assert assessment['background_median_cosine']==1.
    assert assessment['decision']=='insufficient_evidence'
    papers[1]['title']=papers[0]['title']
    _,_,_,assessment = ranking.rank('0',papers,vectors)
    assert assessment['decision']=='candidates'


def test_profile_is_scoped_to_pinned_model():
    from bibdesk_rag.semantic_config import SemanticOptions
    options = SemanticOptions()
    info = {key:getattr(options,key) for key in ('model','revision','dimensions','passage_prefix','query_prefix','max_tokens')}
    info['backend']='sentence-transformers/5.7.0;transformers/5.22.1;torch/2.15.0'
    assert ranking.supported(info)
    for key in ('revision','dimensions','passage_prefix','max_tokens','backend'):
        assert not ranking.supported({**info,key:'other'})


def test_calibrated_service_uses_full_background_before_filters_and_checks_staleness(collection, monkeypatch):  # noqa: F811
    _,config=collection
    monkeypatch.setattr(ranking,'supported',lambda info:True)
    initial=similar_papers(config,'Seed')
    assert initial['assessment']['reason']=='small_background' and initial['results']==[]
    with closing(connect(config.database)) as db,db:
        for n in range(12):
            paper=dict(db.execute("SELECT * FROM papers WHERE citekey='Seed'").fetchone())
            paper.pop('id')
            paper.update(citekey=f'Extra{n}',title='Unrelated',abstract='')
            db.execute('INSERT INTO papers('+','.join(paper)+') VALUES ('+','.join('?' for _ in paper)+')',list(paper.values()))
            pid=db.execute('SELECT id FROM papers WHERE citekey=?',(f'Extra{n}',)).fetchone()[0]
            db.execute('INSERT INTO embeddings(paper_id,part,model_id,content_hash,vector,embedded_at,title_only) '
                       'SELECT ?,0,model_id,?,vector,embedded_at,1 FROM embeddings WHERE paper_id='
                       '(SELECT id FROM papers WHERE citekey=\'Alpha\')', (pid,content_hash('Unrelated','')))
    full=similar_papers(config,'Seed')
    filtered=similar_papers(config,'Seed',citekeys=['Zulu'],top=1)
    assert full['assessment']==filtered['assessment']
    assert full['assessment']['calibrated']
    assert all('ranking_score' in r and 'lexical_score' in r for r in full['results'])
    with closing(connect(config.database)) as db,db:
        db.execute("UPDATE embeddings SET content_hash='stale' WHERE paper_id=(SELECT id FROM papers WHERE citekey='Extra0')")
    with pytest.raises(SimilarPapersError,match='stale'):
        similar_papers(config,'Seed',citekeys=['Zulu'])


def test_recorded_evaluation_is_recomputable_and_all_preregistered_holdout_gates_pass():
    report=json.loads((ROOT/'docs/similarity-improvement-results.json').read_text())
    for split,filename in [('development','similarity_evaluation.json'),('holdout','similarity_holdout.json')]:
        data,digest=load_dataset(ROOT/'tests/fixtures'/filename)
        stored=report['reports'][split]
        assert digest==stored['dataset_sha256']
        for method in stored['methods'].values():
            for case in method['cases']:
                expected = per_query_metrics(case['ranking'],case['relevance'])
                for metric,value in expected.items():
                    if value is None:
                        assert case['metrics'][metric] is None
                    else:
                        assert case['metrics'][metric]==pytest.approx(value,rel=1e-12,abs=1e-12)
                assert case['citekey'] in {s['citekey'] for s in data['seeds']}
            assert aggregate(method['cases'])==pytest.approx(method['overall'],rel=1e-12,abs=1e-12)
        assert gates(stored,report['preregistration']['criteria'])==stored['gates']
        assert all(stored['gates'].values())
    assert report['reports']['holdout']['methods']['title_anchor_hybrid']['long_wrong_top1']==0
    assert report['real_model'] and report['offline_network_guard'] and not report['user_library_read_or_updated']
    assert math.isfinite(report['reports']['holdout']['methods']['title_anchor_hybrid']['overall']['ndcg_at_10'])
    assert hashlib.sha256((ROOT/'tests/fixtures/similarity_holdout.json').read_bytes()).hexdigest()==report['preregistration']['holdout_sha256']
