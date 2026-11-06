"""Title/abstract vectors in the existing index; no source writes or model downloads."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import unicodedata

from .config import Config, check_output_locations
from .database import connect
from .embeddings import SentenceTransformerBackend, normalize_vectors, numpy, split_passages


def normalized_fields(title: str, abstract: str) -> tuple[str, str]:
    # read_library has already converted BibTeX/LaTeX. A second TeX parse could
    # remove literal percent signs or scientific braces.
    return tuple(re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()
                 for s in (title, abstract))


def content_hash(title: str, abstract: str) -> str:
    return hashlib.sha256(json.dumps(normalized_fields(title, abstract),
                                    ensure_ascii=False).encode()).hexdigest()


def require_enabled(config: Config):
    if not config.semantic.enabled:
        raise ValueError("Semantic search is disabled. Run bibdesk-rag --setup to choose it, "
                         "or set enabled = true in the [semantic] TOML table.")


def protect(config: Config, config_path: Path | None = None, papers=None):
    check_output_locations(config.database, config.semantic.cache_dir)
    if papers is None:
        from .bibdesk import read_library
        papers = read_library(config.bib)
    sources = [config.bib, *(Path(ref.path) for p in papers for ref in p.files)]
    config.protect_sources(sources, config_path)
    cache = config.semantic.cache_dir.resolve()
    for source in [*sources, config.database, config_path]:
        if source is not None and (source.resolve().is_relative_to(cache)
                                   or cache == source.resolve().parent):
            raise ValueError("Model cache overlaps a source/config/database directory")
    return papers


def has_paper_vectors(db):
    return "paper_id" in {row[1] for row in db.execute("PRAGMA table_info(embeddings)")}


def active_model(db):
    value = db.execute("SELECT value FROM settings WHERE key='semantic_model_id'").fetchone()
    if value is None:
        return None
    row = db.execute("SELECT * FROM embedding_models WHERE id=?", (value[0],)).fetchone()
    if row is None:
        raise ValueError("Semantic model record is missing; run --index rebuild")
    return row


def update_vectors(db, config, backend, *, rebuild=False, previous_papers=()):
    """Participate in index_library's transaction, including schema and fulltext changes."""
    info = backend.info.as_dict()
    signature = json.dumps(info, sort_keys=True)
    try:
        model = active_model(db)
    except ValueError:
        if not rebuild:
            raise
        model = None
    if (model is None or model["config_json"] != signature
            or (model["name"], model["version"], model["dimensions"])
            != (info["model"], info["revision"], info["dimensions"])):
        # Legacy chunk embeddings are never created here, nor deleted by a model switch.
        db.execute("DELETE FROM embeddings WHERE paper_id IS NOT NULL")
        db.execute("INSERT OR IGNORE INTO embedding_models(name,version,dimensions,config_json) "
                   "VALUES (?,?,?,?)", (info["model"], info["revision"], info["dimensions"], signature))
        model = db.execute("SELECT * FROM embedding_models WHERE name=? AND version=? "
                           "AND dimensions=? AND config_json=?", (info["model"], info["revision"],
                           info["dimensions"], signature)).fetchone()
    model_id = model["id"]
    now = datetime.now(timezone.utc).isoformat()
    report = dict(enabled=True, embedded=0, reused=0, deleted=0, skipped=0,
                  title_only=0, abstract_missing=0, parts=0)
    eligible = set()
    for paper in db.execute("SELECT id,title,abstract FROM papers ORDER BY id").fetchall():
        paper_id = paper["id"]
        title, abstract = normalized_fields(paper["title"], paper["abstract"])
        report["abstract_missing"] += not bool(abstract)
        if not title and not abstract:
            db.execute("DELETE FROM embeddings WHERE paper_id=?", (paper_id,))
            report["skipped"] += 1
            continue
        eligible.add(paper_id)
        report["title_only"] += not bool(abstract)
        hashed = content_hash(title, abstract)
        old = db.execute("SELECT content_hash FROM embeddings WHERE paper_id=? AND model_id=?",
                         (paper_id, model_id)).fetchall()
        if not rebuild and old and all(row[0] == hashed for row in old):
            report["reused"] += 1
            continue
        db.execute("DELETE FROM embeddings WHERE paper_id=?", (paper_id,))
        texts = split_passages(title, abstract, backend)
        for start in range(0, len(texts), config.semantic.batch_size):
            batch = texts[start:start + config.semantic.batch_size]
            vectors = normalize_vectors(backend.embed_documents(batch), info["dimensions"])
            if len(vectors) != len(batch):
                raise ValueError("Embedding backend returned an incorrect number of vectors")
            for part, vector in enumerate(vectors, start):
                db.execute("INSERT INTO embeddings(paper_id,part,model_id,content_hash,vector,"
                           "embedded_at,title_only) VALUES (?,?,?,?,?,?,?)", (
                               paper_id, part, model_id, hashed, vector.astype("<f4").tobytes(),
                               now, not bool(abstract)))
        report["embedded"] += 1
        report["parts"] += len(texts)
    report["deleted"] = len(set(previous_papers) - eligible)
    for key, value in (("semantic_model_id", str(model_id)), ("semantic_last_indexed", now)):
        db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET "
                   "value=excluded.value", (key, value))
    return report


