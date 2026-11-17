"""Read-only paper-to-paper similarity from saved passage vectors; no inference."""
from __future__ import annotations

from contextlib import closing, nullcontext
from itertools import groupby
import heapq
import json
import math
import struct

from .bibdesk import normalize_doi
from .config import Config
from .database import connect, index_state, read_snapshot
from .embeddings import ModelInfo
from . import similarity_ranking
from .semantic import active_model, content_hash, has_paper_vectors, normalized_fields


class SimilarPapersError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise SimilarPapersError(code, message)


def validate_arguments(citekey, top, year, author, citekeys, doi=None):
    if not isinstance(citekey, str) or not 1 <= len(citekey) <= 512 or '\x00' in citekey:
        raise ValueError('citekey must contain 1..512 characters')
    if type(top) is not int or not 1 <= top <= 100:
        raise ValueError('top must be between 1 and 100')
    for name, value, maximum in (('year', year, 32), ('author', author, 512), ('doi', doi, 512)):
        if value is not None and (not isinstance(value, str) or len(value) > maximum or '\x00' in value):
            raise ValueError(f'{name} must be a string of at most {maximum} characters')
    if citekeys is not None and (not isinstance(citekeys, list) or len(citekeys) > 100 or any(
        not isinstance(k, str) or not 1 <= len(k) <= 512 or '\x00' in k for k in citekeys
    )):
        raise ValueError('citekeys must contain at most 100 nonempty strings of at most 512 characters')


def _model(db, config):
    if not has_paper_vectors(db):
        _fail('semantic_index_missing', 'Saved paper vectors are unavailable. Run --index update.')
    try:
        model = active_model(db)
        info = json.loads(model['config_json']) if model else None
    except (ValueError, TypeError) as exc:
        _fail('model_mismatch', str(exc))
    if not model:
        _fail('semantic_index_missing', 'The semantic index has not been built. Run --index update.')
    if not isinstance(info, dict) or any(info.get(key) != model[column] for key, column in (
        ('model', 'name'), ('revision', 'version'), ('dimensions', 'dimensions')
    )):
        _fail('model_mismatch', 'Saved embedding model metadata is inconsistent. Run --index rebuild.')
    if any(info.get(key) != getattr(config.semantic, key) for key in (
        'model', 'revision', 'dimensions', 'passage_prefix', 'query_prefix', 'max_tokens'
    )) or info.get('preprocessing') != ModelInfo.__dataclass_fields__['preprocessing'].default:
        _fail('model_mismatch', 'Semantic settings/preprocessing changed. Run --index update.')
    if not isinstance(info.get('backend'), str) or not info['backend']:
        _fail('model_mismatch', 'Saved embedding backend identity is missing. Run --index rebuild.')
    return model, info


def _vectors(rows, paper, model):
    values = []
    expected = content_hash(paper['title'], paper['abstract'])
    title, abstract = normalized_fields(paper['title'], paper['abstract'])
    if not title and not abstract:
        _fail('invalid_vectors', 'Vectors exist for empty metadata. Run --index rebuild.')
    for part, row in enumerate(rows):
        if row['model_id'] != model['id']:
            _fail('model_mismatch', 'Selected paper vectors use different or inactive models. Run --index update.')
        if row['content_hash'] != expected:
            _fail('stale_vectors', 'Selected title/abstract vectors are stale. Run --index update.')
        if row['part'] != part or bool(row['title_only']) != (not bool(abstract)):
            _fail('invalid_vectors', 'Saved paper vector parts/metadata are inconsistent. Run --index rebuild.')
        if not isinstance(row['vector'], bytes) or len(row['vector']) != model['dimensions'] * 4:
            _fail('invalid_vectors', 'Saved vector dimensions are inconsistent. Run --index rebuild.')
        vector = struct.unpack(f"<{model['dimensions']}f", row['vector'])
        if not all(math.isfinite(x) for x in vector) or abs(math.fsum(x*x for x in vector) - 1) > 2e-4:
            _fail('invalid_vectors', 'Saved vectors are non-finite or unnormalized. Run --index rebuild.')
        values.append(vector)
    return values


def _paper(paper, rows):
    title, abstract = normalized_fields(paper['title'], paper['abstract'])
    data = {key: paper[key] for key in ('citekey', 'title', 'abstract', 'author', 'year', 'journal', 'doi')}
    data.update(title_only=not bool(abstract), has_abstract=bool(abstract),
                indexed_fields=[k for k, value in (('title', title), ('abstract', abstract)) if value],
                embedding_parts=len(rows), embedded_at=rows[0]['embedded_at'])
    return data


