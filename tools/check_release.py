#!/usr/bin/env python3
"""Check the three release archives offline, then write their SHA256SUMS."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import tomllib
from typing import BinaryIO
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {
    ".git", ".local", ".codex", ".agents", ".build-wheels", ".brew-cache",
    "__pycache__", ".pytest_cache", ".ruff_cache", "config.toml",
}
SOURCE_SUFFIXES = {".bib", ".pdf", ".csv", ".tsv", ".xlsx", ".xls"}


def check_path(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unsafe archive member: {name}")
    if any(part in PRIVATE_PARTS or part.startswith(".venv") for part in path.parts):
        raise ValueError(f"Private/generated archive member: {name}")
    if path.suffix in SOURCE_SUFFIXES or ".sqlite" in path.name or ".db" in path.suffixes:
        raise ValueError(f"Library/index data must not be distributed: {name}")
    if path.name.endswith((".pyc", ".pyo", ".db-wal", ".db-shm", ".db-journal")):
        raise ValueError(f"Generated archive member: {name}")


def check_metadata(raw: bytes, version: str) -> None:
    if len(raw) > 1_000_000:
        raise ValueError("Package metadata exceeds the inspection limit")
    metadata = BytesParser().parsebytes(raw, headersonly=True)
    names = metadata.get_all("Name", [])
    versions = metadata.get_all("Version", [])
    if names not in (["bibdesk-rag"], ["bibdesk_rag"]) or versions != [version]:
        raise ValueError(f"Expected bibdesk-rag {version}; found Name={names}, Version={versions}")


def tar_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members = {}
    for member in archive:
        check_path(member.name)
        if member.name in members or not (member.isfile() or member.isdir()):
            raise ValueError(f"Duplicate, linked or special archive member: {member.name}")
        members[member.name] = member
        if len(members) > 10_000:
            raise ValueError("Too many archive members")
    return members


def read_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    if not member.isfile() or member.size > 1_000_000:
        raise ValueError(f"Invalid package metadata member: {member.name}")
    with archive.extractfile(member) as stream:
        return stream.read()


def check_sdist(stream: BinaryIO, version: str) -> None:
    """Inspect names, release metadata and notices without extracting any files."""
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode="r:*") as archive:
        members = tar_members(archive)
        metadata = [name for name in members
                    if len(PurePosixPath(name).parts) == 2 and name.endswith("/PKG-INFO")]
        if len(metadata) != 1:
            raise ValueError("sdist must contain exactly one top-level PKG-INFO")
        root = metadata[0].rsplit("/", 1)[0]
        if any(PurePosixPath(name).parts[0] != root for name in members):
            raise ValueError("sdist must have a single package root")
        check_metadata(read_member(archive, members[metadata[0]]), version)
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml"):
            key = f"{root}/{name}"
            if key not in members or not members[key].isfile():
                raise ValueError(f"sdist is missing {name}")
        project = tomllib.loads(read_member(archive, members[f"{root}/pyproject.toml"]).decode())
        if project["project"]["name"] != "bibdesk-rag" or project["project"]["version"] != version:
            raise ValueError("sdist pyproject.toml does not match the requested release")


def check_wheel(path: Path, version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Wheel contains duplicate members")
        for name in names:
            check_path(name)
        prefix = f"bibdesk_rag-{version}.dist-info/"
        check_metadata(archive.read(prefix + "METADATA"), version)
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if prefix + "licenses/" + name not in names:
                raise ValueError(f"Wheel is missing {name}")


def check_backend_bundle(path: Path) -> None:
    lock_path = ROOT / "packaging/homebrew/build-resources.json"
    locked = json.loads(lock_path.read_text())
    expected = {"build-wheels/manifest.json": hashlib.sha256(lock_path.read_bytes()).hexdigest()}
    expected.update({"build-wheels/" + item["filename"]: item["sha256"]
                     for item in locked["resources"]})
    expected.update({"build-wheels/licenses/" + item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                     for item in (ROOT / "packaging/homebrew/licenses").glob("*.txt")})
    with tarfile.open(path) as archive:
        members = tar_members(archive)
        if set(members) != set(expected):
            raise ValueError("Backend bundle members differ from the locked wheels/notices")
        for name, digest in expected.items():
            with archive.extractfile(members[name]) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError(f"Backend bundle SHA-256 mismatch: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, required=True, help="Fresh release output directory")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    names = [f"bibdesk_rag-{version}.tar.gz", f"bibdesk_rag-{version}-py3-none-any.whl",
             "bibdesk-rag-build-wheels.tar.gz"]
    try:
        present = {path.name for path in args.dist_dir.iterdir()}
        if present - {"SHA256SUMS"} != set(names):
            raise ValueError("Use a fresh directory containing only this version's sdist, wheel and backend bundle")
        for name in names:
            path = args.dist_dir / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Expected a regular release file: {name}")
        with (args.dist_dir / names[0]).open("rb") as stream:
            check_sdist(stream, version)
        check_wheel(args.dist_dir / names[1], version)
        check_backend_bundle(args.dist_dir / names[2])
        lines = []
        for name in sorted(names):
            with (args.dist_dir / name).open("rb") as stream:
                lines.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {name}\n")
        output = args.dist_dir / "SHA256SUMS"
        if output.is_symlink():
            raise ValueError("Refusing to overwrite a symlinked checksum file")
        output.write_text("".join(lines))
    except (OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(f"Verified bibdesk-rag {version}: 3 archives; wrote {output}")


if __name__ == "__main__":
    main()
