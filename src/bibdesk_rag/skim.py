"""Open only server-resolved PDFs in Skim; paths are data, never script source."""

from importlib.resources import as_file, files
from pathlib import Path
import subprocess
import sys


def open_pdf(path: Path, page: int | None = None) -> dict:
    if page is not None and (type(page) is not int or not 1 <= page <= 1000000):
        raise ValueError("page must be a positive integer (at most 1000000)")
    if sys.platform != "darwin":
        raise ValueError("Opening PDFs in Skim requires macOS and Skim.")
    path = path.resolve()
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise ValueError("The linked PDF is missing or is not a regular PDF file. Run --index update after fixing the link in BibDesk.")
    try:
        subprocess.run(["/usr/bin/open", "-a", "Skim", str(path)], check=True,
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("Could not open the PDF in Skim. Check that Skim is installed and can open this file.") from None
    if page is None:
        return {"opened": True, "page_navigated": False, "message": "Opened in Skim."}
    try:
        resource = files("bibdesk_rag").joinpath("resources/web/skim-page.applescript")
        with as_file(resource) as script:
            subprocess.run(["/usr/bin/osascript", str(script), str(path), str(page)],
                           check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return {"opened": True, "page_navigated": False,
                "message": f"Opened in Skim, but could not navigate to page {page}. "
                f"Please go to physical PDF page {page}. Check macOS Automation permission for Skim."}
    return {"opened": True, "page_navigated": True,
            "message": f"Opened physical PDF page {page} in Skim."}
