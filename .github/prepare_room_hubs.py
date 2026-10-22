"""Reproduce the exact room-hub candidate; removed from the final tree."""
from pathlib import Path
import base64
import hashlib
import lzma
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = '9ca2e689929b62b4f42bac3e7d83962c209de10b'
BASE_TREE = '79ea0aa8c0af26ce54f796f3759fedc83766a555'
TREE = 'e39873294b1c74e12d3db43faa51454563531e98'
PARTS = '.github/room-hubs-transfer'
STAGING = {f'{PARTS}/{i}.txt' for i in range(3)} | {
    '.github/prepare_room_hubs.py', '.github/workflows/prepare-room-hubs.yml'}


def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data,
                          check=True, capture_output=True).stdout


def main():
    if git('rev-parse', BASE+'^{tree}').decode().strip() != BASE_TREE:
        raise RuntimeError('Unexpected source baseline')
    changed = set(git('diff', '--name-only', BASE, 'HEAD').decode().splitlines())
    if changed != STAGING or git('status', '--porcelain').strip():
        raise RuntimeError('Stage must contain only the pinned transfer in a clean checkout')
    data = ''.join((ROOT / PARTS / f'{i}.txt').read_text() for i in range(3))
    if len(data) != 35744:
        raise RuntimeError('Incomplete transfer')
    patch = lzma.decompress(base64.b64decode(data, validate=True))
    if len(patch) != 104796 or hashlib.sha256(patch).hexdigest() != 'abfe697e4b80f21399dbb62f8045210524297532bc39da393968b7a08266d1ed':
        raise RuntimeError('Source patch checksum mismatch')
    git('apply', '--check', '--index', '-', data=patch)
    git('apply', '--index', '-', data=patch)
    git('rm', '-r', *sorted(STAGING))
    subprocess.run([sys.executable, 'generate_translations.py'], cwd=ROOT, check=True)
    git('add', '-A')
    actual = git('write-tree').decode().strip()
    if actual != TREE:
        raise RuntimeError(f'Candidate tree mismatch: {actual} != {TREE}')
    git('diff', '--exit-code')
    print('Exact room-hub source tree verified:', actual)


if __name__ == '__main__':
    main()
