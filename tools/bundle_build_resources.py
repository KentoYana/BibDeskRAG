#!/usr/bin/env python3
"""Create a reproducible Homebrew build-backend bundle from verified locked wheels."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / ".build-wheels")
    args = parser.parse_args()
    lock_path = ROOT / "packaging/homebrew/build-resources.json"
    locked = json.loads(lock_path.read_text())
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(mode="w", fileobj=gz, format=tarfile.PAX_FORMAT) as archive:
            for item in locked["resources"]:
                path = args.cache / item["filename"]
                if not path.exists():
                    with urllib.request.urlopen(item["url"], timeout=60) as response:
                        path.write_bytes(response.read())
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != item["sha256"]:
                    raise ValueError(f"SHA-256 mismatch for {path}; remove the cached file and retry")
                info = tarfile.TarInfo("build-wheels/" + item["filename"])
                info.size = len(content)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
            content = lock_path.read_bytes()
            info = tarfile.TarInfo("build-wheels/manifest.json")
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
            for path in sorted((ROOT / "packaging/homebrew/licenses").glob("*.txt")):
                content = path.read_bytes()
                info = tarfile.TarInfo("build-wheels/licenses/" + path.name)
                info.size = len(content)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
    with args.output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(f"{digest}  {args.output}")


if __name__ == "__main__":
    main()
