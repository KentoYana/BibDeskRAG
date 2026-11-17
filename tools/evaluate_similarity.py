#!/usr/bin/env python3
"""Offline real-model quality evaluation on frozen synthetic paper relationships."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
import gc
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import resource
import socket
import struct
import sys
from tempfile import TemporaryDirectory
import time
import urllib.request

from bibdesk_rag.config import Config
from bibdesk_rag.database import connect
from bibdesk_rag.embeddings import MODEL_FILES, SentenceTransformerBackend, model_is_cached, split_passages
from bibdesk_rag.indexer import index_library
from bibdesk_rag.normalization import normalize_search
from bibdesk_rag.semantic_config import SemanticOptions
from bibdesk_rag.semantic import normalized_fields
from bibdesk_rag.similarity import similar_papers

try:
    from .evaluate_search import metrics as retrieval_metrics
except ImportError:
    from evaluate_search import metrics as retrieval_metrics

DATASET = Path(__file__).resolve().parents[1] / 'tests/fixtures/similarity_evaluation.json'
METHODS = ('lexical_tf_idf', 'saved_vector_centroid_cosine', 'similar_papers_max_pairwise_cosine')


def load_dataset(path):
    with path.open("rb") as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Similarity dataset exceeds 2 MB')
    data = json.loads(raw)
    papers, seeds = data['papers'], data['seeds']
    if data['version'] != 1 or not 2 <= len(papers) <= 500 or not 1 <= len(seeds) <= 100:
        raise ValueError('Unsupported dataset size/version')
    keys = [p['citekey'] for p in papers]
    if len(set(keys)) != len(keys) or any(not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', k) for k in keys):
        raise ValueError('Invalid/duplicate paper identifiers')
    for p in papers:
        if any(not isinstance(p[k], str) or len(p[k]) > 100000 for k in ('title', 'abstract')):
            raise ValueError('Invalid title/abstract')
        if any(not isinstance(p[k], str) or not p[k] or len(p[k]) > 256 for k in ('language','domain','condition')):
            raise ValueError('Invalid stratum label')
        if not (p['title'].strip() or p['abstract'].strip()):
            raise ValueError('Quality cases need embeddable metadata')
    if len({s['citekey'] for s in seeds}) != len(seeds):
        raise ValueError('Duplicate seed cases')
    for seed in seeds:
        if seed['citekey'] not in keys or seed['citekey'] in seed['relevance']:
            raise ValueError('Unknown source or self-relevance judgment')
        if not set(seed['relevance']) <= set(keys) or any(type(v) is not int or v not in (1, 2)
                                                         for v in seed['relevance'].values()):
            raise ValueError('Invalid relevance judgment')
    return data, hashlib.sha256(raw).hexdigest()


def per_query_metrics(ranking, relevance, k=10):
    ranked = list(dict.fromkeys(ranking))[:k]
    positive = {key for key, grade in relevance.items() if grade > 0}
    if not positive:
        return {'recall_at_10': None, 'mrr_at_10': None, 'ndcg_at_10': None}
    dcg = sum((2**relevance.get(key, 0)-1)/math.log2(n+1) for n, key in enumerate(ranked, 1))
    ideal = sum((2**grade-1)/math.log2(n+1)
                for n, grade in enumerate(sorted(relevance.values(), reverse=True)[:k], 1))
    return {'recall_at_10': len(set(ranked) & positive)/len(positive),
            'mrr_at_10': next((1/n for n, key in enumerate(ranked, 1) if key in positive), 0),
            'ndcg_at_10': dcg/ideal}


def aggregate(cases):
    positives = [c for c in cases if c['metrics']['recall_at_10'] is not None]
    controls = [c for c in cases if c['metrics']['recall_at_10'] is None]
    shared = retrieval_metrics([{'relevant': [key for key,grade in c['relevance'].items() if grade > 0], 'ranking': c['ranking']} for c in cases])
    return {'seeds': len(cases), 'positive_seeds': len(positives), 'no_related_controls': len(controls),
            'recall_at_10': shared['recall_at_10'], 'mrr_at_10': shared['mrr_at_10'],
            'ndcg_at_10': sum(c['metrics']['ndcg_at_10'] for c in positives)/len(positives) if positives else None,
            'controls_with_nonempty_results': sum(bool(c['ranking']) for c in controls)}


def _terms(text):
    normalized = normalize_search(text)
    words = re.findall(r'[a-z0-9_]+', normalized)
    for segment in re.findall(r'[\u3040-\u30ff\u3400-\u9fff]+', normalized):
        words.extend(segment[i:i+2] for i in range(max(1, len(segment)-1)))
    return Counter(words)


def lexical_vectors(papers):
    counts = {p['citekey']: _terms(p['title']+' '+p['abstract']) for p in papers}
    df = Counter(term for terms in counts.values() for term in terms)
    vectors = {}
    for key, terms in counts.items():
        values = {term: (1+math.log(count))*(1+math.log((1+len(papers))/(1+df[term])))
                  for term, count in terms.items()}
        norm = math.sqrt(math.fsum(v*v for v in values.values()))
        vectors[key] = {term: value/norm for term, value in values.items()} if norm else {}
    return vectors


def centroid(parts):
    mean = [math.fsum(values)/len(parts) for values in zip(*parts)]
    norm = math.sqrt(math.fsum(x*x for x in mean))
    return [x/norm for x in mean] if norm else mean


@contextmanager
def offline_network_guard():
    def prohibited(*args, **kwargs):
        raise AssertionError('Network access is prohibited during similarity evaluation')
    original_connect, original_connect_ex, original_urlopen = socket.socket.connect, socket.socket.connect_ex, urllib.request.urlopen
    socket.socket.connect = prohibited
    socket.socket.connect_ex = prohibited
    urllib.request.urlopen = prohibited
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, urllib.request.urlopen = original_connect, original_connect_ex, original_urlopen


def materialize(data, root, options, backend):
    def escape(value):
        return value.replace('\\', r'\textbackslash{}').replace('{', r'\{').replace('}', r'\}')
    bib = root/'refs.bib'
    bib.write_text('\n'.join('@article{'+p['citekey']+',title={'+escape(p['title'])+'},abstract={'
                             +escape(p['abstract'])+'}}' for p in data['papers'])+'\n')
    config = Config(bib, root/'derived/index.sqlite3', semantic=options)
    report = index_library(config, backend=backend)
    return config, report


def evaluate_saved(data, config, *, top=10, part_notes=None):
    papers = {p['citekey']: p for p in data['papers']}
    lexical = lexical_vectors(data['papers'])
    with closing(connect(config.database, readonly=True, bib=config.bib)) as db:
        model = json.loads(db.execute('SELECT config_json FROM embedding_models WHERE id='
                                     '(SELECT value FROM settings WHERE key=\'semantic_model_id\')').fetchone()[0])
        rows = db.execute('SELECT p.citekey,e.vector,e.content_hash,p.title,p.abstract FROM papers p '
                          'JOIN embeddings e ON p.id=e.paper_id ORDER BY p.id,e.part').fetchall()
        parts = defaultdict(list)
        for row in rows:
            parts[row['citekey']].append(struct.unpack(f"<{model['dimensions']}f", row['vector']))
    means = {key: centroid(values) for key, values in parts.items()}
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (config.bib, config.database)}
    cases = {method: [] for method in METHODS}
    for case in data['seeds']:
        seed, relevance = case['citekey'], case['relevance']
        source = papers[seed]
        for method in METHODS:
            start = time.perf_counter()
            if method == METHODS[2]:
                result = similar_papers(config, seed, top=top, _policy="legacy")
                assert result['source']['citekey'] == seed
                assert result['source']['title_only'] == (not bool(source['abstract']))
                scored = [(r['citekey'], r['similarity_score']) for r in result['results']]
                assert result['candidates']['missing_vectors'] == 0
                assert result['embedding_model'] == model
                for item in result['results']:
                    assert item['evidence_status'] == 'metadata_similarity_unverified'
                    assert item['title_only'] == (not bool(papers[item['citekey']]['abstract']))
            else:
                scores = {}
                for key in papers:
                    if key == seed:
                        continue
                    if method == METHODS[0]:
                        scores[key] = math.fsum(value*lexical[key].get(term, 0)
                                               for term, value in lexical[seed].items())
                    else:
                        scores[key] = math.fsum(a*b for a,b in zip(means[seed], means[key]))
                scored = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top]
            winning_pair = None
            if method == METHODS[2] and scored:
                target = scored[0][0]
                pairs = [(math.fsum(a*b for a,b in zip(left,right)), i, j)
                         for i,left in enumerate(parts[seed]) for j,right in enumerate(parts[target])]
                score,i,j = max(pairs, key=lambda item:item[0])
                assert abs(max(-1.,min(1.,score))-scored[0][1]) < 1e-6
                winning_pair = {'candidate':target,'source_part':i,'candidate_part':j}
                if part_notes:
                    winning_pair.update(source_note=part_notes[seed][i], candidate_note=part_notes[target][j])
            ranking = [key for key, score in scored]
            assert seed not in ranking and len(ranking) == len(set(ranking)) <= top
            assert all(key in papers and math.isfinite(score) for key, score in scored)
            cases[method].append({'seed': seed, 'language': source['language'], 'domain': source['domain'],
                                  'condition': source['condition'], 'source_parts': len(parts[seed]),
                                  'relevance': relevance, 'ranking': ranking,
                                  'scores': [score for _,score in scored],
                                  'metrics': per_query_metrics(ranking, relevance), 'top1_winning_pair': winning_pair,
                                  'retrieval_ms': (time.perf_counter()-start)*1000})
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    methods = {}
    for method, records in cases.items():
        strata = {}
        for field in ('language', 'condition', 'domain'):
            values = defaultdict(list)
            for case in records:
                values[case[field]].append(case)
            strata[field] = {key: aggregate(rows) for key,rows in values.items()}
        methods[method] = {'overall': aggregate(records), 'strata': strata, 'cases': records}
    return {'retrieval_top': top, 'embedding_model': model, 'paper_parts': {k:len(v) for k,v in parts.items()},
            'methods': methods, 'generated_bib_and_index_unchanged_during_retrieval': True,
            'quality_screen_max_ndcg_ge_lexical': methods[METHODS[2]]['overall']['ndcg_at_10'] >= methods[METHODS[0]]['overall']['ndcg_at_10']}


def _sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DATASET)
    parser.add_argument('--model-cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory; existing evaluation evidence is never overwritten')
    data, digest = load_dataset(args.dataset)
    options = SemanticOptions(enabled=True, cache_dir=args.model_cache.expanduser().resolve(), batch_size=8)
    with offline_network_guard():
        if not model_is_cached(options):
            parser.error('The pinned model is not cached; no model download will be attempted')
        args.output.mkdir(parents=True)
        prereg = {'dataset_sha256': digest, 'analysis': data['predeclared_analysis'],
                  'papers': len(data['papers']), 'seeds': len(data['seeds'])}
        (args.output/'preregistration.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2)+'\n')
        print('Frozen dataset:',digest, flush=True)
        started = time.perf_counter()
        with TemporaryDirectory(prefix='bibdesk-rag-similarity-quality-') as directory:
            root = Path(directory).resolve()
            os.environ['TORCH_HOME'] = str(root/'torch-cache')
            try:
                import torch
            except ImportError:
                parser.error('Real-model evaluation requires the existing semantic extra; nothing will be installed automatically')
            from huggingface_hub import snapshot_download

            snapshot = Path(snapshot_download(options.model, revision=options.revision,
                cache_dir=str(options.cache_dir), local_files_only=True, allow_patterns=MODEL_FILES))
            model_files = {str(path.relative_to(snapshot)): _sha(path)
                           for path in snapshot.rglob('*') if path.is_file() and path.suffix in {'.json','.safetensors','.txt'}}
            torch.set_num_threads(1)
            backend = SentenceTransformerBackend(options)
            config, indexing = materialize(data, root, options, backend)
            print('Real-model indexing:', indexing['semantic'], flush=True)
            part_notes = {}
            with closing(connect(config.database, readonly=True, bib=config.bib)) as db:
                for row in db.execute('SELECT citekey,title,abstract FROM papers'):
                    title,abstract = normalized_fields(row['title'],row['abstract'])
                    texts = split_passages(title,abstract,backend)
                    part_notes[row['citekey']] = [dict(part=i, characters=len(text),
                        abstract_opening_present=bool(abstract and abstract[:80] in text),
                        shared_appendix_present='Synthetic reporting appendix.' in text)
                        for i,text in enumerate(texts)]
            # Queries below call the production saved-vector service, not an encoder.
            del backend
            gc.collect()
            report = evaluate_saved(data, config, part_notes=part_notes)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
        report.update(dataset_sha256=digest, preregistration=prereg,
                      judgment_policy=data['judgment_policy'], indexing=indexing['semantic'],
                      real_model=True, offline_network_guard=True, user_library_read_or_updated=False,
                      python=sys.version.split()[0], operating_system=platform.system(), architecture=platform.machine(),
                      model_file_sha256=model_files,
                      evaluator_sha256=_sha(Path(__file__)),
                      service_sha256=_sha(Path(sys.modules[similar_papers.__module__].__file__)),
                      evaluation_config={'top':10,'torch_threads':1,'index_batch_size':options.batch_size},
                      elapsed_seconds=time.perf_counter()-started, peak_process_rss_mib=rss,
                      memory_scope='Whole evaluation process, including CPU model loading/indexing; not MCP serving RSS.',
                      scope='Controlled authored synthetic metadata; no independent expert or real-library relevance judgments.')
        assert hashlib.sha256(args.dataset.read_bytes()).hexdigest() == digest, 'Frozen dataset changed during evaluation'
        (args.output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({method:r['overall'] for method,r in report['methods'].items()},indent=2),flush=True)
        print('Quality screen:',report['quality_screen_max_ndcg_ge_lexical'],flush=True)


if __name__ == '__main__':
    main()
