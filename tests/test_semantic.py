"""Generated bibliography only. Fake embeddings test mechanics, not model quality."""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3

import numpy as np
import pytest

from bibdesk_rag import cli, embeddings, semantic, indexer
from bibdesk_rag.database import connect
from bibdesk_rag.bibdesk import read_library
from bibdesk_rag.config import Config, load_config
from bibdesk_rag.embeddings import ModelInfo, normalize_vectors, split_passages
from bibdesk_rag.mcp_server import MCPServer
from bibdesk_rag.semantic_config import SemanticOptions


def synthetic_bib():
    return r"""
@article{Repair,
 title={Homologous recombination repairs DNA double-strand breaks},
 abstract={DNA damage repair mechanisms restore broken DNA by homologous recombination.
 Repair of double-strand breaks preserves genome integrity.},
 author={Synthetic, Researcher}, year={2026}, journal={Generated Journal}, doi={10.1234/repair}}
@article{Chromatin,
 title={Chromatin regulation and ultraviolet damage tolerance},
 abstract={Histone modifications regulate chromatin accessibility and UV tolerance.
 Chromatin remodeling promotes survival after ultraviolet irradiation.}}
@article{RecQ,
 title={RecQ helicases maintain genome stability under replication stress},
 abstract={RecQ DNA helicases stabilize stalled replication forks in filamentous fungi.
 Replication stress challenges genome stability in Neurospora.}}
@article{Plant,
 title={Photosynthesis in green leaves},
 abstract={Light harvesting and carbon fixation enable plant growth.}}
"""


class FakeBackend:
    def __init__(self, options):
        self.info = ModelInfo(options.model, options.revision, options.dimensions,
                              options.passage_prefix, options.query_prefix,
                              options.max_tokens, "generated-fixture-v1")
        self.calls = []

    def count_tokens(self, text):
        return len(text) + 2

    def vector(self, text):
        value = text.casefold()
        if any(word in value for word in ("chromatin", "クロマチン")):
            return [0, 1, 0, 0]
        if any(word in value for word in ("recq", "genome stability", "糸状菌")):
            return [0, 0, 1, 0]
        if any(word in value for word in ("repair", "recombination", "相同組換え")):
            return [1, 0, 0, 0]
        return [0, 0, 0, 1]

    def embed_documents(self, texts):
        self.calls.extend(texts)
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        return self.vector(text)


@pytest.fixture
def collection(tmp_path):
    source = tmp_path / "sources" / "refs.bib"
    source.parent.mkdir()
    source.write_text(synthetic_bib())
    options = SemanticOptions(enabled=True, dimensions=4)
    config = Config(source, tmp_path / "state" / "index.sqlite3", semantic=options)
    path = tmp_path / "settings.toml"
    path.write_text(f'bib = {json.dumps(str(source))}\n'
                    f'database = {json.dumps(str(config.database))}\n'
                    '[semantic]\nenabled = true\ndimensions = 4\n')
    return config, path, FakeBackend(options)


def update(collection, **kwargs):
    config, path, backend = collection
    return indexer.index_library(config, config_path=path, backend=backend, **kwargs)["semantic"]


def status_for(config):
    with closing(connect(config.database, readonly=True)) as db:
        return semantic.semantic_status(db, config)


def snapshot(config):
    with closing(connect(config.database, readonly=True)) as db:
        return {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table}")]
                for table in ("settings", "papers", "chunks", "embedding_models", "embeddings")}


def test_extract_normalize_hash_and_missing_fields(collection):
    config, _, backend = collection
    config.bib.write_text(r"""@article{Only, title={{RecQ} and $\alpha$ H$_2$O 100\%}}
@article{Empty, author={No title}}
@article{Abstract, abstract={DNA repair}}
""")
    original = config.bib.read_bytes()
    papers = read_library(config.bib)
    title = papers[0].title
    assert "RecQ" in title and "α" in title and "100%" in title
    assert "{" not in title and "\\" not in title
    assert semantic.normalized_fields("A\n  B", "e\u0301") == ("A B", "é")
    assert semantic.content_hash("A\n B", "é") == semantic.content_hash("A B", "e\u0301")
    assert semantic.content_hash("A", "B") != semantic.content_hash("AB", "")
    report = update(collection)
    assert (report["embedded"], report["skipped"], report["title_only"]) == (2, 1, 1)
    assert config.bib.read_bytes() == original
    results = semantic.semantic_search(config, "RecQ", backend=backend)
    assert next(item for item in results if item["citekey"] == "Only")["title_only"]


