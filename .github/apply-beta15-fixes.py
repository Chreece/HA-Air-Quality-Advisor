"""Reproduce pinned beta15 source from exact, hashed line edits.

This staging-only helper is removed before validation/publication. It writes
repository source only and neither contacts HA nor changes any Git reference.
"""
from pathlib import Path
import base64
import hashlib
import json
import lzma
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PARTS = '.github/beta15-fixes-transfer'
SELF = '.github/apply-beta15-fixes.py'
TREE = 'b3a7f52047f643e1a8f7cd7be874c65814b3d56f'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    if git('status', '--porcelain').strip():
        raise RuntimeError('Clean source checkout required')
    manifest = json.loads((ROOT / 'custom_components/air_quality_advisor/manifest.json').read_text())
    if manifest['version'] != '0.6.0b14' or manifest['integration_type'] != 'hub':
        raise RuntimeError('Expected beta14 baseline')
    directory = ROOT / PARTS
    if {p.name for p in directory.iterdir()} != {f'{i}.txt' for i in range(4)}:
        raise RuntimeError('Unexpected transfer file list')
    encoded = ''.join((directory / f'{i}.txt').read_text(encoding='ascii') for i in range(4))
    if len(encoded) != 38908:
        raise RuntimeError('Incomplete transfer')
    raw = lzma.decompress(base64.b64decode(encoded, validate=True))
    if len(raw) != 95712 or hashlib.sha256(raw).hexdigest() != '1966996281ee30e382a52f841de10090326a2ee6480b6e4c9b9fbc2a7b603a06':
        raise RuntimeError('Candidate edits checksum mismatch')
    files = json.loads(raw)['files']
    if len(files) != 33 or len({f['path'] for f in files}) != len(files):
        raise RuntimeError('Unexpected candidate paths')
    for change in files:
        rel = Path(change['path'])
        if (rel.is_absolute() or '..' in rel.parts or '.git' in rel.parts
                or rel.as_posix().startswith('.github/workflows/')):
            raise RuntimeError('Unapproved source path')
        path = ROOT / rel
        if change['old_sha256'] is None:
            if path.exists():
                raise RuntimeError(f'Unexpected existing file: {rel}')
            new = change['content']
        else:
            old = path.read_bytes()
            if hashlib.sha256(old).hexdigest() != change['old_sha256']:
                raise RuntimeError(f'Changed source baseline: {rel}')
            lines = old.decode('utf-8').splitlines(keepends=True)
            cursor, output = 0, []
            for start, end, replacement in change['edits']:
                if not cursor <= start <= end <= len(lines):
                    raise RuntimeError('Invalid pinned line ranges')
                output.extend(lines[cursor:start])
                output.append(replacement)
                cursor = end
            output.extend(lines[cursor:])
            new = ''.join(output)
        result = new.encode('utf-8')
        if hashlib.sha256(result).hexdigest() != change['sha256']:
            raise RuntimeError(f'Reconstructed source mismatch: {rel}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result)
    git('rm', '-r', PARTS, SELF)
    subprocess.run([sys.executable, 'generate_translations.py'], cwd=ROOT, check=True)
    git('add', '-A')
    actual = git('write-tree').decode().strip()
    if actual != TREE:
        raise RuntimeError(f'Candidate tree mismatch: {actual} != {TREE}')
    git('diff', '--exit-code')
    print('EXACT_BETA15_TREE=' + actual)


if __name__ == '__main__':
    main()
