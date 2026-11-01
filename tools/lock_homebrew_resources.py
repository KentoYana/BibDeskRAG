#!/usr/bin/env python3
"""Refresh verified runtime sdists from the installed, tested project environment.

Network access is explicit and only downloads public package metadata/source.
Run after pip install -e '.[dev]'. Review the resulting changes before release.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "packaging/homebrew/resources.json"


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    pending = [Requirement(value) for value in project["project"]["dependencies"]]
    seen: set[tuple[str, tuple[str, ...]]] = set()
    versions: dict[str, str] = {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        key = (name, tuple(sorted(requirement.extras)))
        if key in seen:
            continue
        seen.add(key)
        dist = importlib.metadata.distribution(name)
        if dist.version not in requirement.specifier:
            raise RuntimeError(f"installed {name}=={dist.version} does not satisfy {requirement}")
        versions[name] = dist.version
        for value in dist.requires or []:
            dependency = Requirement(value)
            active = dependency.marker is None
            for minor in (11, 12, 13, 14):
                for extra in requirement.extras or ("",):
                    env = default_environment()
                    env.update(python_version=f"3.{minor}", python_full_version=f"3.{minor}.0", extra=extra)
                    active |= dependency.marker is not None and dependency.marker.evaluate(env)
            if active:
                pending.append(dependency)
    records = []
    for name, version in sorted(versions.items()):
        metadata_url = f"https://pypi.org/pypi/{name}/{version}/json"
        with urllib.request.urlopen(metadata_url, timeout=60) as response:
            metadata = json.load(response)
        sources = [x for x in metadata["urls"] if x["packagetype"] == "sdist"]
        if len(sources) != 1:
            raise RuntimeError(f"expected exactly one sdist for {name}=={version}")
        source = sources[0]
        with urllib.request.urlopen(source["url"], timeout=60) as response:
            actual = hashlib.file_digest(response, "sha256").hexdigest()
        if actual != source["digests"]["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch for {name}=={version}")
        info = metadata["info"]
        records.append(dict(name=name, version=version, url=source["url"], sha256=actual,
                            license=info.get("license_expression") or info.get("license"),
                            metadata_url=metadata_url))
        print(f"Verified {name}=={version}", file=sys.stderr)
    LOCK.write_text(json.dumps({"python_minors": ["3.11", "3.12", "3.13", "3.14"],
                                "resources": records}, indent=2) + "\n")
    formula = ROOT / "packaging/homebrew/Formula/bibdesk-rag.rb"
    blocks = "\n\n".join(
        f'  resource "{r["name"]}" do\n    url "{r["url"]}"\n'
        f'    sha256 "{r["sha256"]}"\n  end' for r in records
    )
    formula.write_text(re.sub(
        r"  # BEGIN LOCKED RESOURCES\n.*?  # END LOCKED RESOURCES",
        "  # BEGIN LOCKED RESOURCES\n" + blocks + "\n  # END LOCKED RESOURCES",
        formula.read_text(), flags=re.DOTALL,
    ))
    print(f"Wrote {LOCK}")


if __name__ == "__main__":
    main()
