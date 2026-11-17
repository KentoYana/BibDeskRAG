"""Saved-vector ranking and development-calibrated rejection; stdlib only."""
from collections import Counter
import math
import re
from statistics import median

from .normalization import normalize_search
from .semantic_config import SemanticOptions

POLICY = 'title-anchor-hybrid-v1'
PROFILE = {'lexical_weight': 0.0, 'title_only_lexical_weight': 0.5,
           'rrf_k': 10, 'minimum_lexical': 0.15, 'minimum_relative_margin': 0.35,
           'minimum_background_candidates': 10}


def supported(info):
    defaults = SemanticOptions()
    return all(info.get(key) == getattr(defaults, key) for key in (
        'model', 'revision', 'dimensions', 'passage_prefix', 'query_prefix', 'max_tokens'
    )) and info.get('backend', '').startswith('sentence-transformers/')


def terms(text):
    text = normalize_search(text)
    words = re.findall(r'[a-z0-9_]+', text)
    for segment in re.findall(r'[\u3040-\u30ff\u3400-\u9fff]+', text):
        words.extend(segment[i:i+2] for i in range(max(1, len(segment)-1)))
    return Counter(words)


def lexical_vectors(papers):
    counts = {p['citekey']: terms((p['title']+' ')*3+p['abstract'][:600]) for p in papers}
    df = Counter(t for counts in counts.values() for t in counts)
    result = {}
    for key, counts in counts.items():
        values = {t:(1+math.log(n))*(1+math.log((1+len(papers))/(1+df[t]))) for t,n in counts.items()}
        norm = math.sqrt(math.fsum(v*v for v in values.values()))
        result[key] = {t:v/norm for t,v in values.items()} if norm else {}
    return result


def dot(a, b):
    return max(-1., min(1., math.fsum(x*y for x,y in zip(a,b))))


def rank(source, papers, vectors):
    """Calibrate against the entire library before applying user filters/top.

    More than two saved parts means a multi-passage abstract (or overlong
    title). Anchor-only comparison prevents shared appendices winning. Short
    abstracts retain their full metadata comparison.
    """
    keys = sorted(k for k in vectors if k != source)
    lexical = lexical_vectors(papers)
    by_key = {p['citekey']:p for p in papers}
    semantic, lexical_scores = {}, {}
    for key in keys:
        left, right = vectors[source], vectors[key]
        semantic[key] = dot(left[0],right[0]) if len(left)>2 or len(right)>2 else max(
            dot(a,b) for a in left[1:] or left for b in right[1:] or right)
        lexical_scores[key] = math.fsum(v*lexical[key].get(t,0) for t,v in lexical[source].items())
    weight = PROFILE['lexical_weight'] if by_key[source]['abstract'].strip() else PROFILE['title_only_lexical_weight']
    scores = {k:(1-weight)/(PROFILE['rrf_k']+1+i) for i,k in enumerate(
        sorted(keys,key=lambda k:(-semantic[k],k)))}
    for i,key in enumerate(sorted(keys,key=lambda k:(-lexical_scores[k],k))):
        if lexical_scores[key] > 0:
            scores[key] += weight/(PROFILE['rrf_k']+1+i)
    anchor_scores = [dot(vectors[source][0], vectors[k][0]) for k in keys]
    background = median(anchor_scores) if keys else 0.
    best = max(anchor_scores,default=0.)
    margin = (best-background)/max(1e-9,1-background)
    best_lexical = max(lexical_scores.values(),default=0.)
    enough = len(keys) >= PROFILE['minimum_background_candidates']
    has_title = bool(by_key[source]['title'].strip())
    accepted = enough and has_title and (best_lexical >= PROFILE['minimum_lexical'] or margin >= PROFILE['minimum_relative_margin'])
    assessment = {'decision':'candidates' if accepted else 'insufficient_evidence',
                  'calibrated':True, 'profile':POLICY,
                  'reason':'support_above_development_gate' if accepted else (
                      'title_anchor_missing' if not has_title else 'small_background' if not enough else 'weak_lexical_and_relative_semantic_support'),
                  'background_candidates':len(keys), 'background_median_cosine':background,
                  'relative_semantic_margin':margin, 'maximum_lexical_cosine':best_lexical,
                  'scope':'Synthetic development calibration; not a probability or scientific evidence.'}
    return scores, semantic, lexical_scores, assessment