def test_vector_math_and_invalid_values():
    actual = normalize_vectors([[3, 4], [0, 5]], 2)
    assert actual.dtype == np.float32
    np.testing.assert_allclose(actual @ actual[1], [0.8, 1])
    for invalid in ([[0, 0]], [[float("nan"), 1]], [[float("inf"), 0]], [[1]], [1, 2]):
        with pytest.raises(ValueError):
            normalize_vectors(invalid, 2)


def test_token_splitting_retains_all_content(collection):
    _, _, backend = collection
    backend.info = replace(backend.info, max_tokens=70)
    abstract = "long 科学的な本文 αβ H₂O  " * 30
    parts = split_passages("RecQ", abstract, backend)
    assert len(parts) > 1
    header = "Title: RecQ\nAbstract: "
    assert "".join(part.removeprefix(header) for part in parts) == abstract
    assert all(backend.count_tokens(backend.info.passage_prefix + part) <= 70 for part in parts)
    long_title = "αβ RecQ " * 70
    parts = split_passages(long_title, abstract, backend)
    assert "".join(parts) == f"Title: {long_title}\nAbstract: {abstract}"


def test_incremental_metadata_changes_removal_model_and_rollback(collection):
    config, _, backend = collection
    original = hashlib.sha256(config.bib.read_bytes()).hexdigest()
    assert update(collection)["embedded"] == 4
    assert all("Synthetic" not in text and "Generated Journal" not in text
               and "10.1234" not in text for text in backend.calls)
    assert config.database.exists()
    assert snapshot(config)["chunks"] == []
    assert original == hashlib.sha256(config.bib.read_bytes()).hexdigest()
    first = snapshot(config)
    backend.calls.clear()
    assert update(collection)["reused"] == 4 and not backend.calls
    config.bib.write_text(config.bib.read_text().replace("Synthetic, Researcher", "New, Author"))
    assert update(collection)["reused"] == 4 and not backend.calls
    assert semantic.semantic_search(config, "repair", backend=backend)[0]["author"] == "New, Author"
    config.bib.write_text(config.bib.read_text().replace("DNA damage repair mechanisms", "New repair"))
    assert update(collection)["embedded"] == 1
    assert len(backend.calls) == 1
    config.bib.write_text(config.bib.read_text() + "\n@article{Added,title={New entry}}")
    assert update(collection)["embedded"] == 1
    config.bib.write_text(config.bib.read_text().split("@article{Plant")[0])
    assert update(collection)["deleted"] == 2
    backend.info = replace(backend.info, revision="b" * 40)
    with pytest.raises(ValueError, match="changed"):
        semantic.semantic_search(config, "repair", backend=backend)
    assert update(collection)["embedded"] == 3
    prior = snapshot(config)
    backend.info = replace(backend.info, backend="failure")
    def failure(texts):
        raise RuntimeError("Synthetic interrupted inference")
    backend.embed_documents = failure
    with pytest.raises(RuntimeError, match="interrupted"):
        update(collection)
    assert snapshot(config) == prior
    assert first["embeddings"]


@pytest.mark.parametrize("query,expected", [
    ("DNA damage repair", "Repair"), ("DNA repair mechanisms", "Repair"),
    ("相同組換え修復", "Repair"), ("Chromatin regulation and UV tolerance", "Chromatin"),
    ("RecQ helicase and genome stability", "RecQ"), ("糸状菌", "RecQ"),
])
def test_synthetic_rank_and_multilingual_query_plumbing(collection, query, expected):
    config, _, backend = collection
    update(collection)
    results = semantic.semantic_search(config, query, 3, backend=backend)
    assert results[0]["citekey"] == expected
    assert len(results) == len({item["citekey"] for item in results}) == 3
    assert all(results[i]["similarity_score"] >= results[i + 1]["similarity_score"]
               for i in range(2))
    assert all(item["evidence_status"] == "metadata_similarity_unverified" for item in results)


