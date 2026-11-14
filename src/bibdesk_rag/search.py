"""Bounded lexical retrieval, with an interface for future local/hybrid engines."""

from __future__ import annotations

from collections import Counter
import json
import re
from typing import Protocol

from .bibdesk import normalize_doi
from .database import paper_dict
from .normalization import match_query, normalize_search

MAX_RESULTS = 100
METADATA_TEXT_LIMITS = {
    "title": 1000,
    "author": 2000,
    "editor": 2000,
    "abstract": 4000,
    "keywords": 2000,
    "journal": 1000,
    "booktitle": 1000,
    "volume": 100,
    "number": 100,
    "pages": 200,
    "year": 50,
    "url": 2000,
    "entry_type": 100,
}


def _bound_metadata(result: dict) -> None:
    """Limit search summaries while preserving exact identifiers and source paths."""
    truncated = []
    for field, limit in METADATA_TEXT_LIMITS.items():
        if field in result and len(result[field]) > limit:
            result[field] = result[field][:limit]
            truncated.append(field)
    if "groups" in result:
        groups = result["groups"]
        if len(groups) > 32 or any(len(group) > 256 for group in groups):
            result["groups"] = [group[:256] for group in groups[:32]]
            truncated.append("groups")
    result["truncated_fields"] = truncated
    result["abstract_truncated"] = "abstract" in truncated