def semantic_status(db, config=None):
    fields = [normalized_fields(row[0], row[1])
              for row in db.execute("SELECT title,abstract FROM papers")]
    settings = dict(db.execute("SELECT key,value FROM settings"))
    model_error = None
    try:
        model = active_model(db)
        info = json.loads(model["config_json"]) if model else None
        if info is not None and not isinstance(info, dict):
            raise ValueError("Semantic model metadata must be an object")
    except (ValueError, TypeError) as exc:
        model, info, model_error = None, None, str(exc)
    supported = has_paper_vectors(db)
    count = db.execute("SELECT count(DISTINCT paper_id),count(*) FROM embeddings "
                       "WHERE paper_id IS NOT NULL").fetchone() if supported else (0, 0)
    indexed = count[0]
    eligible = sum(bool(t or a) for t, a in fields)
    stale = set()
    if supported:
        for row in db.execute("SELECT e.paper_id,e.content_hash,p.title,p.abstract "
                              "FROM embeddings e JOIN papers p ON p.id=e.paper_id"):
            if row["content_hash"] != content_hash(row["title"], row["abstract"]):
                stale.add(row["paper_id"])
    configured = None if config is None or info is None else all(
        info.get(key) == getattr(config.semantic, key)
        for key in ("model", "revision", "dimensions", "passage_prefix", "query_prefix", "max_tokens")
    )
    return dict(enabled=None if config is None else config.semantic.enabled,
                total=len(fields), eligible=eligible, indexed=indexed, vectors=count[1],
                missing=max(0, eligible - indexed), stale=len(stale),
                abstract_missing=sum(not a for _, a in fields),
                title_only=sum(bool(t) and not a for t, a in fields),
                skipped=len(fields) - eligible, model=info, configuration_matches=configured,
                model_error=model_error,
                last_updated=settings.get("semantic_last_indexed"),
                schema_upgrade_required=not supported)


def semantic_check(db, config=None):
    """Validate persisted vectors with stdlib only: no inference, downloads or NumPy import."""
    issues = []
    warnings = []
    summary = semantic_status(db, config)
    if summary["model_error"]:
        return {"issues": [summary["model_error"]], "status": summary}
    if not has_paper_vectors(db):
        if config is not None and config.semantic.enabled:
            issues.append("Semantic schema needs migration; run --index update")
        return {"issues": issues, "status": summary}
    model = active_model(db)
    current = model["id"] if model else None
    active_ids = set()
    groups = {}
    for row in db.execute(
        "SELECT e.*,m.dimensions,m.config_json,p.title,p.abstract FROM embeddings e "
        "JOIN embedding_models m ON m.id=e.model_id "
        "LEFT JOIN papers p ON p.id=e.paper_id ORDER BY e.paper_id,e.part"
    ):
        label = f"embedding {row['id']}"
        blob = row["vector"]
        if len(blob) != row["dimensions"] * 4:
            issues.append(f"{label}: inconsistent vector dimensions")
        else:
            values = struct.unpack(f"<{row['dimensions']}f", blob)
            norm = sum(float(v) * v for v in values)
            if not all(math.isfinite(v) for v in values) or abs(norm - 1) > 2e-4:
                issues.append(f"{label}: invalid or unnormalized vector")
        if row["paper_id"] is None:
            continue
        active_ids.add(row["model_id"])
        groups.setdefault(row["paper_id"], []).append(row["part"])
        if row["content_hash"] != content_hash(row["title"], row["abstract"]):
            target = warnings if config is not None and not config.semantic.enabled else issues
            target.append(f"{label}: stale title/abstract content hash; run --index update when enabled")
        if (row["content_hash"] == content_hash(row["title"], row["abstract"])
                and bool(row["title_only"]) != (not bool(normalized_fields('', row['abstract'])[1]))):
            issues.append(f"{label}: inconsistent title_only flag")
    for parts in groups.values():
        if parts != list(range(len(parts))):
            issues.append("Semantic paper part numbers are not contiguous")
    if active_ids and active_ids != {current}:
        issues.append("Paper vectors use mixed or inactive embedding models")
    if model:
        info = json.loads(model["config_json"])
        if any(info.get(key) != model[col] for key, col in (
            ("model", "name"), ("revision", "version"), ("dimensions", "dimensions")
        )):
            issues.append("Embedding model metadata is inconsistent")
    if config is not None and config.semantic.enabled:
        if summary["missing"]:
            issues.append("Semantic vectors are missing; run --index update")
        if summary["configuration_matches"] is False:
            issues.append("Semantic settings changed; run --index update")
        if not model:
            issues.append("Semantic index has not been built; run --index update")
    return {"issues": issues, "warnings": warnings, "status": summary}


