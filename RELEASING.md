# Releasing Home Environment Manager

## v0.6.0b15 - Device settings and selector fixes

Publish only from `beta/v0.6.0b15` after the beta15 workflow validates Python
3.13/3.14, generated catalogs, frontend, Hassfest, HACS and three actual-HA
API checks (registry migration, wizard selectors, read-only settings/device
methods). Exact source SHA, prerelease and `--latest=false` are mandatory.
No prior release tag or main branch is updated.

## v0.6.0b12 — Native room grouping and registry migration

Publish the exact validated commit from `beta/v0.6.0b12`, marked prerelease and not Latest. Validate both Python versions, regenerated catalogs, frontend, pinned real Home Assistant registry migration, Hassfest/HACS and ZIP integrity. Preserve main, stable v0.5.1 and earlier tags. Installation migrates the service flags and room memberships in place; no user-run migration script or integration deletion is needed.

## v0.6.0b11 — Combined controller beta

Publish only from `beta/v0.6.0b11` after Python 3.13/3.14, deterministic
38-language generation (including `equipment_text.py`), frontend, Hassfest,
HACS and ZIP checks. Tag the exact validated source SHA once, mark prerelease
and `--latest=false`, and never move the old tags or stable/main branch.
The release includes all pending Area-hub/per-device-climate, method selector,
on/off-PID and quiet-mode software. Default method Existing prevents automatic
migration of equipment control; real hardware commissioning is still required.


## v0.6.0b10 — Source selection in setup and per-device tuning

Opt-in beta 10 is released only from `beta/v0.6.0b10` at the validated
commit. Area and Home configuration entities, manual measured mold calibration,
room sleep Time controls, native PID controls and 38-language generated labels
ship without changing stable v0.5.1 or earlier immutable beta tags. CI must
validate Python 3.13/3.14, generated translations, frontend, Hassfest, HACS and
the installation archive before publishing. Real hardware commissioning is
still required for experimental physical power or compressor controls.


## v0.6.0b5 — Complete initial/options help across 38 locales

The opt-in `beta/v0.6.0b5` HACS/GitHub prerelease is locked to its fully validated HEAD. All 38 locales have required data_description text for every visible initial-config or options field, including 22 advanced thresholds previously missing help. Reviewed English and Greek explanation texts cover exact controls and scientific caveats; the other 36 locale texts are localized with safety-aware templates. CI checks no untranslated labels, no missing help, reproducible translation generation, Python 3.13/3.14, frontend, Hassfest, HACS and the manual package. The integration's original `air_quality_advisor` domain, stored options, stable v0.5.1 and physical-control safety gates are unchanged.

## v0.6.0b4 — First-install retry recovery beta

This HACS-selectable prerelease is built from `beta/v0.6.0b4` and published **only after** the full Python 3.13/3.14, frontend, translation, Hassfest, HACS and installation ZIP checks pass. It removes the early unique-ID reservation that made a first-time dialog lost by the browser block retries as `already_in_progress`. The fixed `home` unique ID and existing-entry checks are enforced at final save, not removed. Stable `v0.5.1`, earlier betas, the internal domain and all hardware-safety permissions remain unchanged. A previous pending HA config flow can be cleared by restarting only Home Assistant after the HACS update.

## v0.6.0b3 — Measurement help and useful-source selector beta

This opt-in HACS prerelease is published from the isolated `beta/v0.6.0b3` branch only after Python 3.13 and 3.14, generated 38-language translations, Node.js frontend tests, Hassfest, HACS validation and ZIP integrity succeed. It adds contextual measurement info, fresh/valid occupied and sleep-room selector choices and corrected Greek form guidance. Stable v0.5.1 and existing tags remain unchanged. The GitHub release is explicitly marked prerelease and never Latest. The ZIP is for manual installation; HACS reads the matching tagged source tree.

## v0.6.0b2 — Compact options and international device occupancy beta

Version `v0.6.0b2` is the next HACS-selectable **prerelease**, created from
`beta/v0.6.0b2` at its validated HEAD. GitHub Latest remains stable `v0.5.1`
and the first `v0.6.0b1` tag is immutable. HACS uses the tagged source tree
(`custom_components/air_quality_advisor`); the attached ZIP is for manual
installation. The validation workflow gates publication on Python 3.13/3.14,
full translations, frontend tests, Hassfest, HACS checks, and package smoke
tests. This beta does not merge the experimental branch to `main`.

See the beta README for grouped Outside data / General / Area settings,
device-by-device commissioning and occupancy/sleep input formats. Unknown
state/attribute data never authorizes an absence OFF. Native AC compressor
and electrical safety are still the responsibility of independently
commissioned hardware, never of these software tests.

## v0.6.0b1 opt-in HACS beta (no stable-branch merge)

The first 0.6 preview publishes from `beta/v0.6.0b1` as the GitHub **prerelease** tag `v0.6.0b1`, with the same `0.6.0b1` manifest version. The beta workflow is branch- and version-locked and runs the Python 3.13/3.14 tests, generated translations, frontend, Hassfest, HACS checks and package smoke test **before** creating the release. It pins the tag to the validated exact Git SHA, never retags/overwrites it, and uses `--prerelease --latest=false` so v0.5.1 remains stable/latest.

