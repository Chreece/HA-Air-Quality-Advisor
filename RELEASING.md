# Release checklist (v0.1.8)

1. Run `python -m pytest -q tests`, `python -m compileall -q custom_components`, `node --check custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js` and `node tests/card_test.cjs`.
2. Confirm all JSON translations are valid and `generate_translations.py` produces the same UI contract.
3. In GitHub **Actions → Validate (manual only) → Run workflow**, confirm the `test`, `hacs` and `hassfest` jobs pass. There are no scheduled, push or PR triggers.
4. Test initial setup in Home Assistant 2026.10+: it must walk areas/rooms → window exclusions → indoor sensors per room → outdoor quality → weather/warnings → announcements, with no advanced-threshold checkbox. Test **Configure** separately: a translated seven-choice menu (with **Rooms first**) must open only the selected section and preserve other saved settings; Advanced thresholds must be a separate choice.
5. Assign multiple supported readings to a single physical device, including CO₂ and humidity. Check that the indoor selector shows **device name, entity name, metric and entity ID**; never include an entity from another room, incompatible unit or unsupported device class.
6. Exclude a high indoor reading for one room and verify it is absent from that room’s recommendation reasons and dashboard readings, without disabling the entity in Home Assistant or affecting another room. Clear the exclusion, save and verify the reading returns.
7. Verify room preselection is the **first initial setup page**. Test that excluding every contact displays an actionable error; if only some selected rooms become contact-less, the Areas page reappears for review. Verify covers are ignored, saved empty exclusions are respected, and disappearing sensors don't erase saved Options selections.
8. Check outside sensor / weather warning behavior, timestamps, urgent closure, announcement cooldowns, unload/reload and unchanged entity unique ID.
9. Verify the Lovelace card is offered automatically, with localized safe/attention/unknown counts and responsive mobile/desktop layouts in both HA themes.
10. Verify direct notification, TTS, and optional Announcement Hub delivery on live devices, including per-action language selection. Only call delivery successful after observing the actual output.
11. After all live gates pass, create a GitHub Release tagged `v0.1.8` and include tested Home Assistant versions and known limitations. Public HACS catalog submission is a separate process.

Air Quality Advisor remains advisory only. It never directly actuates windows or covers.