def semantic_search(config: Config, query: str, limit=None, *, backend=None):
    require_enabled(config)
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Semantic query must contain 1..2000 characters")
    limit = config.semantic.default_limit if limit is None else limit
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Semantic limit must be between 1 and 100")
    if not config.database.is_file():
        raise ValueError("Index missing. Run bibdesk-rag --index update first.")
    with closing(connect(config.database, readonly=True)) as db:
        db.execute("BEGIN")
        settings = dict(db.execute("SELECT key,value FROM settings"))
        if settings.get("bib_path") != str(config.bib.resolve()):
            raise ValueError("Index belongs to a different library; choose a different database")
        model = active_model(db)
        if not model or not has_paper_vectors(db):
            raise ValueError("Semantic index missing. Run bibdesk-rag --index update first.")
        backend = backend or SentenceTransformerBackend(config.semantic)
        if json.loads(model["config_json"]) != backend.info.as_dict():
            raise ValueError("Embedding model/settings changed. Run bibdesk-rag --index update.")
        if (model["name"], model["version"], model["dimensions"]) != (
            backend.info.model, backend.info.revision, backend.info.dimensions
        ):
            raise ValueError("Embedding model metadata is inconsistent; run --index rebuild")
        if backend.count_tokens(backend.info.query_prefix + query.strip()) > backend.info.max_tokens:
            raise ValueError("Query exceeds the model token limit; shorten the query")
        vector = normalize_vectors([backend.embed_query(query.strip())], backend.info.dimensions)[0]
        np = numpy()
        scores = {}
        cursor = db.execute("SELECT e.paper_id,e.vector,e.content_hash,p.title,p.abstract "
                            "FROM embeddings e JOIN papers p ON p.id=e.paper_id "
                            "WHERE e.model_id=? ORDER BY e.paper_id,e.part", (model["id"],))
        while rows := cursor.fetchmany(1024):
            values = []
            for row in rows:
                if row["content_hash"] != content_hash(row["title"], row["abstract"]):
                    raise ValueError("Stale semantic vectors; run --index update")
                if len(row["vector"]) != backend.info.dimensions * 4:
                    raise ValueError("Inconsistent vector dimensions; run --index rebuild")
                values.append(np.frombuffer(row["vector"], dtype="<f4"))
            matrix = np.asarray(values)
            if not np.isfinite(matrix).all() or not np.allclose(
                np.linalg.norm(matrix, axis=1), 1, atol=1e-4
            ):
                raise ValueError("Invalid stored vector; run --index rebuild")
            for row, score in zip(rows, np.clip(matrix @ vector, -1, 1)):
                key = row["paper_id"]
                scores[key] = max(scores.get(key, -1.0), float(score))
        ranked = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
        results = []
        for key in ranked:
            row = db.execute("SELECT citekey,title,author,year,journal,doi,abstract,id "
                             "FROM papers WHERE id=?", (key,)).fetchone()
            data = dict(row)
            embedded = db.execute("SELECT embedded_at,title_only FROM embeddings WHERE "
                                  "paper_id=? AND model_id=? LIMIT 1", (key, model["id"])).fetchone()
            data.update(similarity_score=scores[key], title_only=bool(embedded["title_only"]),
                        has_abstract=not bool(embedded["title_only"]),
                        embedding_model=backend.info.as_dict(), embedded_at=embedded["embedded_at"],
                        evidence_status="metadata_similarity_unverified", source_bib=settings["bib_path"],
                        indexed_bib_hash=settings["bib_hash"])
            results.append(data)
        return results
