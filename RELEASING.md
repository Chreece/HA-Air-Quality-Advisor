# Releasing Air Quality Advisor

**First public GitHub/HACS release:** v0.1.8. Earlier 0.1.x changelog entries are development milestones and were not individually tagged.

## Verification gates

The repository's `.github/workflows/validate.yml` runs on manual dispatch or an explicit release-request change, not on every push, pull request or schedule. Checks:

1. `python -m pytest -q tests` and `python -m compileall -q custom_components`.
2. `node --check custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js` and `node tests/card_test.cjs`.
3. JSON, HACS manifest, Home Assistant minimum version and brand checks.
4. HACS Action (`hacs/action@main`) and Hassfest (`home-assistant/actions/hassfest@master`).

A failed check **prevents release publication**.

## Release process

1. Update the `version` in `custom_components/air_quality_advisor/manifest.json` and compatible HACS `hacs.json` minimum.
2. Update `CHANGELOG.md`, README, and `.github/releases/v<VERSION>.md` with current release notes.
3. Test locally; optionally trigger the manual validation action (manual runs never publish).
4. Commit an intentional update to `.github/release-request.json` containing `{"version":"<VERSION>"}` on `main`. This one file is the only automatic release trigger.
5. If **every** validation job passes, the workflow creates `v<VERSION>` pointing to the exact tested commit, a published GitHub Release with Markdown notes, and an optional integration-only ZIP.
6. Check that the published release (not just a tag) appears in HACS and the ZIP contains the correct manifest version and built-in dashboard card.

If checks fail, fix the issue and change the request file again for one new attempt. Leave normal development pushes quiet, and do not call failed releases published.

Live Home Assistant setup, sensor integration and physical Announcement Hub/TTS/notification output tests remain separate acceptance requirements. The integration never operates windows.
