"""Optional local embedding configuration; no inference libraries imported here."""
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class SemanticOptions:
    enabled: bool = False
    model: str = "intfloat/multilingual-e5-small"
    revision: str = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
    dimensions: int = 384
    passage_prefix: str = "passage: "
    query_prefix: str = "query: "
    max_tokens: int = 512
    cache_dir: Path | None = None
    default_limit: int = 5
    batch_size: int = 16

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("semantic.enabled must be a boolean")
        if not isinstance(self.model, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", self.model):
            raise ValueError("semantic.model must be a Hugging Face owner/model ID")
        if not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise ValueError("semantic.revision must be an immutable 40-character commit hash")
        for name, low, high in (("dimensions", 1, 65536), ("max_tokens", 16, 8192),
                                ("default_limit", 1, 100), ("batch_size", 1, 256)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"semantic.{name} must be an integer from {low} to {high}")
        for name in ("query_prefix", "passage_prefix"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > 100:
                raise ValueError(f"semantic.{name} must be a string of at most 100 characters")
