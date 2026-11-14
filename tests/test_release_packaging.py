"""Release archives are synthetic; no library, network or Homebrew is accessed."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_checks", ROOT / "tools/check_release.py")
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


def write_tar(path, files):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def sdist_files(version="0.1.0"):
    root = f"bibdesk_rag-{version}"
    return {
        f"{root}/PKG-INFO": f"Name: bibdesk-rag\nVersion: {version}\n\n".encode(),
        f"{root}/pyproject.toml": f'[project]\nname = "bibdesk-rag"\nversion = "{version}"\n'.encode(),
        f"{root}/LICENSE": b"Synthetic MIT notice",
        f"{root}/THIRD_PARTY_NOTICES.md": b"Synthetic dependency notices",
        f"{root}/src/bibdesk_rag/__init__.py": f'__version__ = "{version}"\n'.encode(),
    }


def generate_formula(tmp_path, *, version="0.1.0", filename="bibdesk_rag-0.1.0.tar.gz"):
    source = tmp_path / filename
    write_tar(source, sdist_files())
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"synthetic backend bundle")
    output = tmp_path / "formula.rb"
    result = subprocess.run([
        sys.executable, str(ROOT / "tools/generate_formula.py"),
        "--version", version, "--homepage", "https://example.invalid/local-test",
        "--local-sdist", str(source), "--local-build-wheels", str(bundle),
        "--output", str(output),
    ], capture_output=True, text=True, check=False)
    return result, source, output


def test_formula_rejects_requested_version_not_in_sdist_without_overwriting(tmp_path):
    output = tmp_path / "formula.rb"
    output.write_text("keep prior Formula")
    result, _, _ = generate_formula(tmp_path, version="0.2.0")
    assert result.returncode != 0 and "Expected bibdesk-rag 0.2.0" in result.stderr
    assert output.read_text() == "keep prior Formula"


def test_formula_keeps_explicit_version_for_misleading_archive_name(tmp_path):
    result, source, output = generate_formula(tmp_path, filename="bibdesk_rag-0.1.01.tar.gz")
    assert result.returncode == 0, result.stderr
    formula = output.read_text()
    assert '  version "0.1.0"' in formula
    assert hashlib.sha256(source.read_bytes()).hexdigest() in formula
    assert "@@" not in formula and "disable!" not in formula


@pytest.mark.parametrize("raw", [
    b'__version__ = "9.9.9"',
    b'__version__ = __import__("os").environ["NEVER_EXECUTE"]',
    b'__version__ = "0.1.0"\n__version__ = "9.9.9"',
])
def test_runtime_version_mismatch_is_rejected_without_executing(raw):
    with pytest.raises(ValueError, match="Runtime"):
        checks.check_runtime_version(raw, "0.1.0")


def test_tag_must_match_exact_release():
    checks.check_tag(None, "0.5.0")
    checks.check_tag("v0.5.0", "0.5.0")
    for tag in ("v0.4.1", "0.5.0", "v0.5.0-extra"):
        with pytest.raises(ValueError, match="tag"):
            checks.check_tag(tag, "0.5.0")


def test_sdist_runtime_version_must_match_metadata(tmp_path):
    path = tmp_path / "source.tar.gz"
    files = sdist_files()
    files["bibdesk_rag-0.1.0/src/bibdesk_rag/__init__.py"] = b'__version__ = "9.9.9"'
    write_tar(path, files)
    with path.open("rb") as stream, pytest.raises(ValueError, match="Runtime"):
        checks.check_sdist(stream, "0.1.0")


@pytest.mark.parametrize("name", [".local/config.toml", "data/index.sqlite3", "library.bib",
                                 "paper.DOCX", "slides.key", "document.pages", "table.numbers",
                                 "paper.doc", "slides.pptx", "source.tex",
                                 ".venv/bin/python", "../outside"])
def test_sdist_rejects_private_data_and_escaping_members(tmp_path, name):
    path = tmp_path / "source.tar.gz"
    files = sdist_files()
    files["bibdesk_rag-0.1.0/" + name] = b"synthetic private fixture"
    write_tar(path, files)
    with path.open("rb") as stream, pytest.raises(ValueError):
        checks.check_sdist(stream, "0.1.0")


def test_sdist_requires_matching_pyproject_and_license_notices(tmp_path):
    path = tmp_path / "source.tar.gz"
    files = sdist_files()
    files["bibdesk_rag-0.1.0/pyproject.toml"] = b'[project]\nname="bibdesk-rag"\nversion="0.2.0"'
    write_tar(path, files)
    with path.open("rb") as stream, pytest.raises(ValueError, match="pyproject.toml"):
        checks.check_sdist(stream, "0.1.0")
    files = sdist_files()
    del files["bibdesk_rag-0.1.0/THIRD_PARTY_NOTICES.md"]
    write_tar(path, files)
    with path.open("rb") as stream, pytest.raises(ValueError, match="THIRD_PARTY_NOTICES"):
        checks.check_sdist(stream, "0.1.0")


def release_fixture(tmp_path, monkeypatch):
    root = tmp_path / "project"
    notices = root / "packaging/homebrew/licenses"
    notices.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nversion="0.1.0"\n')
    (notices / "backend.txt").write_text("synthetic MIT backend notice")
    wheel_bytes = b"synthetic backend wheel bytes"
    lock = {"resources": [{"filename": "backend-1.0-py3-none-any.whl",
                           "sha256": hashlib.sha256(wheel_bytes).hexdigest()}]}
    lock_path = root / "packaging/homebrew/build-resources.json"
    lock_path.write_text(json.dumps(lock))
    monkeypatch.setattr(checks, "ROOT", root)
    dist = tmp_path / "release"
    dist.mkdir()
    write_tar(dist / "bibdesk_rag-0.1.0.tar.gz", sdist_files())
    with zipfile.ZipFile(dist / "bibdesk_rag-0.1.0-py3-none-any.whl", "w") as archive:
        prefix = "bibdesk_rag-0.1.0.dist-info/"
        archive.writestr(prefix + "METADATA", "Name: bibdesk-rag\nVersion: 0.1.0\n\n")
        archive.writestr("bibdesk_rag/__init__.py", '__version__ = "0.1.0"\n')
        archive.writestr(prefix + "licenses/LICENSE", "synthetic MIT")
        archive.writestr(prefix + "licenses/THIRD_PARTY_NOTICES.md", "synthetic notices")
    write_tar(dist / "bibdesk-rag-build-wheels.tar.gz", {
        "build-wheels/manifest.json": lock_path.read_bytes(),
        "build-wheels/backend-1.0-py3-none-any.whl": wheel_bytes,
        "build-wheels/licenses/backend.txt": (notices / "backend.txt").read_bytes(),
    })
    monkeypatch.setattr(sys, "argv", ["check_release.py", "--dist-dir", str(dist)])
    return dist


def test_release_check_writes_only_three_verified_checksums_and_preserves_inputs(tmp_path, monkeypatch):
    dist = release_fixture(tmp_path, monkeypatch)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in dist.iterdir()}
    checks.main()
    lines = (dist / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 3
    assert {line.split("  ")[1]: line.split("  ")[0] for line in lines} == before
    assert all(hashlib.sha256((dist / name).read_bytes()).hexdigest() == digest
               for name, digest in before.items())


def test_stale_archive_is_rejected_without_replacing_existing_checksums(tmp_path, monkeypatch):
    dist = release_fixture(tmp_path, monkeypatch)
    (dist / "bibdesk_rag-0.0.1.tar.gz").write_bytes(b"stale archive")
    (dist / "SHA256SUMS").write_text("previous checksums")
    with pytest.raises(SystemExit):
        checks.main()
    assert (dist / "SHA256SUMS").read_text() == "previous checksums"


def test_backend_bundle_hash_mismatch_prevents_checksum_publication(tmp_path, monkeypatch):
    dist = release_fixture(tmp_path, monkeypatch)
    path = dist / "bibdesk-rag-build-wheels.tar.gz"
    with tarfile.open(path) as archive:
        files = {member.name: archive.extractfile(member).read() for member in archive}
    files["build-wheels/backend-1.0-py3-none-any.whl"] = b"changed backend wheel"
    write_tar(path, files)
    with pytest.raises(SystemExit):
        checks.main()
    assert not (dist / "SHA256SUMS").exists()
