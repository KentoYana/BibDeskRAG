"""Transactional SQLite storage with trigger-maintained, separate FTS indexes."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

SCHEMA_VERSION = 2
# SQLite application identifier: ASCII "BRAG". Never adopt an unrelated DB.
APPLICATION_ID = 0x42524147
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS papers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, citekey TEXT NOT NULL UNIQUE,
 entry_type TEXT NOT NULL, title TEXT NOT NULL, author TEXT NOT NULL, editor TEXT NOT NULL,
 year TEXT NOT NULL, journal TEXT NOT NULL, booktitle TEXT NOT NULL,
 volume TEXT NOT NULL, number TEXT NOT NULL, pages TEXT NOT NULL,
 doi TEXT NOT NULL, abstract TEXT NOT NULL, keywords TEXT NOT NULL,
 groups_json TEXT NOT NULL, url TEXT NOT NULL, fields_json TEXT NOT NULL,
 bibtex TEXT NOT NULL, fingerprint TEXT NOT NULL,
 search_title TEXT NOT NULL, search_author TEXT NOT NULL, search_abstract TEXT NOT NULL,
 search_keywords TEXT NOT NULL, search_other TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS papers_doi ON papers(doi);
CREATE TABLE IF NOT EXISTS attachments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, file_type TEXT NOT NULL,
 file_size INTEGER, mtime_ns INTEGER, content_hash TEXT,
 extraction_status TEXT NOT NULL, error_message TEXT, members_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS paper_attachments (
 paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
 attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
 role TEXT NOT NULL, original TEXT NOT NULL,
 PRIMARY KEY(paper_id, attachment_id)
);
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
 source_type TEXT NOT NULL, page_start INTEGER, page_end INTEGER,
 sheet_name TEXT, row_start INTEGER, row_end INTEGER, member_path TEXT,
 text TEXT NOT NULL, search_text TEXT NOT NULL, chunk_order INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_attachment ON chunks(attachment_id);
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
 search_title, search_author, search_abstract, search_keywords, search_other,
 content='papers', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
 search_text, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS embedding_models (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL,
 dimensions INTEGER NOT NULL CHECK(dimensions > 0), config_json TEXT NOT NULL,
 UNIQUE(name,version,dimensions,config_json)
);
CREATE TABLE IF NOT EXISTS embeddings (
 id INTEGER PRIMARY KEY,
 chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
 paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
 part INTEGER NOT NULL DEFAULT 0 CHECK(part >= 0),
 model_id INTEGER NOT NULL REFERENCES embedding_models(id) ON DELETE CASCADE,
 content_hash TEXT NOT NULL, vector BLOB NOT NULL,
 embedded_at TEXT NOT NULL DEFAULT '', title_only INTEGER NOT NULL DEFAULT 0,
 CHECK ((chunk_id IS NOT NULL AND paper_id IS NULL) OR
        (chunk_id IS NULL AND paper_id IS NOT NULL))
);
"""


def _check_identity(db: sqlite3.Connection, *, allow_empty: bool) -> None:
    application_id = db.execute("PRAGMA application_id").fetchone()[0]
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if application_id != APPLICATION_ID:
        empty = not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
        if allow_empty and application_id == 0 and version == 0 and empty:
            return
        raise ValueError(
            "Refusing database without the bibdesk-rag application identifier; choose a separate index path"
        )
    if version not in (0, 1, SCHEMA_VERSION) or (version == 0 and not allow_empty):
        raise ValueError(
            f"Unsupported or uninitialized index schema {version}; use a compatible application"
        )


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path).expanduser().resolve()
    # Inspect an existing file in read-only mode before opening it for writing,
    # chmodding it, recovering a journal, or creating any application tables.
    if not readonly and path.exists() and path.stat().st_size:
        existing = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        try:
            _check_identity(existing, allow_empty=True)
        finally:
            existing.close()
    if readonly:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        db.execute("PRAGMA query_only=ON")
    else:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        _check_identity(db, allow_empty=not readonly)
        if not readonly:
            path.chmod(0o600)
    except Exception:
        db.close()
        raise
    return db


