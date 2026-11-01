#!/usr/bin/env python3
"""Render the unreleased Formula template with verified, immutable source inputs."""
from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from check_release import check_sdist

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Semantic version, without v")
    parser.add_argument("--homepage", required=True, help="Actual project homepage")
    parser.add_argument("--url", help="Published immutable HTTPS sdist URL")
    parser.add_argument("--sha256", help="Expected SHA-256 for --url; verified by downloading")
    parser.add_argument("--local-sdist", type=Path, help="Local-only installation test archive")
    parser.add_argument("--local-build-wheels", type=Path, help="Local build-backend bundle")
    parser.add_argument("--build-wheels-url", help="Published immutable HTTPS backend bundle URL")
    parser.add_argument("--build-wheels-sha256", help="Expected backend bundle SHA-256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", args.version):
        parser.error("--version must be a semantic version")
    if not args.homepage.startswith("https://"):
        parser.error("--homepage must be the actual HTTPS project homepage")
    if args.local_sdist:
        if args.url or args.sha256:
            parser.error("--local-sdist cannot be combined with --url/--sha256")
        source = args.local_sdist.resolve(strict=True)
        url = source.as_uri()
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            try:
                check_sdist(stream, args.version)
            except (ValueError, KeyError, tarfile.TarError) as error:
                parser.error(f"invalid sdist: {error}")
    else:
        if not args.url or not args.sha256:
            parser.error("provide --local-sdist or both --url and --sha256")
        if not args.url.startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", args.sha256):
            parser.error("a fixed HTTPS URL and lowercase 64-digit SHA-256 are required")
        url, digest = args.url, args.sha256
        with tempfile.TemporaryFile() as source:
            with urllib.request.urlopen(url, timeout=60) as response:
                while block := response.read(1024 * 1024):
                    source.write(block)
            source.seek(0)
            actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != digest:
                parser.error(f"source SHA-256 mismatch: expected {digest}, got {actual}")
            try:
                check_sdist(source, args.version)
            except (ValueError, KeyError, tarfile.TarError) as error:
                parser.error(f"invalid sdist: {error}")
    if args.local_build_wheels:
        if not args.local_sdist or args.build_wheels_url or args.build_wheels_sha256:
            parser.error("--local-build-wheels requires --local-sdist and no published bundle URL")
        build_source = args.local_build_wheels.resolve(strict=True)
        build_url = build_source.as_uri()
        with build_source.open("rb") as stream:
            build_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    else:
        build_url, build_digest = args.build_wheels_url, args.build_wheels_sha256
        if not build_url or not build_url.startswith("https://") or not build_digest:
            parser.error("provide --local-build-wheels or --build-wheels-url and --build-wheels-sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", build_digest):
            parser.error("invalid build bundle SHA-256")
        with urllib.request.urlopen(build_url, timeout=60) as response:
            if hashlib.file_digest(response, "sha256").hexdigest() != build_digest:
                parser.error("build bundle SHA-256 mismatch")
    for value in (args.homepage, url, build_url):
        if any(c in value for c in ('"', "\\", "\n", "\r", "#{")):
            parser.error("URLs contain characters unsafe in a Ruby string")
    template = (ROOT / "packaging/homebrew/Formula/bibdesk-rag.rb").read_text()
    for key, value in {
        "@@HOMEPAGE@@": args.homepage,
        "@@URL@@": url,
        "@@SHA256@@": digest,
        "@@VERSION@@": args.version,
        "@@BUILD_URL@@": build_url,
        "@@BUILD_SHA256@@": build_digest,
    }.items():
        template = template.replace(key, value)
    template = "\n".join(line for line in template.splitlines()
                         if "# TEMPLATE:" not in line and "disable!" not in line) + "\n"
    template = re.sub(r"\n{3,}", "\n\n", template)
    if re.search(rf"[-_]{re.escape(args.version)}\.tar\.(?:gz|bz2|xz)$", url.rsplit("/", 1)[-1]):
        template = template.replace(f'  version "{args.version}"\n', "", 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template)
    print(f"Wrote {args.output}; source SHA-256 {digest}")


if __name__ == "__main__":
    main()
