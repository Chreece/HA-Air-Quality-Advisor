"""Apply the reviewed menu patch and generate the beta13 candidate once.

Only repository source and metadata are edited. The helper and plain patch
are removed from the validated source commit; no physical HA instance is used.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCH = '.github/single-device-picker.patch'
SELF = '.github/apply-single-device-picker.py'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    if git('status', '--porcelain').strip():
        raise RuntimeError('A clean candidate checkout is required')
    component = ROOT / 'custom_components/air_quality_advisor'
    manifest = json.loads((component / 'manifest.json').read_text())
    if manifest['version'] != '0.6.0b12' or manifest['integration_type'] != 'hub':
        raise RuntimeError('Expected the published beta12 room-hub baseline')
    patch = (ROOT / PATCH).read_bytes()
    if hashlib.sha256(patch).hexdigest() != '09921f94bc2c109826f50332116a80d567eef43676ce0645ab51c5efb4876c62':
        raise RuntimeError('Reviewed source patch checksum mismatch')
    git('apply', '--check', PATCH)
    git('apply', PATCH)
    manifest['version'] = '0.6.0b13'
    (component / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    request = json.loads((ROOT / '.github/release-request.json').read_text())
    request.update(version='0.6.0b13', channel='beta', release_branch='beta/v0.6.0b13',
                   note='Single per-room physical climate-device picker; device-owned operating controls; no implicit actuation',
                   changes=['Remove separate Climate and Climate PID setup entry points',
                            'Group supported native endpoints by physical device in the room picker',
                            'Save inventory directly; keep optional sensor/hardware commissioning in the same path',
                            'Reconcile removed devices across legacy PID and native control with no permission inheritance',
                            'Retain room hubs, source identities, tuning and all 38 localized catalogs'])
    (ROOT / '.github/release-request.json').write_text(json.dumps(request, indent=2) + '\n')
    readme = ROOT / 'README.md'
    text = readme.read_text().replace('v0.6.0b12', 'v0.6.0b13').replace('v0.6.0 beta 12 is available', 'v0.6.0 beta 13 is available')
    heading = '## Beta 12'
    position = text.find(heading)
    if position < 0:
        position = text.index('\n## ', text.index('# Home Environment Manager for Home Assistant')) + 1
    section = ('## Beta 13 — One climate-device selection path\n\n'
               '**Configure → Area settings → Climate devices → room → physical devices → Save.** '
               'The separate Climate and Climate PID setup entries are removed. Saving creates the '
               'selected controller devices inside the room hub without a mandatory setup wizard. '
               'One physical product is one selector choice even when it exposes several native endpoints.\n\n'
               'Targets, presets, Automatic/Manual/Off/PID and quiet settings belong to the managed '
               'devices; general room settings remain on the room hub. The optional sensor/hardware '
               'commissioning checkbox continues in this same setup path. Selection is not an '
               'automatic-control grant. Deselecting a device also removes its old supervisory PID '
               'assignment without deleting tuning or changing other rooms. All 38 locales are included.\n\n')
    readme.write_text(text[:position] + section + text[position:])
    changelog = ROOT / 'CHANGELOG.md'
    changelog.write_text(changelog.read_text().replace('# Changelog\n', '# Changelog\n\n## 0.6.0b13 — Single per-room climate-device picker (beta)\n\n- Replace duplicate Climate/PID/device menus with one physical-device picker.\n- Save selection directly; optional sensor and hardware commissioning stays in the same path.\n- Keep operating controls on managed devices and room-wide controls on the room hub.\n- Preserve unavailable selected equipment and revoke deselected legacy PID assignments.\n- Prevent inherited/stale automation grants for newly selected endpoints; preserve tuning and other rooms.\n- Translate the new setup guidance in all 38 languages, including Greek.\n', 1))
    test = ROOT / 'tests/test_beta_distribution.py'
    test.write_text(test.read_text().replace('0.6.0b12', '0.6.0b13').replace('beta 12', 'beta 13').replace('workflows/validate.yml', 'workflows/single-device-picker.yml'))
    test = ROOT / 'tests/test_readme_assets.py'
    text = test.read_text()
    marker = '"v0.6.0b12")'
    if marker not in text:
        raise RuntimeError('Unexpected allowed README source refs')
    test.write_text(text.replace(marker, '"v0.6.0b12", "v0.6.0b13")', 1))
    git('rm', PATCH, SELF)
    subprocess.run([sys.executable, 'generate_translations.py'], cwd=ROOT, check=True)
    git('add', '-A')
    print('CANDIDATE_TREE=' + git('write-tree').decode().strip())


if __name__ == '__main__':
    main()
