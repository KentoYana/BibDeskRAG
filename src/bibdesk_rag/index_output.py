"""Bounded, terminal-safe warnings and summaries for index operations."""

from __future__ import annotations

import os
import re
import sys

from .progress import single_line


def _style(text, code, stream):
    if (sys.stdout.isatty() and sys.stderr.isatty() and stream.isatty()
            and os.environ.get("TERM") != "dumb" and "NO_COLOR" not in os.environ):
        return f"\033[{code}m{text}\033[0m"
    return text


def _description(message):
    """Explain known parser failures; retain original details in JSON/verbose."""
    if ": PdfReadError: More than one /FontFile found" in message:
        return (message.split(": PdfReadError:", 1)[0]
                + ": Could not extract text because of conflicting font definitions.")
    if ": LimitReachedError: Reached maximum number of tokens per stream" in message:
        return (message.split(": LimitReachedError:", 1)[0]
                + ": Could not extract text because the PDF parser reached its processing limit.")
    return message.replace(
        "no extractable text (possibly image-only; OCR not enabled)",
        "No extractable text; the page may contain only images or figures (OCR not enabled).",
    )


def _parser_description(message):
    if "Exceeded 5000 form XObject invocations" in message:
        return "Form XObject processing limit reached; some content was skipped."
    if "Token exceeds maximum length of 64 bytes" in message:
        return "PDF token length exceeded the parser limit."
    if "Ignoring wrong pointing object" in message:
        return "An invalid PDF object reference was ignored."
    return message


def print_index_warnings(result, diagnostics, *, verbose=False):
    stream = sys.stderr
    issues = result["errors"]
    if not issues and not diagnostics.count:
        return
    print(file=stream)
    print(_style("Warning", "1;33", stream), file=stream)
    print("Some attachments could not be fully indexed." if issues else
          "PDF or bibliography parsing produced warnings.", file=stream)
    print("If your searches are working as expected, you can ignore these warnings.", file=stream)
    print("Text that could not be extracted will not appear in full-text search results.",
          file=stream)
    if issues:
        print(file=stream)
        print(f"Attachment issues: {len(issues)} (this run; including partial extraction "
              "and unsupported formats).", file=stream)
        shown = issues if verbose else issues[:3]
        print(f"Showing {len(shown)} of {len(issues)}:", file=stream)
        for issue in shown:
            path = single_line(issue["path"], len(issue["path"]) if verbose else 180)
            print("  " + _style(path, "33", stream), file=stream)
            details = re.split(r"; (?=Page \d+:)", issue["error"])
            for message in details if verbose else details[:3]:
                text = message if verbose else _description(message)
                print("    " + single_line(text, len(text) if verbose else 180), file=stream)
            if not verbose and len(details) > 3:
                print(_style("    Additional details omitted.", "90", stream), file=stream)
    if diagnostics.count:
        print(file=stream)
        print(f"Parser diagnostics: {diagnostics.count} warning/error messages.", file=stream)
        for sample in diagnostics.samples:
            print("  • " + single_line(_parser_description(sample)), file=stream)
    print(file=stream)
    if issues:
        print(_style("Inspect an attachment: bibdesk-rag --paper attachments KEY --format json",
                     "90", stream), file=stream)
        print(_style("Use the same configuration; add --format json to an update for all issue details.",
                     "90", stream), file=stream)
    if not verbose:
        print(_style("Show full diagnostics during an update: add --verbose", "90", stream),
              file=stream)
    stream.flush()


def print_index_summary(result, label):
    stream = sys.stdout
    print()
    print(_style("Summary", "1;36", stream))
    print(_style(f"{label} complete.", "32", stream))
    print(f"  Papers:       {result['papers_added']} added, {result['papers_changed']} changed, "
          f"{result['papers_deleted']} deleted, {result['papers_renamed']} renamed.")
    print(f"  Attachments:  {result['files_extracted']} extraction attempts, "
          f"{result['files_reused']} reused, {result['files_hashed']} hashed.")
    if result["semantic"]["enabled"]:
        semantic = result["semantic"]
        print(f"  Semantic:     {semantic['embedded']} embedded, {semantic['reused']} reused, "
              f"{semantic['skipped']} skipped, {semantic['title_only']} title-only.")
    else:
        print("  Semantic:     disabled (no model loaded).")
