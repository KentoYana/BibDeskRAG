#!/usr/bin/env python3
"""Offline 40-query generated-corpus evaluation; never reads a user's library."""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time
import zipfile

from bibdesk_rag.config import init_config, load_config
from bibdesk_rag.context import build_context
from bibdesk_rag.database import connect
from bibdesk_rag.indexer import index_library
from bibdesk_rag.search import SQLiteSearch

try:
    from .package_smoke import synthetic_pdf
except ImportError:
    from package_smoke import synthetic_pdf

DATASET = Path(__file__).resolve().parents[1] / 'tests/fixtures/search_evaluation.json'


def load_dataset(path):
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError('Evaluation dataset exceeds 2 MB')
    data = json.loads(raw)
    papers, queries = data['papers'], data['queries']
    if data['version'] != 1 or not 1 <= len(papers) <= 1000 or not 30 <= len(queries) <= 50:
        raise ValueError('Unsupported evaluation dataset size/version')
    keys = [p['citekey'] for p in papers]
    if len(set(keys)) != len(keys) or any(not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', k) for k in keys):
        raise ValueError('Invalid/duplicate evaluation citekeys')
    for paper in papers:
        if paper['format'] not in (None, 'pdf', 'csv', 'zip_csv'):
            raise ValueError('Unknown generated attachment format')
        if any(not isinstance(paper[k], str) or len(paper[k]) > 2000 for k in ('title', 'doi')):
            raise ValueError('Invalid generated metadata')
        if paper['body'] is not None and (not isinstance(paper['body'], str) or len(paper['body']) > 20000):
            raise ValueError('Invalid generated body')
    if len({q['id'] for q in queries}) != len(queries):
        raise ValueError('Duplicate query IDs')
    for query in queries:
        if not isinstance(query['query'], str) or len(query['query']) > 2000:
            raise ValueError('Invalid evaluation query')
        if not set(query['relevance']) <= set(keys) or any(type(v) is not int or v not in (0, 1, 2)
                                                         for v in query['relevance'].values()):
            raise ValueError('Invalid relevance judgments')
    return data, hashlib.sha256(raw).hexdigest()


def materialize(data, root):
    """Only generated filenames and literal CSV/PDF content, never source instructions."""
    directory = root / 'sources'
    directory.mkdir()
    manifest, entries = {}, []

    def field(value):
        return value.replace('\\', r'\textbackslash{}').replace('{', r'\{').replace('}', r'\}')

    for index, paper in enumerate(data['papers']):
        attachment = ''
        if paper['body'] is not None:
            suffix = '.pdf' if paper['format'] == 'pdf' else '.zip' if paper['format'] == 'zip_csv' else '.csv'
            path = directory / f'p{index:04}{suffix}'
            rows = [['marker', 'observation'], [paper['body'], 'synthetic']]
            if suffix == '.pdf':
                path.write_bytes(synthetic_pdf(paper['body']))
            else:
                stream = io.StringIO(newline='')
                csv.writer(stream).writerows(rows)
                if suffix == '.zip':
                    with zipfile.ZipFile(path, 'w') as archive:
                        archive.writestr('tables/evidence.csv', stream.getvalue())
                else:
                    path.write_text(stream.getvalue())
            manifest[str(path)] = {**paper, 'rows': rows}
            attachment = ',Bdsk-File-1={' + str(path.relative_to(root)) + '}'
        entries.append('@article{' + paper['citekey'] + ',title={' + field(paper['title'])
                       + '},doi={' + field(paper['doi']) + '}' + attachment + '}')
    bib = root / 'refs.bib'
    bib.write_text('\n'.join(entries) + '\n')
    config_path = init_config(bib, root / 'settings/config.toml', root / 'derived')
    config = load_config(config_path)
    index_library(config)
    return config_path, config, manifest


def ranking(result):
    return list(dict.fromkeys(item['citekey'] for item in result['results']))[:10]


def metrics(records):
    records = [{**r, 'ranking': list(dict.fromkeys(r['ranking']))[:10]} for r in records]
    positive = [r for r in records if r['relevant']]
    negative = [r for r in records if not r['relevant']]
    return {
        'queries': len(records), 'positive_queries': len(positive), 'negative_queries': len(negative),
        'recall_at_10': (sum(len(set(r['ranking']) & set(r['relevant'])) / len(r['relevant'])
                             for r in positive) / len(positive)) if positive else None,
        'mrr_at_10': (sum(next((1 / n for n, key in enumerate(r['ranking'], 1)
                                if key in r['relevant']), 0) for r in positive) / len(positive)) if positive else None,
        'correct_empty_queries': sum(not r['ranking'] for r in negative),
    }


def check_citations(result, engine, manifest, papers):
    counts = {'fulltext': 0, 'metadata_only': 0}
    for item in result['results']:
        assert item['citekey'] in papers
        assert item['doi'] == papers[item['citekey']]['doi']
        if item['chunk_id'] is None:
            counts['metadata_only'] += 1
            continue
        chunk = engine.get_chunk(item['chunk_id'], max_chars=20000)
        assert item['text'] == chunk['text'][:len(item['text'])]
        assert any(c['citekey'] == item['citekey'] for c in chunk['citations'])
        for name in ('file_path', 'content_hash', 'page_start', 'page_end', 'sheet_name',
                     'row_start', 'row_end', 'member_path'):
            assert item.get(name) == chunk.get(name), name
        source = manifest[item['file_path']]
        assert source['citekey'] == item['citekey']
        assert hashlib.sha256(Path(item['file_path']).read_bytes()).hexdigest() == item['content_hash']
        if source['format'] == 'pdf':
            assert item['page_start'] == item['page_end'] == 2
            assert item['text'] in source['body']
        else:
            assert item['row_start'] == item['row_end'] == 2
            assert item['member_path'] == ('tables/evidence.csv' if source['format'] == 'zip_csv' else None)
            for cell in item['table_provenance']['cells']:
                original = source['rows'][cell['row'] - 1][cell['column'] - 1]
                assert item['text'][cell['text_start']:cell['text_end']] == original[cell['cell_start']:cell['cell_end']]
        counts['fulltext'] += 1
    return counts


def evaluate(data, root, *, baseline_python=None):
    config_path, config, manifest = materialize(data, root)
    paths = [config_path, config.bib, config.database, *(Path(p) for p in manifest)]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    modes = ('baseline', 'current_default', 'current_fulltext')
    records = {mode: [] for mode in modes}
    citations = {mode: {'fulltext': 0, 'metadata_only': 0} for mode in modes}
    paper_map = {p['citekey']: p for p in data['papers']}
    env = os.environ.copy()
    for name in ('BIBDESK_RAG_CONFIG', 'BIBDESK_RAG_HOME', 'PYTHONPATH', 'PYTHONHOME', 'PYENV_VERSION'):
        env.pop(name, None)
    with closing(connect(config.database, readonly=True, bib=config.bib)) as db:
        engine = SQLiteSearch(db)
        for query in data['queries']:
            relevant = [k for k, grade in query['relevance'].items() if grade > 0]
            for mode in modes:
                start = time.perf_counter()
                if mode == 'baseline' and baseline_python:
                    output = subprocess.run(
                        [str(baseline_python), '-m', 'bibdesk_rag.cli', '--temp', str(config_path),
                         '--paper', 'context', query['query'], '--top', '10', '--max-chars', '100000',
                         '--format', 'json'], cwd=root, env=env, text=True, capture_output=True,
                        check=True, timeout=30).stdout
                    result = json.loads(output)
                else:
                    result = build_context(engine, query['query'], top=10, max_chars=100000,
                                           scope='fulltext' if mode == 'current_fulltext' else 'all')
                elapsed = (time.perf_counter() - start) * 1000
                assert len(result['context']) <= 100000 and len(result['results']) <= 10
                checked = check_citations(result, engine, manifest, paper_map)
                for name, count in checked.items():
                    citations[mode][name] += count
                records[mode].append(dict(id=query['id'], category=query['category'],
                                          relevant=relevant, ranking=ranking(result),
                                          elapsed_ms=round(elapsed, 3),
                                          search_scope=result.get('search_scope')))
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    grouped = {}
    for mode in modes:
        categories = defaultdict(list)
        for record in records[mode]:
            categories[record['category']].append(record)
        grouped[mode] = {'overall': metrics(records[mode]),
                         'by_category': {key: metrics(rows) for key, rows in categories.items()},
                         'citation_checks': citations[mode], 'cases': records[mode]}
    assert [r['ranking'] for r in records['baseline']] == [r['ranking'] for r in records['current_default']]
    return {'corpus_papers': len(paper_map), 'queries': len(data['queries']),
            'baseline': str(baseline_python) if baseline_python else 'current unchanged two-stage path',
            'baseline_process_startup_in_timing': bool(baseline_python),
            'source_configuration_index_hashes_unchanged': True,
            'scope': 'Synthetic lexical retrieval only; not real-library or semantic-model quality.',
            'modes': grouped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DATASET)
    parser.add_argument('--baseline-python', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.output.resolve() == args.dataset.resolve() or args.output.is_symlink()
            or (args.output.exists() and args.output.samefile(args.dataset))):
        parser.error('Refusing to overwrite the evaluation dataset')
    data, sha = load_dataset(args.dataset)
    with TemporaryDirectory(prefix='bibdesk-rag-eval-') as directory:
        report = evaluate(data, Path(directory).resolve(),
                          baseline_python=args.baseline_python.absolute() if args.baseline_python else None)
    report.update(dataset_sha256=sha, relevance_policy=data['relevance_policy'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({mode: result['overall'] for mode, result in report['modes'].items()}, indent=2))


if __name__ == '__main__':
    main()
