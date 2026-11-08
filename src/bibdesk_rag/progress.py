"""Terminal-only indexing progress and bounded dependency diagnostics."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import logging
import shutil
import sys
import time
from typing import TYPE_CHECKING, TextIO
import warnings

if TYPE_CHECKING:
    from .indexer import IndexProgress


LABEL_WIDTH = 15
BAR_WIDTH = 20
MODEL_BAR_FORMAT = (
    f"{{desc:<{LABEL_WIDTH}}} [{{bar:{BAR_WIDTH}}}] {{percentage:3.0f}}% | {{n_fmt}}/{{total_fmt}}"
)
_active_progress: ContextVar[IndexProgressBar | None] = ContextVar("index_progress", default=None)


@contextmanager
def model_loading_progress():
    """Style the optional loader's real progress within a CLI indexing operation.

    The context also suppresses dependency bars for JSON, pipes and --no-progress.
    Imports remain lazy, and dependency state is restored even when loading fails.
    """
    progress = _active_progress.get()
    if progress is None:
        yield
        return
    # Finish the reading line before imports can emit dependency diagnostics.
    progress.finish_line()
    from transformers.utils import logging as transformers_logging

    def options(kwargs):
        return dict(kwargs, file=progress.stream, ascii="-#", leave=True,
                    dynamic_ncols=True, position=0, mininterval=0.1,
                    bar_format=MODEL_BAR_FORMAT,
                    disable=not progress.enabled or bool(kwargs.get("disable")))

    def hook(factory, args, kwargs):
        return factory(*args, **options(kwargs))

    setter = getattr(transformers_logging, "set_tqdm_hook", None)
    if setter is not None:
        previous = setter(hook)
        try:
            yield
        finally:
            setter(previous)
    else:
        # Older supported Transformers versions predate set_tqdm_hook. Their
        # existing tqdm wrapper delegates to this class, including imported refs.
        tqdm_lib = transformers_logging.tqdm_lib
        original = tqdm_lib.tqdm

        class StyledTqdm(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **options(kwargs))

        tqdm_lib.tqdm = StyledTqdm
        try:
            yield
        finally:
            tqdm_lib.tqdm = original


def single_line(value: str, limit: int = 180) -> str:
    """Keep untrusted source diagnostics from controlling the terminal."""
    text = " ".join("".join(c if c.isprintable() else " " for c in value).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class IndexProgressBar:
    """Refresh one stderr line; never put terminal controls in a data stream."""

    def __init__(self, *, enabled: bool, stream: TextIO | None = None):
        self.enabled = enabled
        self.stream = stream if stream is not None else sys.stderr
        self._width = 0
        self._phase = ""
        self._last_update = 0.0

    def __enter__(self) -> IndexProgressBar:
        self._token = _active_progress.set(self)
        return self

    def update(self, event: IndexProgress) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if event.phase == self._phase and now - self._last_update < 0.1:
            return
        self._last_update = now
        self._phase = event.phase
        if event.phase == "reading":
            line = "Reading bibliography..."
        elif event.phase == "embedding":
            line = "Embedding title/abstract on local CPU..."
        elif event.phase == "committing":
            line = "Saving index..."
        else:
            total = event.papers_total + event.files_total
            completed = event.papers_done + event.files_done
            percent = min(99, int(100 * completed / total)) if total else 0
            if event.phase == "done":
                percent = 100
            filled = percent * BAR_WIDTH // 100
            bar = "#" * filled + "-" * (BAR_WIDTH - filled)
            label = "Indexed" if event.phase == "done" else "Indexing"
            line = (
                f"{label:<{LABEL_WIDTH}} [{bar}] {percent:3d}% | "
                f"files {event.files_done}/{event.files_total}, "
                f"papers {event.papers_done}/{event.papers_total}"
            )
        self._write(line)

    def _write(self, line: str) -> None:
        # Leave one column unused so the terminal does not wrap into a new line.
        columns = max(1, shutil.get_terminal_size(fallback=(80, 24)).columns - 1)
        line = line[:columns]
        padding = " " * max(0, min(self._width, columns) - len(line))
        self.stream.write("\r" + line + padding)
        self.stream.flush()
        self._width = len(line)

    def finish_line(self) -> None:
        if self.enabled and self._width:
            self.stream.write("\n")
            self.stream.flush()
            self._width = 0

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if self.enabled and self._width and exc_type is not None:
                self._write("Indexing stopped; operation did not finish.")
            self.finish_line()
        finally:
            _active_progress.reset(self._token)


class IndexDiagnostics(logging.Handler):
    """Capture noisy parser output only during one CLI indexing operation.

    Store at most three short examples, regardless of the library size. Fatal
    exceptions and the indexer's attachment issues are handled separately.
    Verbose mode preserves the original dependency output instead.
    """

    LOGGER_NAMES = ("pypdf", "bibtexparser", "bibdeskparser", "pylatexenc", "openpyxl")
    SAMPLE_LIMIT = 3

    def __init__(self, *, verbose: bool = False, stream: TextIO | None = None):
        super().__init__(level=logging.WARNING)
        self.verbose = verbose
        self.stream = stream if stream is not None else sys.stderr
        self.count = 0
        self.samples: list[str] = []
        self._loggers: list[tuple[logging.Logger, list, bool, int]] = []

    def _record(self, message: str) -> None:
        self.count += 1
        if len(self.samples) < self.SAMPLE_LIMIT:
            text = single_line(message)
            if text not in self.samples:
                self.samples.append(text)

    def emit(self, record: logging.LogRecord) -> None:
        self._record(f"{record.name}: {record.getMessage()}")

    def _warning(self, message, category, filename, lineno, file=None, line=None) -> None:
        self._record(f"{category.__name__}: {message}")

    def __enter__(self) -> IndexDiagnostics:
        if not self.verbose:
            self._warnings = warnings.catch_warnings()
            self._warnings.__enter__()
            warnings.showwarning = self._warning
            for name in self.LOGGER_NAMES:
                logger = logging.getLogger(name)
                self._loggers.append((logger, logger.handlers[:], logger.propagate, logger.level))
                logger.handlers = [self]
                logger.propagate = False
                logger.setLevel(logging.WARNING)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.verbose:
            for logger, handlers, propagate, level in self._loggers:
                logger.handlers = handlers
                logger.propagate = propagate
                logger.setLevel(level)
            self._warnings.__exit__(exc_type, exc, traceback)
            if self.count:
                print(f"Parser diagnostics: {self.count} warning/error messages.", file=self.stream)
                for sample in self.samples:
                    print(f"  {sample}", file=self.stream)
                print("Use --verbose to see parser diagnostics as they occur.", file=self.stream)
        self.close()
