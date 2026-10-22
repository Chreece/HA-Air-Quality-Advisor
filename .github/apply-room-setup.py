"""Apply the checksum-pinned rooms-first source patch on the beta13 baseline.

This one-use transfer helper only edits repository source, tests and release
metadata. It is removed before validation and never calls Home Assistant.
"""
from pathlib import Path
import base64
import hashlib
import json
import lzma
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PARTS = '.github/room-setup-transfer'
SELF = '.github/apply-room-setup.py'
ALLOWED = {
    'apply_room_setup_i18n.py',
    'custom_components/air_quality_advisor/area_entities.py',
    'custom_components/air_quality_advisor/config_flow.py',
    'custom_components/air_quality_advisor/discovery.py',
    'custom_components/air_quality_advisor/environment.py',
    'custom_components/air_quality_advisor/equipment_model.py',
    'custom_components/air_quality_advisor/equipment_runtime.py',
    'custom_components/air_quality_advisor/manager.py',
    'custom_components/air_quality_advisor/mold_controls.py',
    'custom_components/air_quality_advisor/room_setup.py',
    'custom_components/air_quality_advisor/room_sources.py',
    'tests/test_area_config_flow.py', 'tests/test_discovery.py', 'tests/test_room_setup.py',
}


def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data,
                          check=True, capture_output=True).stdout


def main():
    if git('status', '--porcelain').strip():
        raise RuntimeError('Clean checkout required')
    component = ROOT / 'custom_components/air_quality_advisor'
    manifest = json.loads((component/'manifest.json').read_text())
    if manifest['version'] != '0.6.0b13' or manifest['integration_type'] != 'hub':
        raise RuntimeError('Expected the released beta13 room/device hierarchy')
    if {p.name for p in (ROOT/PARTS).iterdir()} != {f'{i}.txt' for i in range(4)}:
        raise RuntimeError('Unexpected transfer parts')
    encoded = ''.join((ROOT/PARTS/f'{i}.txt').read_text(encoding='ascii') for i in range(4))
    if len(encoded) != 30896:
        raise RuntimeError('Incomplete source transfer')
    patch = lzma.decompress(base64.b64decode(encoded, validate=True))
    if len(patch) != 87012 or hashlib.sha256(patch).hexdigest() != '2a0e5225874603fb22c976c01104e36604e25b5c2f45809355e1f5964d3aa560':
        raise RuntimeError('Source patch checksum mismatch')
    paths = {line.split(' b/', 1)[1] for line in patch.decode().splitlines() if line.startswith('diff --git ')}
    if paths != ALLOWED:
        raise RuntimeError('Unexpected source paths')
    git('apply', '--check', '--index', '-', data=patch)
    git('apply', '--index', '-', data=patch)
    generator = ROOT/'generate_translations.py'
    text = generator.read_text()
    if 'apply_room_setup_i18n' in text:
        raise RuntimeError('Source setup translation pass already exists')
    generator.write_text(text.rstrip() + '\n\n# Ordered rooms, explicit inputs and final general-source setup.\nfrom apply_room_setup_i18n import apply_room_setup_i18n\napply_room_setup_i18n(root)\n')
    manifest['version'] = '0.6.0b14'
    (component/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    request = json.loads((ROOT/'.github/release-request.json').read_text())
    request.update(version='0.6.0b14', channel='beta', release_branch='beta/v0.6.0b14',
        note='Rooms first, six explicit per-room multi-selects, general settings last; stable and physical hardware unchanged',
        changes=['One ordered initial/options flow ending with General settings',
                 'Per-room windows, air/environment, temperature, humidity, pressure and device selections with device/entity labels',
                 'Positive source filters govern monitoring and control feedback; explicit empty lists never rediscover inputs',
                 'Preserve Home/room/controller identities and operating entities; no implicit actuation permission',
                 'Final-submit-only persistence with concurrent change protection and all 38 language catalogs'])
    (ROOT/'.github/release-request.json').write_text(json.dumps(request, indent=2)+'\n')
    readme = ROOT/'README.md'
    text = readme.read_text().replace('v0.6.0b13', 'v0.6.0b14').replace('v0.6.0 beta 13 is available', 'v0.6.0 beta 14 is available')
    position = text.index('## Beta 13')
    section = ('## Beta 14 — Rooms, room inputs, general settings, done\n\n'
        '**Select monitored rooms → one page per selected room → General settings → Finish.** '
        'Each room page has six separate multi-selects: windows, air-quality/environmental sensors, '
        'temperature, humidity, pressure and climate/fan/humidity devices. Options show **device name — entity name**, '
        'plus the exact entity ID. All real HA areas are selectable, including rooms without windows.\n\n'
        'Setup then creates or retains the Home hub with general input/output entities and each selected room hub '
        'with its general settings/overview device and one managed controller per physical product. '
        'No further Climate or PID configuration menu is part of this route. Targets, presets, control methods '
        'and quiet settings stay on the managed devices. Selecting equipment does not authorize automatic power.\n\n'
        'Explicit source lists govern actual monitoring; empty means unused. Selected missing inputs remain '
        'unavailable instead of silently falling back. Qualified temperatures are normalized before averaging; '
        'selected pressure readings appear in room input diagnostics in hPa. Cancelling writes nothing, '
        'and the final save preserves unrelated concurrent settings. Existing IDs and tuning are retained.\n\n')
    readme.write_text(text[:position]+section+text[position:])
    changelog = ROOT/'CHANGELOG.md'
    changelog.write_text(changelog.read_text().replace('# Changelog\n', '# Changelog\n\n## 0.6.0b14 — Rooms-first setup and explicit input lists (beta)\n\n- Replace the public initial/options menu with rooms → per-room six-category multi-selects → general settings → finish.\n- Label inputs by physical device and entity; filter by real room/type and exclude generated controllers.\n- Apply positive source selection to monitoring, temperature/humidity feedback, windows and pressure diagnostics.\n- Preserve empty selections, invalid-source visibility, device identities, calibration/tuning and unrelated concurrent settings.\n- Withdraw affected automatic grants when feedback sources or rooms are removed; never authorize new devices implicitly.\n- Supply all 38 localized setup catalogs and regression/actual-HA selector checks.\n', 1))
    test = ROOT/'tests/test_beta_distribution.py'
    test.write_text(test.read_text().replace('0.6.0b13', '0.6.0b14').replace('beta 13', 'beta 14').replace('workflows/single-device-picker.yml', 'workflows/rooms-first-setup.yml'))
    test = ROOT/'tests/test_readme_assets.py'
    text = test.read_text()
    if '"v0.6.0b13")' not in text:
        raise RuntimeError('Unexpected README ref allowlist')
    test.write_text(text.replace('"v0.6.0b13")', '"v0.6.0b13", "v0.6.0b14")', 1))
    git('rm', '-r', PARTS, SELF)
    subprocess.run([sys.executable, 'generate_translations.py'], cwd=ROOT, check=True)
    git('add', '-A')
    if git('diff', '--cached', '--name-only', '--', '.github/workflows').strip():
        raise RuntimeError('Preparing source must not alter workflows')
    print('ROOM_SETUP_CANDIDATE_TREE='+git('write-tree').decode().strip())


if __name__ == '__main__':
    main()
