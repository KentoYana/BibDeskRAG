"""User-owned configuration, independent of Python and Homebrew installation paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
import os
from pathlib import Path
import sys
import tomllib

from .extractors import ExtractionOptions


def default_config_path() -> Path:
    if os.environ.get("BIBDESK_RAG_CONFIG"):
        return Path(os.environ["BIBDESK_RAG_CONFIG"]).expanduser().resolve()
    if os.environ.get("BIBDESK_RAG_HOME"):
        return Path(os.environ["BIBDESK_RAG_HOME"]).expanduser().resolve() / "config.toml"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).expanduser() / "bibdesk-rag/config.toml"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/bibdesk-rag/config.toml"
    return Path.home() / ".config/bibdesk-rag/config.toml"


def default_data_dir(config_path: Path) -> Path:
    if os.environ.get("BIBDESK_RAG_HOME"):
        return Path(os.environ["BIBDESK_RAG_HOME"]).expanduser().resolve()
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]).expanduser().resolve() / "bibdesk-rag"
    return config_path.parent


def same_file(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))


@dataclass
class Config:
    bib: Path
    database: Path
    extraction: ExtractionOptions = field(default_factory=ExtractionOptions)

    def protect_sources(self, sources: list[Path], config_path: Path | None = None) -> None:
        outputs = [
            self.database,
            *(Path(str(self.database) + s) for s in ("-journal", "-wal", "-shm")),
        ]
        if config_path:
            if any(same_file(config_path, output) for output in outputs):
                raise ValueError("Configuration path overlaps the database or a SQLite sidecar")
            outputs.append(config_path)
        for source in sources:
            if any(same_file(source, output) for output in outputs):
                raise ValueError(f"Application output overlaps a source file: {source}")
        # The library is always protected, including before an index exists.
        if any(same_file(self.bib, output) for output in outputs):
            raise ValueError("Configuration/database must not overwrite the BibDesk library")


def load_config(path: Path | None = None) -> Config:
    path = (path or default_config_path()).expanduser().resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    unknown = set(raw) - {"bib", "database", "extraction"}
    if unknown:
        raise ValueError("Unknown configuration keys: " + ", ".join(sorted(unknown)))

    def resolve(key: str) -> Path:
        value = raw.get(key)
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ValueError(f"Configuration {key!r} must be a nonempty path string")
        candidate = Path(value).expanduser()
        return (candidate if candidate.is_absolute() else path.parent / candidate).resolve()

    extraction = raw.get("extraction", {})
    if not isinstance(extraction, dict):
        raise ValueError("Configuration 'extraction' must be a TOML table")
    unknown_options = set(extraction) - {item.name for item in fields(ExtractionOptions)}
    if unknown_options:
        raise ValueError("Unknown extraction options: " + ", ".join(sorted(unknown_options)))
    config = Config(resolve("bib"), resolve("database"), ExtractionOptions(**extraction))
    config.protect_sources([], path)
    return config


def init_config(bib: Path, path: Path | None = None, data_dir: Path | None = None) -> Path:
    path = (path or default_config_path()).expanduser().resolve()
    bib = bib.expanduser().resolve(strict=True)
    if not bib.is_file():
        raise ValueError("--bib must refer to a file")
    data_dir = (data_dir or default_data_dir(path)).expanduser().resolve()
    config = Config(bib, data_dir / "index.sqlite3")
    # Parse first, also preventing a config path from overwriting any linked attachment.
    from .bibdesk import read_library

    papers = read_library(bib)
    config.protect_sources([Path(ref.path) for p in papers for ref in p.files], path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    content = f"bib = {json.dumps(str(bib), ensure_ascii=False)}\ndatabase = {json.dumps(str(config.database), ensure_ascii=False)}\n\n[extraction]\n"
    content += "".join(f"{k} = {v}\n" for k, v in asdict(config.extraction).items())
    # Exclusive creation: never replace an existing user configuration.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)
    path.chmod(0o600)
    return path