def _verbatim_snippet(text: str, query: str, max_chars: int = 600) -> tuple[str, bool]:
    """Locate normalized terms but quote only unchanged source characters.

    FTS indexes intentionally normalize identifiers. Its own snippet function
    would consequently turn scientific values such as '10-15' into '1015'.
    Find a matching source word instead and keep the returned evidence literal.
    """
    terms = set(re.findall(r"\w+", normalize_search(query)))
    anchor = 0
    for word in re.finditer(r"\w+(?:[-‐‑‒–—−﹣－]\w+)*", text):
        if normalize_search(word.group()) in terms:
            anchor = word.start()
            break
    start = max(0, anchor - max_chars // 3)
    end = min(len(text), start + max_chars)
    start = max(0, end - max_chars)
    return text[start:end], start > 0 or end < len(text)


def check_top(top: int) -> None:
    if type(top) is not int or not 1 <= top <= MAX_RESULTS:
        raise ValueError(f"top must be between 1 and {MAX_RESULTS}")


class SearchEngine(Protocol):
    def search_papers(self, query: str, top: int = 10, **filters) -> list[dict]: ...
    def search_fulltext(self, query: str, top: int = 10, **filters) -> list[dict]: ...


class SQLiteSearch:
    def __init__(self, db):
        self.db = db

    def search_papers(
        self,
        query: str,
        top: int = 10,
        *,
        year: str | None = None,
        doi: str | None = None,
        citekey: str | None = None,
        author: str | None = None,
    ) -> list[dict]:
        check_top(top)
        expr = match_query(query)
        clauses, args = [], []
        for column, value in (
            ("year", year),
            ("doi", normalize_doi(doi) if doi else None),
            ("citekey", citekey),
        ):
            if value is not None:
                clauses.append(f"p.{column}=?")
                args.append(str(value))
        if author:
            clauses.append("instr(lower(p.author),lower(?))>0")
            args.append(author)
        where = " AND ".join(clauses) or "1"
        # Exact identifiers bypass FTS entirely; duplicate DOI entries are retained.
        if citekey is not None or doi is not None:
            rows = self.db.execute(
                f"SELECT p.*,0.0 AS score FROM papers p WHERE {where} ORDER BY p.id LIMIT ?",
                [*args, top],
            )
            return [self._metadata(row) for row in rows]
        exact = self.db.execute(
            f"SELECT p.*,0.0 AS score FROM papers p WHERE {where} AND (p.citekey=? OR (p.doi<>'' AND p.doi=?)) ORDER BY p.id LIMIT ?",
            [*args, query.strip(), normalize_doi(query), top],
        ).fetchall()
        if exact:
            return [self._metadata(row) for row in exact]
        if not expr:
            return []
        rows = self.db.execute(
            f"SELECT p.*,bm25(papers_fts,8.0,4.0,2.0,3.0,1.0) AS score FROM papers_fts JOIN papers p ON p.id=papers_fts.rowid WHERE papers_fts MATCH ? AND {where} ORDER BY score,p.id LIMIT ?",
            [expr, *args, top],
        )
        return [self._metadata(row) for row in rows]

    @staticmethod
    def _metadata(row):
        result = paper_dict(row)
        # Search is compact; full fields and BibTeX are available through get_paper.
        result.pop("bibtex", None)
        result.pop("fields", None)
        _bound_metadata(result)
        result.update(
            source_type="metadata",
            file_path=None,
            page_start=None,
            page_end=None,
            chunk_id=None,
            attachment_id=None,
            snippet=(result["abstract"] or result["title"])[:600],
            untrusted_source=True,
        )
        return result

    def get_paper(self, citekey: str) -> dict:
        row = self.db.execute("SELECT * FROM papers WHERE citekey=?", (citekey,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown citekey: {citekey}")
        result = paper_dict(row)
        result["untrusted_source"] = True
        return result

    def get_attachments(self, citekey: str) -> list[dict]:
        paper = self.get_paper(citekey)
        rows = self.db.execute(
            "SELECT a.*,pa.role,pa.original FROM attachments a JOIN paper_attachments pa ON pa.attachment_id=a.id WHERE pa.paper_id=? ORDER BY a.id",
            (paper["id"],),
        )
        results = []
        for row in rows:
            value = dict(row)
            value["attachment_id"] = value.pop("id")
            value["file_path"] = value.pop("path")
            value["members"] = json.loads(value.pop("members_json"))
            value.update(citekey=citekey, doi=paper["doi"])
            results.append(value)
        return results

    def _chunk(self, row, *, include_text=True):
        value = dict(row)
        value["chunk_id"] = value.pop("id")
        value.pop("search_text", None)
        value["untrusted_source"] = True
        if value.get("extraction_warning"):
            warning = value["extraction_warning"]
            value["extraction_warning"] = warning[:1000]
            value["extraction_warning_truncated"] = len(warning) > 1000
        if not include_text:
            value.pop("text", None)
        return value

    def get_chunk(self, chunk_id: int, *, max_chars: int = 10000) -> dict:
        if type(chunk_id) is not int or chunk_id < 1:
            raise ValueError("chunk_id must be a positive integer")
        if type(max_chars) is not int or not 1 <= max_chars <= 20000:
            raise ValueError("max_chars must be between 1 and 20000")
        row = self.db.execute(
            "SELECT c.*,a.path AS file_path,a.content_hash,a.extraction_status,"
            "a.error_message AS extraction_warning FROM chunks c JOIN attachments a ON a.id=c.attachment_id WHERE c.id=?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown chunk: {chunk_id}")
        value = self._chunk(row)
        value["truncated"] = len(value["text"]) > max_chars
        value["text"] = value["text"][:max_chars]
        value["citations"] = [
            dict(r)
            for r in self.db.execute(
                "SELECT p.citekey,p.title,p.doi,pa.role FROM papers p JOIN paper_attachments pa ON pa.paper_id=p.id WHERE pa.attachment_id=? ORDER BY p.id",
                (value["attachment_id"],),
            )
        ]
        return value

    def search_fulltext(
        self, query: str, top: int = 10, *, citekeys: list[str] | None = None, per_paper: int = 2
    ) -> list[dict]:
        check_top(top)
        if type(per_paper) is not int or not 1 <= per_paper <= 10:
            raise ValueError("per_paper must be between 1 and 10")
        expr = match_query(query)
        if not expr or citekeys == []:
            return []
        args = [expr]
        restriction = ""
        if citekeys is not None:
            if len(citekeys) > 100 or any(not isinstance(key, str) for key in citekeys):
                raise ValueError("citekeys must contain at most 100 strings")
            restriction = " AND p.citekey IN (" + ",".join("?" for _ in citekeys) + ")"
            args.extend(citekeys)
        # Stream ranking then apply per-paper limits: a prolific paper cannot exhaust a
        # fixed SQL candidate window and hide all other papers.
        rows = self.db.execute(
            """SELECT c.*,a.path AS file_path,a.content_hash,a.extraction_status,
          a.error_message AS extraction_warning,p.citekey,p.title,p.doi,
          pa.role,bm25(chunks_fts) AS score
          FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
          JOIN attachments a ON a.id=c.attachment_id
          JOIN paper_attachments pa ON pa.attachment_id=a.id
          JOIN papers p ON p.id=pa.paper_id WHERE chunks_fts MATCH ?"""
            + restriction
            + " ORDER BY score,c.id,p.id",
            args,
        )
        counts, results = Counter(), []
        for row in rows:
            if counts[row["citekey"]] >= per_paper:
                continue
            value = self._chunk(row)
            _bound_metadata(value)
            value["snippet"], value["snippet_truncated"] = _verbatim_snippet(
                value.pop("text"), query
            )
            counts[row["citekey"]] += 1
            results.append(value)
            if len(results) >= top:
                break
        return results

    def search(
        self,
        query: str,
        top: int = 10,
        *,
        scope: str = "all",
        per_paper: int = 2,
        citekeys: list[str] | None = None,
        metadata_query: str | None = None,
    ) -> list[dict]:
        check_top(top)
        if scope == "metadata":
            return self.search_papers(query, top)
        if scope == "fulltext":
            return self.search_fulltext(query, top, citekeys=citekeys, per_paper=per_paper)
        if scope != "all":
            raise ValueError("scope must be all, metadata or fulltext")
        candidates = (
            self.search_papers(metadata_query or query, min(100, max(20, top)))
            if citekeys is None
            else []
        )
        selected = (
            citekeys if citekeys is not None else ([p["citekey"] for p in candidates] or None)
        )
        if metadata_query is not None and not candidates and citekeys is None:
            return []
        fulltext = self.search_fulltext(query, top, citekeys=selected, per_paper=per_paper)
        seen = {hit["citekey"] for hit in fulltext}
        return (fulltext + [p for p in candidates if p["citekey"] not in seen])[:top]