def similar_papers(config: Config, citekey: str, top: int = 10, *, year=None, author=None,
                   citekeys=None, doi=None, _db=None, _policy=None) -> dict:
    """Rank saved metadata vectors; evaluated E5 profiles can abstain."""
    validate_arguments(citekey, top, year, author, citekeys, doi)
    if not config.semantic.enabled:
        _fail('semantic_disabled', 'Semantic search is disabled. Use --setup to enable it.')
    if not config.database.is_file():
        _fail('index_missing', 'Index missing. Run --index update first.')
    connection = (closing(connect(config.database, readonly=True, bib=config.bib))
                  if _db is None else nullcontext(_db))
    with connection as db, read_snapshot(db):
        seed = db.execute('SELECT * FROM papers WHERE citekey=?', (citekey,)).fetchone()
        if seed is None:
            _fail('unknown_citekey', 'The source citekey is not in this indexed library.')
        model, info = _model(db, config)
        source_rows = db.execute('SELECT * FROM embeddings WHERE paper_id=? ORDER BY part,id',
                                 (seed['id'],)).fetchall()
        if not source_rows:
            _fail('paper_vectors_missing', 'This paper has no saved title/abstract vectors. Run --index update.')
        source_vectors = _vectors(source_rows, seed, model)
        if _policy != 'legacy' and similarity_ranking.supported(info):
            return _rank_anchored(db, config, seed, source_rows, model, info, top,
                                  year=year, author=author, citekeys=citekeys, doi=doi)
        clauses, arguments = ['p.id<>?'], [seed['id']]
        if year is not None:
            clauses.append('p.year=?')
            arguments.append(year)
        if author is not None:
            clauses.append('instr(lower(p.author),lower(?))>0')
            arguments.append(author)
        if doi is not None:
            clauses.append('p.doi=?')
            arguments.append(normalize_doi(doi))
        if citekeys is not None:
            clauses.append('p.citekey IN (' + ','.join('?' for _ in citekeys) + ')' if citekeys else '0')
            arguments.extend(citekeys)
        where = ' AND '.join(clauses)
        summary = dict(total=db.execute('SELECT count(*) FROM papers p WHERE '+where, arguments).fetchone()[0],
                       indexed=0, missing_vectors=0, empty_metadata=0)
        rows = db.execute('SELECT p.*,e.id AS vector_id,e.model_id,e.vector,e.part,e.title_only,'
                          'e.content_hash,e.embedded_at FROM papers p LEFT JOIN embeddings e '
                          'ON e.paper_id=p.id WHERE '+where+' ORDER BY p.id,e.part,e.id', arguments)
        def matches():
            for _, group in groupby(rows, key=lambda r: r['id']):
                group = list(group)
                paper = group[0]
                if paper['vector_id'] is None:
                    summary['missing_vectors'] += 1
                    summary['empty_metadata'] += not any(normalized_fields(paper['title'], paper['abstract']))
                    continue
                vectors = _vectors(group, paper, model)
                score = max(math.fsum(a*b for a,b in zip(left, right))
                            for left in source_vectors for right in vectors)
                summary['indexed'] += 1
                yield {**_paper(paper, group), 'similarity_score': max(-1., min(1., score)),
                               'evidence_status': 'metadata_similarity_unverified'}

        try:
            scored = heapq.nsmallest(top, matches(), key=lambda item: (-item["similarity_score"], item["citekey"]))
        finally:
            rows.close()
        return {'source': _paper(seed, source_rows), 'results': scored[:top],
                'embedding_model': info, 'index': index_state(db),
                'filters': {'year': year, 'author': author, 'doi': doi, 'citekeys': citekeys},
                'assessment': {'decision':'uncalibrated_candidates', 'calibrated':False},
                'candidates': summary, 'ranking': 'max_pairwise_passage_cosine; ties=citekey',
                'evidence_status': 'metadata_similarity_unverified'}


def _rank_anchored(db, config, seed, source_rows, model, info, top, **filters):
    rows = db.execute('SELECT * FROM papers ORDER BY id').fetchall()
    vectors, items = {}, {}
    for paper in rows:
        saved = db.execute('SELECT * FROM embeddings WHERE paper_id=? ORDER BY part,id',
                           (paper['id'],)).fetchall()
        if saved:
            vectors[paper['citekey']] = _vectors(saved, paper, model)
            items[paper['citekey']] = _paper(paper, saved)
    scores, semantic, lexical, assessment = similarity_ranking.rank(seed['citekey'], rows, vectors)
    selected = [p for p in rows if p['id'] != seed['id'] and
                (filters['year'] is None or p['year'] == filters['year']) and
                (filters['author'] is None or filters['author'].lower() in p['author'].lower()) and
                (filters['doi'] is None or p['doi'] == normalize_doi(filters['doi'])) and
                (filters['citekeys'] is None or p['citekey'] in filters['citekeys'])]
    eligible = {p['citekey'] for p in selected} & items.keys()
    ranked = sorted(eligible, key=lambda key:(-scores[key],key))[:top] if assessment['decision']=='candidates' else []
    results = [{**items[key], 'ranking_score':scores[key], 'similarity_score':semantic[key],
                'lexical_score':lexical[key], 'evidence_status':'metadata_similarity_unverified'} for key in ranked]
    return {'source':_paper(seed,source_rows), 'results':results, 'embedding_model':info,
            'index':index_state(db), 'filters':filters, 'assessment':assessment,
            'ranking':similarity_ranking.POLICY+'; ties=citekey',
            'candidates':{'total':len(selected), 'indexed':len(eligible),
                          'missing_vectors':len(selected)-len(eligible),
                          'empty_metadata':sum(not any(normalized_fields(p['title'],p['abstract'])) for p in selected)},
            'evidence_status':'metadata_similarity_unverified'}