The existing `hacs.json` intentionally uses HACS's supported release-tag source-tree installation from `custom_components/air_quality_advisor/` rather than `zip_release`. Changing `zip_release` retroactively could strand v0.5.1 installs whose assets had different names. The attached ZIP is **for manual installation only**; its contents are verified to begin at `custom_components/air_quality_advisor/`, include the manifest and Home Assistant brand PNGs, and exclude bytecode/cache files.

For HACS beta testers: Add this repository as a custom **Integration**, open its entry, choose Redownload/version selection and enable **Show beta versions** before choosing `v0.6.0b1`; then restart HA. If the beta isn't selectable, use the manual ZIP from the release page. Users must back up before changing a major controller branch and may choose stable `v0.5.1` again. Experimental power and compressor-mode controls require independently commissioned real hardware; CI alone cannot grant hardware approval.

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

## v0.2.3 repeat reminders and original release workflow checks

- Reconfigure → Announcements: a number selector with default 10, minimum 0, maximum 1440; reject fractional, negative and non-numeric values. Setting 0 disables repeats entirely.
- Test repeated open and urgent close recommendations, multiple rooms, numeric fluctuations, reason changes, disappearing/recovered conditions, startup behavior, cooldown bypass and clean cancellation on unload.
- Ensure reminders are emitted only for automatic notification/TTS channels, and each repeat reuses normal Announcement Hub/AI/direct delivery without overlapping calls.
- Historical note: v0.2.3 introduced manual release dispatch; v0.2.4 supersedes it with automatic post-push validation and release.
- Check all 38 translations and independent menu settings; verify one live 10-minute repeat and one case where the window is opened before the next deadline.

## v0.2.4 complete configuration localization audit

- Generate translations with `python generate_translations.py`, then ensure `git diff --exit-code -- custom_components/air_quality_advisor/strings.json custom_components/air_quality_advisor/translations` reports no generated changes.
- Run `python -m pytest -q tests/test_config_i18n_audit.py`. All 38 languages must contain identical keys and no remaining English-identical config/option prose or errors.
- Verify the Greek Weather/warnings screen and the 18 translated Greek threshold labels visually, along with samples in German, French, Spanish and extra languages.
- Verify the `SelectSelector` `translation_key="output_language"` and localized `selector.output_language.options.auto` work for each HA frontend user language, independent of the server default.
- Hassfest requires lower-case keys under `selector.output_language.options`; test `pt-br`, `zh-hans` and `zh-hant` in the UI while preserving `pt-BR`, `zh-Hans` and `zh-Hant` in saved settings.
- User-assigned sensor names, area names and provider-specific weather-warning names remain unchanged. These are dynamic data, not integration UI strings.
- Push all source, translations and notes together. The completed push to `main` triggers CI and publishes only the latest tested commit after every gate passes.

## Verification gates

A completed push to `main` automatically starts `.github/workflows/validate.yml`. The workflow also supports `workflow_dispatch` for optional manual validation, with manual publishing off by default. Every push-triggered run automatically publishes a **new, unreleased** manifest version only after all gates succeed:

1. `python -m pytest -q tests` and `python -m compileall -q custom_components`.
2. `node --check custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js` and `node tests/card_test.cjs`.
3. Regenerate translations and compare them with checked-in JSON; validate all JSON.
4. HACS Action (`hacs/action@main`) and Hassfest (`home-assistant/actions/hassfest@master`).

A failed gate **prevents a release**. Newer pushes cancel superseded runs, and the publish job confirms that its tested SHA is still the head of `main`, even after packaging. Already published versions are skipped without failing CI. An orphaned pre-existing tag blocks publication rather than being silently repointed.

## Release process — automatic after pushing

1. Commit the complete code, translation, test and documentation changes. Set `manifest.json` and `.github/release-request.json` to the same **new** version and include `.github/releases/v<VERSION>.md`.
2. Push the complete changes to `main`. This **automatically** starts validation and publishes the versioned GitHub/HACS Release (including the installation ZIP) after every check passes. No manual Actions click or CLI dispatch is necessary.
3. Inspect the automatic Actions run and resulting GitHub Release only if troubleshooting is needed. If a gate fails, fix it and push again; the next push validates the newer commit. Do not hand-create a tag or overwrite an existing release.
4. Future changes using the **same version** still run CI, but do not create duplicate releases. Increment the version and prepare notes for the next publish.

The manual `workflow_dispatch` entry point is retained as an optional fallback. Its default is validation-only and does not publish a version unless **Publish release** is explicitly selected.

Live Home Assistant setup, sensor integration and physical Announcement Hub/TTS/notification output tests remain separate acceptance requirements. The integration never operates windows.

**GitHub About metadata:** HACS Action currently ignores only the missing `description` and `topics` checks. Add a repository description/topics and remove this exception before any default HACS catalog application.