def test_cli_mcp_and_readonly_offline(collection, monkeypatch, capsys):
    config, path, backend = collection
    monkeypatch.setattr(semantic, "SentenceTransformerBackend", lambda options: backend)
    def no_network(*args, **kwargs):
        pytest.fail("Normal indexing/search must not access network")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert cli.main(["--temp", str(path), "--index", "update", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["semantic"]["embedded"] == 4
    assert cli.main(["--temp", str(path), "--index", "status", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["semantic"]["indexed"] == 4
    assert cli.main(["--temp", str(path), "--paper", "search", "相同組換え修復",
                     "--mode", "semantic", "--top", "1", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["citekey"] == "Repair"
    before = config.database.read_bytes()
    server = MCPServer(path)
    result = server.call_tool("semantic_search_papers", {"query": "repair", "limit": 1})
    assert not result["isError"]
    data = json.loads(result["content"][0]["text"])["data"]
    assert data[0]["citekey"] == "Repair"
    for invalid in ({"query": "x", "limit": True}, {"query": "x", "limit": 101},
                    {"query": "x", "unknown": "value"}, {"query": "x" * 2001}):
        assert server.call_tool("semantic_search_papers", invalid)["isError"]
    assert config.database.read_bytes() == before
    with closing(connect(config.database, readonly=True)) as db:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM papers")


def test_mcp_long_metadata_preserves_model_and_provenance(collection, monkeypatch):
    config, path, backend = collection
    config.bib.write_text('@article{Long,title={' + 'RecQ ' * 2000 + '},abstract={repair}}')
    update(collection)
    monkeypatch.setattr(semantic, "SentenceTransformerBackend", lambda options: backend)
    result = MCPServer(path).call_tool("semantic_search_papers", {"query": "RecQ", "limit": 1})
    assert not result["isError"]
    data = json.loads(result["content"][0]["text"])["data"][0]
    assert data["embedding_model"] == backend.info.as_dict()
    assert data["source_bib"] == str(config.bib)
    assert data["indexed_bib_hash"] == indexer.digest(config.bib)
    assert data["truncated"] and "title" in data["truncated_fields"]


def test_bounds_parts_and_corrupt_dimensions(collection):
    config, _, backend = collection
    config.bib.write_text("@article{Long,title={Repair},abstract={" + "repair " * 300 + "}}")
    update(collection)
    assert status_for(config)["vectors"] > 1
    assert len(semantic.semantic_search(config, "repair", 10, backend=backend)) == 1
    for query, limit in (("", 1), ("q" * 2001, 1), ("q", 0), ("q", True)):
        with pytest.raises(ValueError):
            semantic.semantic_search(config, query, limit, backend=backend)
    with closing(connect(config.database, readonly=False)) as db, db:
        db.execute("UPDATE embeddings SET vector=?", (b"bad",))
    with pytest.raises(ValueError, match="dimensions"):
        semantic.semantic_search(config, "repair", backend=backend)


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_original_and_sidecar_collisions(collection, suffix):
    config, _, _ = collection
    output = config.database
    output.parent.mkdir()
    Path(str(output) + suffix).hardlink_to(config.bib)
    before = config.bib.read_bytes()
    with pytest.raises(ValueError, match="overlap|overwrite"):
        update(collection)
    assert config.bib.read_bytes() == before


def test_unrelated_database_and_library_rejected(collection):
    config, _, backend = collection
    path = config.database
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unrelated(x)")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="application identifier"):
        update(collection)
    assert path.read_bytes() == before
    path.unlink()
    update(collection)
    config.bib = config.bib.with_name("other.bib")
    config.bib.write_text(synthetic_bib())
    with pytest.raises(ValueError, match="another library"):
        update(collection)
    with pytest.raises(ValueError, match="different library"):
        semantic.semantic_search(config, "repair", backend=backend)


def test_missing_disabled_and_config_validation(collection):
    config, path, backend = collection
    with pytest.raises(ValueError, match="--index update"):
        semantic.semantic_search(config, "repair", backend=backend)
    config.semantic.enabled = False
    assert indexer.index_library(config)["semantic"] == {"enabled": False}
    with pytest.raises(ValueError, match="disabled"):
        semantic.semantic_search(config, "repair", backend=backend)
    for option in (dict(enabled="yes"), dict(revision="main"), dict(batch_size=0),
                   dict(dimensions=True), dict(model="/a/local/path")):
        with pytest.raises(ValueError):
            SemanticOptions(**option)
    assert load_config(path).semantic.enabled
    path.write_text(path.read_text() + 'cache_dir = "relative-models"\n')
    assert load_config(path).semantic.cache_dir == path.parent / "relative-models"


def test_wrong_backend_dimensions_roll_back(collection):
    config, _, backend = collection
    update(collection)
    before = snapshot(config)
    backend.embed_documents = lambda texts: [[1, 0] for _ in texts]
    with pytest.raises(ValueError, match="dimensions"):
        update(collection, rebuild=True)
    assert snapshot(config) == before


def test_keyword_database_cache_and_config_collisions(collection):
    config, path, _ = collection
    config.database = path
    with pytest.raises(ValueError, match="overlaps"):
        update(collection)
    config.database = path.parent / "index.sqlite3"
    config.semantic.cache_dir = config.bib.parent
    with pytest.raises(ValueError, match="overlaps"):
        update(collection)


def test_optional_dependencies_missing(monkeypatch):
    import builtins
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name in {"numpy", "sentence_transformers", "huggingface_hub"}:
            raise ImportError("fixture missing dependency")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    for call in (embeddings.numpy, lambda: embeddings.SentenceTransformerBackend(SemanticOptions()),
                 lambda: embeddings.download_model(SemanticOptions())):
        with pytest.raises(ValueError, match="pip install"):
            call()


def test_original_change_rolls_back(collection, monkeypatch):
    config, _, backend = collection
    update(collection)
    before = snapshot(config)
    original = indexer.digest
    calls = []
    def changed(path):
        calls.append(path)
        return original(path) if len(calls) <= 2 else "changed"
    monkeypatch.setattr(indexer, "digest", changed)
    with pytest.raises(RuntimeError, match="rolled back"):
        update(collection, rebuild=True)
    assert snapshot(config) == before


@pytest.mark.skipif(not os.environ.get("BIBDESK_RAG_REAL_MODEL_CACHE"),
                    reason="Opt-in: pre-download model; set BIBDESK_RAG_REAL_MODEL_CACHE")
def test_real_multilingual_model_offline(tmp_path, monkeypatch):
    """Actual E5 relevance check, separate from deterministic fake tests; no downloads."""
    cache = Path(os.environ["BIBDESK_RAG_REAL_MODEL_CACHE"]).resolve()
    source = tmp_path / "source" / "refs.bib"
    source.parent.mkdir()
    source.write_text(synthetic_bib())
    config = Config(source, tmp_path / "data" / "index.sqlite3",
                    semantic=SemanticOptions(enabled=True, cache_dir=cache))
    def no_network(*args, **kwargs):
        raise AssertionError("Real model test must be offline")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    backend = embeddings.SentenceTransformerBackend(config.semantic)
    indexer.index_library(config, backend=backend)
    for query, expected in [
        ("DNA damage repair", "Repair"), ("DNA repair mechanisms", "Repair"),
        ("相同組換え修復", "Repair"), ("Chromatin regulation and UV tolerance", "Chromatin"),
        ("RecQ helicase and genome stability", "RecQ"),
        ("DNA複製ストレスにおけるRecQヘリカーゼの役割", "RecQ"),
        ("クロマチン修飾と紫外線損傷耐性", "Chromatin"),
        ("糸状菌におけるゲノム安定性の維持", "RecQ"),
    ]:
        result = semantic.semantic_search(config, query, 2, backend=backend)
        assert expected in [item["citekey"] for item in result], (query, result)
    source.write_text(synthetic_bib() + '@article{Long,title={RecQ replication stress},abstract={'
                      + 'RecQ helicases protect genome stability. ' * 100 + '}}')
    changed = indexer.index_library(config, backend=backend)["semantic"]
    assert changed["parts"] > 1 and changed["embedded"] == 1 and changed["reused"] == 4
    hits = semantic.semantic_search(config, "RecQ replication stress", 10, backend=backend)
    assert len(hits) == 5 and len({item["citekey"] for item in hits}) == 5
    with pytest.raises(ValueError, match="token limit"):
        semantic.semantic_search(config, "修復" * 700, backend=backend)