def initialize(db: sqlite3.Connection, *, in_transaction: bool = False) -> None:
    triggers = []
    for table, columns in (
        (
            "papers",
            ["search_title", "search_author", "search_abstract", "search_keywords", "search_other"],
        ),
        ("chunks", ["search_text"]),
    ):
        cols = ",".join(columns)
        new = ",".join("new." + c for c in columns)
        old = ",".join("old." + c for c in columns)
        triggers.append(f"""
        CREATE TRIGGER IF NOT EXISTS {table}_ai AFTER INSERT ON {table} BEGIN
          INSERT INTO {table}_fts(rowid,{cols}) VALUES(new.id,{new}); END;
        CREATE TRIGGER IF NOT EXISTS {table}_ad AFTER DELETE ON {table} BEGIN
          INSERT INTO {table}_fts({table}_fts,rowid,{cols}) VALUES('delete',old.id,{old}); END;
        CREATE TRIGGER IF NOT EXISTS {table}_au AFTER UPDATE ON {table} BEGIN
          INSERT INTO {table}_fts({table}_fts,rowid,{cols}) VALUES('delete',old.id,{old});
          INSERT INTO {table}_fts(rowid,{cols}) VALUES(new.id,{new}); END;
        """)
    def execute_script(script):
        # executescript commits an existing transaction. Execute complete SQLite
        # statements individually so migration + both indexes share one commit.
        statement = ""
        for line in script.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                db.execute(statement)
                statement = ""
        if statement.strip():
            raise ValueError("Incomplete schema statement")

    def create():
        old_columns = {row[1] for row in db.execute("PRAGMA table_info(embeddings)")}
        if old_columns and "paper_id" not in old_columns:
            db.execute("ALTER TABLE embeddings RENAME TO embeddings_v1")
        execute_script(SCHEMA + "\n" + "\n".join(triggers))
        if old_columns and "paper_id" not in old_columns:
            db.execute("INSERT INTO embeddings(chunk_id,model_id,content_hash,vector) "
                       "SELECT chunk_id,model_id,content_hash,vector FROM embeddings_v1")
            db.execute("DROP TABLE embeddings_v1")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS embeddings_chunk_model "
                   "ON embeddings(chunk_id,model_id) WHERE chunk_id IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS embeddings_paper_part_model "
                   "ON embeddings(paper_id,part,model_id) WHERE paper_id IS NOT NULL")
        db.execute(f"PRAGMA application_id={APPLICATION_ID}")
        db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    if in_transaction:
        if not db.in_transaction:
            raise ValueError("Schema migration requires a write transaction")
        create()
    else:
        with db:
            db.execute("BEGIN IMMEDIATE")
            create()


def status(db: sqlite3.Connection, config=None) -> dict:
    from .semantic import semantic_status

    return {
        "semantic": semantic_status(db, config),
        "counts": {
            t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("papers", "attachments", "chunks")
        },
        "extraction_status": {
            row[0]: row[1]
            for row in db.execute(
                "SELECT extraction_status,count(*) FROM attachments GROUP BY extraction_status"
            )
        },
        "settings": dict(db.execute("SELECT key,value FROM settings")),
        "duplicate_dois": [
            dict(row)
            for row in db.execute(
                "SELECT doi,count(*) AS count FROM papers WHERE doi<>'' GROUP BY doi HAVING count(*)>1"
            )
        ],
    }


def doctor(db: sqlite3.Connection, config=None) -> dict:
    issues = []
    check = db.execute("PRAGMA quick_check").fetchone()[0]
    if check != "ok":
        issues.append(check)
    issues.extend(str(tuple(row)) for row in db.execute("PRAGMA foreign_key_check"))
    # Copy into RAM: FTS's integrity-check is an INSERT, so never run it on a read-only index.
    memory = sqlite3.connect(":memory:")
    try:
        db.backup(memory)
        for name in ("papers_fts", "chunks_fts"):
            try:
                memory.execute(f"INSERT INTO {name}({name},rank) VALUES('integrity-check',1)")
            except sqlite3.DatabaseError as exc:
                issues.append(f"{name}: {exc}")
    finally:
        memory.close()
    failures = [
        dict(row)
        for row in db.execute(
            "SELECT id,path,extraction_status,error_message FROM attachments WHERE extraction_status NOT IN ('ok','unsupported')"
        )
    ]
    from .semantic import semantic_check

    semantic_result = semantic_check(db, config)
    issues.extend(semantic_result["issues"])
    return {
        "semantic": semantic_result,
        "ok": not issues,
        "issues": issues,
        "extraction_failures": failures,
        "status": status(db, config),
    }


def paper_dict(row: sqlite3.Row) -> dict:
    result = {k: row[k] for k in row.keys() if not k.startswith("search_") and k != "fingerprint"}
    for name in ("groups", "fields"):
        if name + "_json" in result:
            result[name] = json.loads(result.pop(name + "_json"))
    return result
