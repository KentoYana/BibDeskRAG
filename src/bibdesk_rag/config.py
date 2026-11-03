"""User-owned configuration, independent of Python and Homebrew installation paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import tomllib

from .extractors import ExtractionOptions


def config_directory() -> Path:
    """The user-owned directory containing the default config and selection."""
    if os.environ.get("BIBDESK_RAG_HOME"):
        return Path(os.environ["BIBDESK_RAG_HOME"]).expanduser().resolve()
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).expanduser().resolve() / "bibdesk-rag"
    return Path.home() / ".config/bibdesk-rag"


def active_config_path() -> Path:
    return config_directory() / "active-config.json"


def _selector_stat(path: Path) -> os.stat_result | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
        raise ValueError(f"Active configuration selection must be an owned, unlinked file: {path}")
    return info


def _read_selection(path: Path) -> tuple[Path | None, os.stat_result | None]:
    info = _selector_stat(path)
    if info is None:
        return None, None
    if info.st_size > 16384:
        raise ValueError(f"Active configuration selection is too large: {path}")
    try:
        with path.open("rb") as handle:
            content = handle.read(16385)
        if len(content) > 16384:
            raise ValueError("selection is too large")
        raw = json.loads(content)
        if (not isinstance(raw, dict) or set(raw) != {"version", "config"}
                or type(raw["version"]) is not int or raw["version"] != 1
                or not isinstance(raw["config"], str) or not raw["config"]
                or "\x00" in raw["config"] or not Path(raw["config"]).is_absolute()):
            raise ValueError("invalid selection format")
        selected = Path(raw["config"]).resolve()
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid active configuration selection: {path}") from exc
    return selected, info


def config_selection(path: Path | None = None) -> tuple[Path, str]:
    """Resolve selection without reading a library, opening SQLite, or writing files."""
    if path is not None:
        return path.expanduser().resolve(), "explicit"
    if os.environ.get("BIBDESK_RAG_CONFIG"):
        return Path(os.environ["BIBDESK_RAG_CONFIG"]).expanduser().resolve(), "BIBDESK_RAG_CONFIG"
    selected, _ = _read_selection(active_config_path())
    if selected is not None:
        if not selected.is_file():
            raise ValueError(
                f"Saved configuration is missing: {selected}. "
                "Choose an existing file with 'bibdesk-rag --config use PATH' or use --temp PATH."
            )
        return selected, "active"
    default = config_directory() / "config.toml"
    return default.resolve(), "default"


def resolve_config_path(path: Path | None = None) -> Path:
    return config_selection(path)[0]


def default_config_path() -> Path:
    """Return the effective default, including the remembered custom selection."""
    return resolve_config_path()


def default_data_dir(config_path: Path) -> Path:
    if os.environ.get("BIBDESK_RAG_HOME"):
        return Path(os.environ["BIBDESK_RAG_HOME"]).expanduser().resolve()
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]).expanduser().resolve() / "bibdesk-rag"
    if same_file(config_path, config_directory() / "config.toml"):
        return Path.home() / ".local/share/bibdesk-rag"
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
    path = resolve_config_path(path)
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


def _protect_selection(selector: Path, path: Path, config: Config, sources: list[Path]) -> None:
    config.protect_sources(sources, path)
    protected = [
        path, config.bib, config.database, *sources,
        *(Path(str(config.database) + suffix) for suffix in ("-journal", "-wal", "-shm")),
    ]
    if any(same_file(selector, source) for source in protected):
        raise ValueError("Active configuration selection overlaps a source, config, or database")


def check_output_locations(*paths: Path) -> None:
    """Keep persistent application state outside Python and Homebrew installations."""
    installations = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    for prefix in tuple(installations):
        for parent in (prefix, *prefix.parents):
            if parent.name == "Cellar":
                installations.add(parent.parent)
    if sys.platform == "darwin":
        installations.update((Path("/opt/homebrew"), Path("/usr/local")))
    if any(path.resolve().is_relative_to(prefix) for path in paths for prefix in installations):
        raise ValueError("Application state is inside a Python or Homebrew installation")


def activate_config(path: Path) -> Path:
    """Remember an explicitly selected config without changing it or its index."""
    path = resolve_config_path(path)
    config = load_config(path)
    selector = active_config_path()
    check_output_locations(path, config.database, selector)
    previous, previous_stat = _read_selection(selector)
    from .bibdesk import read_library

    papers = read_library(config.bib)
    _protect_selection(selector, path, config, [Path(ref.path) for p in papers for ref in p.files])
    if previous is not None and previous != path:
        # Protect sources linked by the currently selected library when they can
        # still be inspected, while allowing recovery from missing or invalid
        # previous configuration/library files. Collision errors must propagate.
        try:
            previous_config = load_config(previous)
            previous_papers = read_library(previous_config.bib)
        except (OSError, ValueError):
            pass
        else:
            _protect_selection(
                selector, previous, previous_config,
                [Path(ref.path) for paper in previous_papers for ref in paper.files],
            )
    content = json.dumps({"version": 1, "config": str(path)}, ensure_ascii=False) + "\n"
    if previous == path:
        return path
    selector.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=selector.parent,
            prefix=".active-config-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        current_stat = _selector_stat(selector)

        def identity(info: os.stat_result | None) -> tuple | None:
            if info is None:
                return None
            return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size

        if identity(current_stat) != identity(previous_stat):
            raise ValueError("Active configuration selection changed concurrently; retry --config use")
        os.replace(temporary, selector)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def init_config(bib: Path, path: Path | None = None, data_dir: Path | None = None) -> Path:
    path = resolve_config_path(path)
    bib = bib.expanduser().resolve(strict=True)
    if not bib.is_file():
        raise ValueError("--bib must refer to a file")
    data_dir = (data_dir or default_data_dir(path)).expanduser().resolve()
    config = Config(bib, data_dir / "index.sqlite3")
    selector = active_config_path()
    check_output_locations(path, config.database, selector)
    _read_selection(selector)
    # Parse first, also preventing a config path from overwriting any linked attachment.
    from .bibdesk import read_library

    papers = read_library(bib)
    _protect_selection(selector, path, config, [Path(ref.path) for p in papers for ref in p.files])
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    content = f"bib = {json.dumps(str(bib), ensure_ascii=False)}\ndatabase = {json.dumps(str(config.database), ensure_ascii=False)}\n\n[extraction]\n"
    content += "".join(f"{k} = {v}\n" for k, v in asdict(config.extraction).items())
    # Exclusive creation: never replace an existing user configuration.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)
    path.chmod(0o600)
    return path
