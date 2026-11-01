#!/usr/bin/env python3
"""Record downloaded backend wheels after verifying their public PyPI hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from packaging.utils import parse_wheel_filename


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_directory", type=Path)
    args = parser.parse_args()
    records = []
    for path in sorted(args.wheel_directory.glob("*.whl")):
        name, version, _, _ = parse_wheel_filename(path.name)
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as r:
            metadata = json.load(r)
        source = next(s for s in metadata["urls"] if s["filename"] == path.name)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != source["digests"]["sha256"]:
            raise ValueError(f"invalid SHA-256: {path}")
        info = metadata["info"]
        records.append(dict(name=name, version=str(version), filename=path.name, url=source["url"],
                            sha256=digest, license=info.get("license_expression") or info.get("license")))
    if not records:
        raise ValueError("no wheels")
    destination = Path(__file__).resolve().parents[1] / "packaging/homebrew/build-resources.json"
    destination.write_text(json.dumps({"python": "3.14", "resources": records}, indent=2) + "\n")
    print(f"Verified {len(records)} backend wheels; wrote {destination}")


if __name__ == "__main__":
    main()
