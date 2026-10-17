# Releasing Air Quality Advisor

**First public GitHub/HACS release:** v0.1.8. Earlier 0.1.x changelog entries are development milestones and were not individually tagged.

## v0.2.0 language checks

- Run the translation generator and ensure shipped JSON files do not change.
- Verify all 38 Home Assistant BCP47 language files, fallback tags, speech placeholders and RTL card layouts.
- Check regional Portuguese and Chinese script handling and sampled spoken messages.
- All configuration/Options errors now have localized text, with concise messages for the 33 newer languages; native-speaker review is welcome.

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

## v0.2.3 repeat reminders and manual-only workflow checks

- Reconfigure → Announcements: a number selector with default 10, minimum 0, maximum 1440; reject fractional, negative and non-numeric values. Setting 0 disables repeats entirely.
- Test repeated open and urgent close recommendations, multiple rooms, numeric fluctuations, reason changes, disappearing/recovered conditions, startup behavior, cooldown bypass and clean cancellation on unload.
- Ensure reminders are emitted only for automatic notification/TTS channels, and each repeat reuses normal Announcement Hub/AI/direct delivery without overlapping calls.
- Verify the workflow has **only `workflow_dispatch`**, no push/PR/schedule triggers. The **Publish release** boolean is false by default; it must be explicitly enabled after every file is pushed to `main`.
- Check all 38 translations and independent menu settings; verify one live 10-minute repeat and one case where the window is opened before the next deadline.

## v0.2.4 complete configuration localization audit

- Generate translations with `python generate_translations.py`, then ensure `git diff --exit-code -- custom_components/air_quality_advisor/strings.json custom_components/air_quality_advisor/translations` reports no generated changes.
- Run `python -m pytest -q tests/test_config_i18n_audit.py`. All 38 languages must contain identical keys and no remaining English-identical config/option prose or errors.
- Verify the Greek Weather/warnings screen and the 18 translated Greek threshold labels visually, along with samples in German, French, Spanish and extra languages.
- Verify the `SelectSelector` `translation_key="output_language"` and localized `selector.output_language.options.auto` work for each HA frontend user language, independent of the server default.
- User-assigned sensor names, area names and provider-specific weather-warning names remain unchanged. These are dynamic data, not integration UI strings.
- Push all files before launching GitHub Actions. The workflow must remain **manual-only**, with publish disabled by default.

## Verification gates

The repository's `.github/workflows/validate.yml` runs **exclusively on manual dispatch** (`workflow_dispatch`). No push, pull request, tag, release-request change or schedule starts any Actions. The default run validates only; release publication requires explicitly checking **Publish release**. Checks:

1. `python -m pytest -q tests` and `python -m compileall -q custom_components`.
2. `node --check custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js` and `node tests/card_test.cjs`.
3. JSON, HACS manifest, Home Assistant minimum version and brand checks.
4. HACS Action (`hacs/action@main`) and Hassfest (`home-assistant/actions/hassfest@master`).

A failed check **prevents release publication**.

## Release process — manual after the full push

1. Finish *all* source, UI translations, tests, README, changelog and `.github/releases/v<VERSION>.md` changes in one commit or series of development commits.
2. Set the manifest version and matching `.github/release-request.json` metadata version. **This file no longer triggers any workflow.**
3. Push everything to `main`. Verify the branch head and ensure nobody else is still pushing.
4. Open **GitHub → Actions → [Validate and release (on demand)](https://github.com/Chreece/HA-Air-Quality-Advisor/actions/workflows/validate.yml) → Run workflow**, choose branch `main`. Leave **Publish release = false** for a validation-only run, or turn it **on** to publish the new HACS release automatically **only if every check passes**.
5. Confirm the test, HACS and Hassfest jobs succeeded. When publishing was requested, confirm the `v<VERSION>` tag points to the validated commit and the GitHub Release includes the installation ZIP and changelog.
6. If a test fails, push a correction, then manually run the workflow again. Never assume a development push or changing the version automatically launches Actions.

A manual run with Publish release disabled cannot publish any release. A failed validation cannot publish a release. Existing installed versions remain available through HACS while a new version waits for its manual run.

Live Home Assistant setup, sensor integration and physical Announcement Hub/TTS/notification output tests remain separate acceptance requirements. The integration never operates windows.

**GitHub About metadata:** HACS Action currently ignores only the missing `description` and `topics` checks. Add a repository description/topics and remove this exception before any default HACS catalog application.
