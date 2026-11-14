"""Incremental index updates; BibDesk and attachments are only ever read."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

from .bibdesk import read_library
from .config import Config
from .database import connect, initialize
from .extractors import extract_file
from .extractors.formats import EXCLUDED_FORMATS, EXTRACTION_REVISION, NEW_FORMATS
from .extractors.sources import is_iwork_directory, source_digest, source_stat
from .normalization import normalize_search


@dataclass(frozen=True)
class IndexProgress:
    """Completed work within an indexing phase; no source text or paths are exposed."""

    phase: str
    papers_done: int = 0
    papers_total: int = 0
    files_done: int = 0
    files_total: int = 0


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _paper_values(paper) -> dict:
    values = asdict(paper)
    values.pop("files")
    values["groups_json"] = json.dumps(values.pop("groups"), ensure_ascii=False)
    values["fields_json"] = json.dumps(values.pop("fields"), ensure_ascii=False, sort_keys=True)
    values["fingerprint"] = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    for key in ("title", "abstract", "keywords"):
        values["search_" + key] = normalize_search(values[key])
    values["search_author"] = normalize_search(values["author"] + " " + values["editor"])
    values["search_other"] = normalize_search(
        " ".join(
            str(values[k])
            for k in ("citekey", "doi", "year", "journal", "booktitle", "groups_json")
        )
    )
    return values


def index_library(
    config: Config,
    *,
    rebuild: bool = False,
    verify_hashes: bool = False,
    progress: Callable[[IndexProgress], None] | None = None,
    config_path: Path | None = None,
    backend=None,
) -> dict:
    papers_done = papers_total = files_done = files_total = 0

    def emit(phase: str) -> None:
        if progress is not None:
            progress(IndexProgress(phase, papers_done, papers_total, files_done, files_total))

    emit("reading")
    bib_hash = digest(config.bib)
    papers = read_library(config.bib)
    if digest(config.bib) != bib_hash:
        raise RuntimeError("BibDesk library changed during parsing; retry update")
    config.protect_sources([Path(ref.path) for paper in papers for ref in paper.files], config_path)
    if config.semantic.enabled:
        from .semantic import SentenceTransformerBackend, protect

        protect(config, config_path, papers)
        # Preflight is offline, before opening SQLite for writes or migrating it.
        backend = backend or SentenceTransformerBackend(config.semantic)
    papers_total = len(papers)
    if progress is not None:
        files_total = len({str(Path(ref.path).resolve()) for paper in papers for ref in paper.files})
    emit("indexing")
    options_json = json.dumps(asdict(config.extraction), sort_keys=True)
    report = dict(
        papers_added=0,
        papers_changed=0,
        papers_deleted=0,
        papers_renamed=0,
        files_extracted=0,
        files_reused=0,
        files_hashed=0,
        errors=[],
    )
    db = connect(config.database)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            initialize(db, in_transaction=True)
            previous = dict(db.execute("SELECT key,value FROM settings"))
            if previous.get("bib_path", str(config.bib)) != str(config.bib):
                raise ValueError("Index belongs to another library; choose a different database")
            previous_vectors = {row[0] for row in db.execute(
                "SELECT DISTINCT paper_id FROM embeddings WHERE paper_id IS NOT NULL")}
            reextract = rebuild or previous.get("extraction_options") != options_json
            policy_changed = previous.get("extraction_revision") != EXTRACTION_REVISION
            old = {
                row["citekey"]: dict(row)
                for row in db.execute("SELECT id,citekey,doi,fingerprint FROM papers")
            }
            new_keys = {paper.citekey for paper in papers}
            doi_counts = Counter(p.doi for p in papers if p.doi)
            old_doi_counts = Counter(p["doi"] for p in old.values() if p["doi"])
            deleted = {k: v for k, v in old.items() if k not in new_keys}
            incoming_paths = set()
            for paper in papers:
                values = _paper_values(paper)
                existing = old.get(paper.citekey)
                if (
                    not existing
                    and paper.doi
                    and doi_counts[paper.doi] == old_doi_counts[paper.doi] == 1
                ):
                    matches = [(k, v) for k, v in deleted.items() if v["doi"] == paper.doi]
                    if len(matches) == 1:
                        key, existing = matches[0]
                        deleted.pop(key)
                        report["papers_renamed"] += 1
                if existing:
                    paper_id = existing["id"]
                    if values["fingerprint"] != existing["fingerprint"]:
                        db.execute(
                            "UPDATE papers SET "
                            + ",".join(f"{k}=?" for k in values)
                            + " WHERE id=?",
                            [*values.values(), paper_id],
                        )
                        report["papers_changed"] += 1
                else:
                    paper_id = db.execute(
                        "INSERT INTO papers ("
                        + ",".join(values)
                        + ") VALUES ("
                        + ",".join("?" for _ in values)
                        + ")",
                        list(values.values()),
                    ).lastrowid
                    report["papers_added"] += 1
                db.execute("DELETE FROM paper_attachments WHERE paper_id=?", (paper_id,))
                for ref in paper.files:
                    path = str(Path(ref.path).resolve())
                    if path not in incoming_paths:
                        _index_attachment(
                            db, Path(path), ref.error, config,
                            reextract or (policy_changed and Path(path).suffix.lower()
                                          in NEW_FORMATS | {".zip"}),
                            verify_hashes, report,
                        )
                        incoming_paths.add(path)
                        files_done += 1
                        emit("indexing")
                    attachment_id = db.execute(
                        "SELECT id FROM attachments WHERE path=?", (path,)
                    ).fetchone()[0]
                    db.execute(
                        "INSERT OR IGNORE INTO paper_attachments VALUES (?,?,?,?)",
                        (paper_id, attachment_id, ref.role, ref.original),
                    )
                papers_done += 1
                emit("indexing")
            for removed in deleted.values():
                db.execute("DELETE FROM papers WHERE id=?", (removed["id"],))
                report["papers_deleted"] += 1
            db.execute(
                "DELETE FROM attachments WHERE id NOT IN (SELECT attachment_id FROM paper_attachments)"
            )
            if config.semantic.enabled:
                from .semantic import update_vectors

                emit("embedding")
                report["semantic"] = update_vectors(
                    db, config, backend, rebuild=rebuild, previous_papers=previous_vectors,
                )
            else:
                report["semantic"] = {"enabled": False}
            emit("committing")
            if digest(config.bib) != bib_hash:
                raise RuntimeError(
                    "BibDesk library changed during indexing; transaction rolled back"
                )
            for key, value in {
                "bib_path": str(config.bib),
                "bib_hash": bib_hash,
                "last_indexed": str(time.time()),
                "extraction_options": options_json,
                "extraction_revision": EXTRACTION_REVISION,
            }.items():
                db.execute(
                    "INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
    finally:
        db.close()
    emit("done")
    return report


def _index_attachment(db, path, resolution_error, config, reextract, verify_hashes, report):
    old = db.execute("SELECT * FROM attachments WHERE path=?", (str(path),)).fetchone()
    if old is None:
        attachment_id = db.execute(
            "INSERT INTO attachments(path,file_type,extraction_status) VALUES (?,?,'pending')",
            (str(path), path.suffix.lower()),
        ).lastrowid
    else:
        attachment_id = old["id"]
    try:
        if resolution_error:
            # Failed locators may carry a diagnostic placeholder path. Never
            # mistake an existing file at that path for an authorized source.
            raise ValueError(resolution_error)
        stat = source_stat(path, config.extraction)
        if not path.is_file() and not is_iwork_directory(path):
            raise ValueError("Attachment is not a regular file")
        if path.suffix.lower() in EXCLUDED_FORMATS:
            if (old and old["extraction_status"] == "excluded"
                    and old["file_size"] == stat.st_size and old["mtime_ns"] == stat.st_mtime_ns):
                report["files_reused"] += 1
                return
            # Classification requires no reading/hashing of excluded media bytes.
            db.execute("DELETE FROM chunks WHERE attachment_id=?", (attachment_id,))
            db.execute(
                "UPDATE attachments SET file_size=?,mtime_ns=?,content_hash=NULL,"
                "extraction_status='excluded',error_message=?,members_json='[]' WHERE id=?",
                (stat.st_size, stat.st_mtime_ns, "Images and videos are explicitly excluded", attachment_id),
            )
            report["files_extracted"] += 1
            return
        if stat.st_size > config.extraction.max_file_bytes:
            raise ValueError("Attachment exceeds max_file_bytes")
        if (
            not reextract
            and not verify_hashes
            and old
            and old["file_size"] == stat.st_size
            and old["mtime_ns"] == stat.st_mtime_ns
            and old["extraction_status"]
            in (
                "ok",
                "partial",
                "unsupported",
                "empty",
                "encrypted",
                "error",
                "image_only",
                "no_text",
            )
        ):
            report["files_reused"] += 1
            return
        content_hash = (source_digest(path, config.extraction) if is_iwork_directory(path)
                        else digest(path))
        report["files_hashed"] += 1
        if not reextract and old and old["content_hash"] == content_hash:
            db.execute(
                "UPDATE attachments SET file_size=?,mtime_ns=? WHERE id=?",
                (stat.st_size, stat.st_mtime_ns, attachment_id),
            )
            report["files_reused"] += 1
            return
        result = extract_file(path, config.extraction)
        report["files_extracted"] += 1
        after = source_stat(path, config.extraction)
        if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ):
            raise RuntimeError(f"Attachment changed during extraction: {path}; retry update")
        db.execute("DELETE FROM chunks WHERE attachment_id=?", (attachment_id,))
        for order, chunk in enumerate(result.chunks):
            values = asdict(chunk)
            values.update(
                attachment_id=attachment_id,
                chunk_order=order,
                search_text=normalize_search(chunk.text),
            )
            db.execute(
                "INSERT INTO chunks ("
                + ",".join(values)
                + ") VALUES ("
                + ",".join("?" for _ in values)
                + ")",
                list(values.values()),
            )
        db.execute(
            "UPDATE attachments SET file_size=?,mtime_ns=?,content_hash=?,extraction_status=?,error_message=?,members_json=? WHERE id=?",
            (
                stat.st_size,
                stat.st_mtime_ns,
                content_hash,
                result.status,
                result.error,
                json.dumps(result.members, ensure_ascii=False),
                attachment_id,
            ),
        )
        if result.error:
            report["errors"].append({"path": str(path), "error": result.error})
    except (OSError, ValueError) as exc:
        # Stale extracted content must not remain searchable after a missing/invalid source.
        db.execute("DELETE FROM chunks WHERE attachment_id=?", (attachment_id,))
        error = resolution_error or str(exc)
        db.execute(
            "UPDATE attachments SET file_size=NULL,mtime_ns=NULL,content_hash=NULL,extraction_status='error',error_message=? WHERE id=?",
            (error, attachment_id),
        )
        report["errors"].append({"path": str(path), "error": error})
