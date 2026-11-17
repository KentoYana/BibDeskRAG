#!/usr/bin/env python3
"""Evaluate the frozen title-anchor policy against legacy and lexical baselines offline."""
from collections import defaultdict
from contextlib import closing
import argparse
import hashlib
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory

from bibdesk_rag.database import connect
from bibdesk_rag.embeddings import SentenceTransformerBackend, model_is_cached
from bibdesk_rag.semantic_config import SemanticOptions
from bibdesk_rag.similarity import similar_papers
from bibdesk_rag import similarity_ranking
try:
    from .evaluate_similarity import load_dataset, materialize, offline_network_guard, lexical_vectors, per_query_metrics, aggregate
except ImportError:
    from evaluate_similarity import load_dataset, materialize, offline_network_guard, lexical_vectors, per_query_metrics, aggregate

ROOT = Path(__file__).resolve().parents[1]


def evaluate(data, config):
    papers = {p['citekey']:p for p in data['papers']}
    lexical = lexical_vectors(data['papers'])
    parts = defaultdict(list)
    with closing(connect(config.database, readonly=True, bib=config.bib)) as db:
        model = json.loads(db.execute('SELECT config_json FROM embedding_models WHERE id='
                                     '(SELECT value FROM settings WHERE key=\'semantic_model_id\')').fetchone()[0])
        for row in db.execute('SELECT p.citekey,e.vector FROM papers p JOIN embeddings e ON p.id=e.paper_id ORDER BY p.id,e.part'):
            parts[row[0]].append(struct.unpack(f"<{model['dimensions']}f",row[1]))
    # The dataset titles each fit one anchor. Remove the newly added anchor to
    # reconstruct the original passage-max algorithm on identical saved values.
    legacy = {key:(vectors[1:] if papers[key]['abstract'] else vectors) for key,vectors in parts.items()}
    methods = defaultdict(list)
    digests = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (config.bib,config.database)}
    for seed in data['seeds']:
        key = seed['citekey']
        response = similar_papers(config,key)
        repeat = similar_papers(config,key)
        assert response == repeat
        scores = {
            'legacy_max':{k:max(similarity_ranking.dot(a,b) for a in legacy[key] for b in legacy[k]) for k in papers if k!=key},
            'lexical_tf_idf':{k:sum(v*lexical[k].get(t,0) for t,v in lexical[key].items()) for k in papers if k!=key}}
        rankings = {method:sorted(values,key=lambda k:(-values[k],k))[:10] for method,values in scores.items()}
        rankings['title_anchor_hybrid'] = [r['citekey'] for r in response['results']]
        for method,rank in rankings.items():
            methods[method].append({**seed, **{k:papers[key][k] for k in ('condition','language','domain')},
                                    'ranking':rank, 'metrics':per_query_metrics(rank,seed['relevance']),
                                    'assessment':response['assessment'] if method=='title_anchor_hybrid' else None})
    assert digests == {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in digests}
    result = {}
    for method,cases in methods.items():
        strata = {}
        for field in ('condition','language'):
            strata[field] = {v:aggregate([c for c in cases if c[field]==v]) for v in sorted({c[field] for c in cases})}
        positives = [c for c in cases if c['relevance']]
        result[method] = {'overall':aggregate(cases), 'strata':strata,
                          'positive_query_coverage':sum(bool(c['ranking']) for c in positives)/len(positives),
                          'long_wrong_top1':sum(c['condition']=='long_abstract' and bool(c['ranking']) and
                                               c['ranking'][0] not in c['relevance'] for c in cases), 'cases':cases}
    return {'methods':result, 'embedding_model':model, 'generated_source_and_index_unchanged':True,
            'repeat_saved_queries_identical':True, 'source_sha256':digests}


def gates(report, criteria):
    new,old,lex = [report['methods'][k] for k in ('title_anchor_hybrid','legacy_max','lexical_tf_idf')]
    return {'long_wrong_top1':new['long_wrong_top1']<=criteria['long_top1_wrong_max'],
            'positive_query_coverage':new['positive_query_coverage']>=criteria['positive_query_coverage_min'],
            'no_related_abstention':new['overall']['no_related_controls']-new['overall']['controls_with_nonempty_results']>=criteria['no_related_abstention_required'],
            'ndcg_ge_legacy':new['overall']['ndcg_at_10']>=old['overall']['ndcg_at_10'],
            'title_only_ge_lexical':new['strata']['condition']['title_only']['ndcg_at_10']>=lex['strata']['condition']['title_only']['ndcg_at_10'],
            'recall_retained':new['overall']['recall_at_10']>=old['overall']['recall_at_10']-criteria['recall_drop_vs_legacy_max'],
            'japanese_retained':new['strata']['language']['ja']['ndcg_at_10']>=old['strata']['language']['ja']['ndcg_at_10']-criteria['japanese_ndcg_drop_vs_legacy_max']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory')
    prereg = json.loads((ROOT/'tests/fixtures/similarity_improvement_preregistration.json').read_text())
    options=SemanticOptions(enabled=True,cache_dir=args.model_cache,batch_size=8)
    frozen = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        ROOT/'src/bibdesk_rag/similarity.py',ROOT/'src/bibdesk_rag/similarity_ranking.py',ROOT/'src/bibdesk_rag/embeddings.py')}
    args.output.mkdir(parents=True)
    (args.output/'frozen-policy.json').write_text(json.dumps({'source_sha256':frozen,'profile':similarity_ranking.PROFILE,
        'selection':'Development only: title anchor required; 0 lexical for abstract sources, 0.5 for title-only. Gate uses anchor cosine background.',
        'preregistration':prereg},indent=2)+'\n')
    reports = {}
    with offline_network_guard():
        if not model_is_cached(options):
            parser.error('Pinned model not cached; no download attempted')
        import torch
        torch.set_num_threads(1)
        backend=SentenceTransformerBackend(options)
        for split,filename,expected in (('development','similarity_evaluation.json',prereg['development_sha256']),
                                        ('holdout','similarity_holdout.json',prereg['holdout_sha256'])):
            data,digest=load_dataset(ROOT/'tests/fixtures'/filename)
            assert digest==expected
            with TemporaryDirectory(prefix='bibdesk-rag-improvements-') as directory:
                config,indexing=materialize(data,Path(directory).resolve(),options,backend)
                report=evaluate(data,config)
            report.update(dataset_sha256=digest,indexing=indexing['semantic'])
            report['gates']=gates(report,prereg['criteria'])
            reports[split]=report
            print(split,json.dumps({k:v['overall'] for k,v in report['methods'].items()}),flush=True)
            print('gates',report['gates'],flush=True)
    result={'policy':similarity_ranking.POLICY,'profile':similarity_ranking.PROFILE,'preregistration':prereg,
            'frozen_source_sha256':frozen,'real_model':True,'offline_network_guard':True,
            'user_library_read_or_updated':False,'scope':'Authored synthetic metadata; no independent expert judgments or real-library evaluation.',
            'reports':reports}
    (args.output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    main()
