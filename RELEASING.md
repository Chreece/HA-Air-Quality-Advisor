# Releasing Air Quality Advisor

**First public GitHub/HACS release:** v0.1.8. Earlier 0.1.x changelog entries are development milestones and were not individually tagged.

## v0.2.0 language checks

- Run the translation generator and ensure shipped JSON files do not change.
- Verify all 38 Home Assistant BCP47 language files, fallback tags, speech placeholders and RTL card layouts.
- Check regional Portuguese and Chinese script handling and sampled spoken messages.
- Some uncommon configuration error details still use English fallback pending native-speaker review.

## v0.2.1 optional AI checks

- Verify the Announcements editor offers an opt-in AI checkbox and a single-agent selector with Home Assistant default preselected.
- Confirm every agent choice originates from a `conversation.*` entity (except the default option), and that stale saved selections can be changed.
- Test direct notification and TTS message rewriting with the same text; configured Announcement Hub must bypass the AI call.
- Test `conversation.process` errors, no agent, empty replies, added numbers, changed windows/rooms, wrong action, agent tool-action response and eight-second timeout. All failures must return the original message.
- Run translation generation and check the extra field keys across all 38 languages. Verify real delivery against configured HA conversation agents; do not claim physical TTS/notifier success from unit tests.
- Warn that conversation agents with exposed HA actions might execute tool calls; text-only usage is requested but cannot be enforced by this integration.

## v0.2.2 shared AI and delivery fallback checks

- Confirm **Use AI for announcements** appears once and retains the saved value and existing conversation agent.
- With a configured running Announcement Hub, submit `notify.announcement_hub` with explicit `use_ai: true/false`, optional `ai_agent` and targeted room IDs.
- The Hub option must not appear when only an identically named `notify` action is installed; real `announcement_hub` config entry is required.
- Exercise stopped/unloaded Hub, rejected response, timeout and accepted job with no eligible outputs. Verify direct `notify.send_message` / `tts.speak` fallback followed by persistent notification if nothing succeeds.
- Avoid duplicate messages after an accepted queued Hub job; downstream output retries remain owned by Hub.
- Check the AI checkbox remains optional and off by default and that Hub AI does not cause an additional local AI rewrite.
- Run all 38 translation generation/schema tests and execute one manual Hub success plus one stopped-Hub fallback in a real HA instance before considering physical delivery validated.

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

**GitHub About metadata:** HACS Action currently ignores only the missing `description` and `topics` checks. Add a repository description/topics and remove this exception before any default HACS catalog application.
