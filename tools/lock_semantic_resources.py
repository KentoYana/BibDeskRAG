#!/usr/bin/env python3
"""Explicitly lock PyPI-verified Apple Silicon semantic wheels for offline Homebrew install.

Run from the tested project venv with the semantic extra installed. This is a
maintainer operation, never called by setup, indexing, search or MCP.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = json.loads((ROOT / 'packaging/homebrew/resources.json').read_text())
    base_versions = {item['name']: item['version'] for item in base['resources']}
    destination = ROOT / 'packaging/homebrew/build-resources.json'
    lock = json.loads(destination.read_text())
    versions = {}
    pending = [Requirement('numpy>=1.26,<3'), Requirement('sentence-transformers>=5.1,<6')]
    seen = set()
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        key = name, tuple(sorted(requirement.extras))
        if key in seen:
            continue
        seen.add(key)
        installed = distribution(name)
        selected = base_versions.get(name, installed.version)
        if selected not in requirement.specifier:
            raise ValueError(f'{name}=={selected} does not satisfy {requirement}')
        if name not in base_versions:
            versions[name] = selected
        for value in installed.requires or []:
            dep = Requirement(value)
            for extra in requirement.extras or ('',):
                env = default_environment()
                env.update(python_version='3.14', python_full_version='3.14.10', extra=extra,
                           platform_system='Darwin', sys_platform='darwin', platform_machine='arm64')
                if dep.marker is None or dep.marker.evaluate(env):
                    pending.append(dep)
                    break
    records = []
    cache = ROOT / '.build-wheels'
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bibdesk-semantic-wheels-') as temporary:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--no-deps',
                        '--only-binary=:all:', '--platform', 'macosx_14_0_arm64',
                        '--python-version', '3.14', '--abi', 'cp314', '--abi', 'abi3',
                        '--implementation', 'cp', '--dest', temporary,
                        *[f'{name}=={version}' for name, version in sorted(versions.items())]],
                       check=True)
        for path in sorted(Path(temporary).glob('*.whl')):
            name, version, _, _ = parse_wheel_filename(path.name)
            with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=60) as r:
                metadata = json.load(r)
            source = next(item for item in metadata['urls'] if item['filename'] == path.name)
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != source['digests']['sha256']:
                raise ValueError(f'PyPI checksum mismatch: {path.name}')
            (cache / path.name).write_bytes(data)
            records.append(dict(name=name, version=str(version), filename=path.name,
                                url=source['url'], sha256=digest, semantic_runtime=True,
                                license=metadata['info'].get('license_expression')
                                or metadata['info'].get('license')))
    original = [dict(item) for item in lock['resources'] if not item.get('semantic_only')]
    for item in original:
        item.pop('semantic_runtime', None)
    merged = {item['filename']: item for item in original}
    for item in records:
        if item['filename'] in merged:
            assert merged[item['filename']]['sha256'] == item['sha256']
            merged[item['filename']]['semantic_runtime'] = True
        else:
            item['semantic_only'] = True
            merged[item['filename']] = item
    lock['resources'] = [merged[name] for name in sorted(merged)]
    lock['semantic_platform'] = 'macosx_14_0_arm64'
    destination.write_text(json.dumps(lock, indent=2) + '\n')
    print(f'Locked {len(records)} semantic wheels; shared offline bundle: {destination}')


if __name__ == '__main__':
    main()
