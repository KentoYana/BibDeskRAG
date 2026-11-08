"""Offline embedding interface and optional CPU SentenceTransformers adapter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import version
import os
from pathlib import Path
from typing import Protocol

from .progress import model_loading_progress
from .semantic_config import SemanticOptions

INSTALL_HELP = "Install in a standard venv with: python -m pip install 'bibdesk-rag[semantic]'"
MODEL_FILES = ["*.json", "*.safetensors", "*.txt", "tokenizer.model",
               "sentencepiece.bpe.model", "README.md", "LICENSE*"]


def model_is_cached(options: SemanticOptions) -> bool:
    """Inspect only the explicitly configured cache; never contact the Hub."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ValueError(INSTALL_HELP) from exc
    try:
        snapshot_download(options.model, revision=options.revision,
                          cache_dir=str(options.cache_dir), local_files_only=True,
                          allow_patterns=MODEL_FILES)
    except (OSError, ValueError):
        return False
    return True


def numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError(INSTALL_HELP) from exc
    return np


def normalize_vectors(values, dimensions: int):
    np = numpy()
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != dimensions or not np.isfinite(array).all():
        raise ValueError("Invalid embedding dimensions or non-finite vector")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or (norms <= 0).any():
        raise ValueError("Invalid zero or overflowing embedding vector")
    return array / norms


@dataclass(frozen=True)
class ModelInfo:
    model: str
    revision: str
    dimensions: int
    passage_prefix: str
    query_prefix: str
    max_tokens: int
    backend: str
    preprocessing: str = "unicode-fields-whitespace-nfc-v1;character-split-v1;max-pooling"

    def as_dict(self):
        return asdict(self)


class EmbeddingBackend(Protocol):
    info: ModelInfo

    def count_tokens(self, text: str) -> int: ...
    def embed_documents(self, texts: list[str]): ...
    def embed_query(self, text: str): ...


def split_passages(title: str, abstract: str, backend: EmbeddingBackend) -> list[str]:
    """Retain all characters; measure the complete prefixed input before encoding.

    Repeat a fitting title on each abstract part. If the title itself is too long,
    split the complete labelled text instead. No tokenizer decode/re-encode loss.
    """
    info = backend.info
    header = f"Title: {title}\nAbstract: "
    complete = header + abstract
    if backend.count_tokens(info.passage_prefix + complete) <= info.max_tokens:
        return [complete]
    if backend.count_tokens(info.passage_prefix + header) < info.max_tokens // 2:
        prefix, remaining = header, abstract
    else:
        prefix, remaining = "", complete
    pieces = []
    while remaining:
        low, high = 0, len(remaining)
        while low < high:
            mid = (low + high + 1) // 2
            if backend.count_tokens(info.passage_prefix + prefix + remaining[:mid]) <= info.max_tokens:
                low = mid
            else:
                high = mid - 1
        if low == 0:
            raise ValueError("Embedding token budget cannot fit an input character")
        piece = prefix + remaining[:low]
        if backend.count_tokens(info.passage_prefix + piece) > info.max_tokens:
            raise ValueError("Embedding token limit exceeded")
        pieces.append(piece)
        remaining = remaining[low:]
    return pieces


class SentenceTransformerBackend:
    def __init__(self, options: SemanticOptions):
        # No Hub requests, telemetry, remote code or pickle model deserialization.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        try:
            with model_loading_progress():
                from sentence_transformers import SentenceTransformer
                from huggingface_hub import snapshot_download

                snapshot = snapshot_download(options.model, revision=options.revision,
                                             cache_dir=str(options.cache_dir), local_files_only=True,
                                             allow_patterns=MODEL_FILES)
                self.model = SentenceTransformer(
                    snapshot, device="cpu", local_files_only=True, trust_remote_code=False,
                    model_kwargs={"use_safetensors": True},
                )
        except ImportError as exc:
            raise ValueError(INSTALL_HELP) from exc
        except (OSError, ValueError, RuntimeError) as exc:
            raise ValueError("Local model unavailable. Run bibdesk-rag --semantic download "
                             "with this configuration while online. " + str(exc)[:300]) from exc
        get_dimensions = getattr(self.model, "get_embedding_dimension", None)
        if get_dimensions is None:
            get_dimensions = self.model.get_sentence_embedding_dimension
        if get_dimensions() != options.dimensions:
            raise ValueError("Configured dimensions do not match the embedding model")
        if options.max_tokens > self.model.max_seq_length:
            raise ValueError("semantic.max_tokens exceeds the model's token limit")
        self.batch_size = options.batch_size
        self.info = ModelInfo(
            options.model, options.revision, options.dimensions, options.passage_prefix,
            options.query_prefix, options.max_tokens,
            "sentence-transformers/" + version("sentence-transformers")
            + ";transformers/" + version("transformers") + ";torch/" + version("torch"),
        )

    def count_tokens(self, text):
        return len(self.model.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def _encode(self, texts):
        if any(self.count_tokens(text) > self.info.max_tokens for text in texts):
            raise ValueError("Input exceeds model token limit; shorten the query")
        return normalize_vectors(self.model.encode(
            texts, batch_size=self.batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True, prompt="",
        ), self.info.dimensions)

    def embed_documents(self, texts):
        return self._encode([self.info.passage_prefix + text for text in texts])

    def embed_query(self, text):
        return self._encode([self.info.query_prefix + text])[0]


def download_model(options: SemanticOptions) -> dict:
    """Only this explicitly invoked operation may access the model Hub."""
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ValueError(INSTALL_HELP) from exc
    previous = {name: os.environ.pop(name, None)
                for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    try:
        # Environment flags may have been cached at import time by an earlier load.
        from huggingface_hub import constants
        offline = constants.HF_HUB_OFFLINE
        constants.HF_HUB_OFFLINE = False
        try:
            try:
                location = snapshot_download(
                    options.model, revision=options.revision, cache_dir=str(options.cache_dir),
                    allow_patterns=MODEL_FILES,
                )
            except Exception as exc:
                raise ValueError("Model download failed. Check network/cache access and "
                                 "retry --setup or --semantic download: " + str(exc)[:300]) from exc
        finally:
            constants.HF_HUB_OFFLINE = offline
    finally:
        for name, value in previous.items():
            if value is not None:
                os.environ[name] = value
    return {"model": options.model, "revision": options.revision, "snapshot": str(Path(location))}
