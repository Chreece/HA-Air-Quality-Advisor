# Configuration and Options translation audit — v0.2.4

## Scope

The audit covers the **nine** Home Environment Manager flow pages (Rooms, Window exclusions, per-room indoor sensor exclusions, Outdoor quality, Weather/warnings, Announcements, Advanced thresholds), their menu labels and descriptions, **all per-field help**, validation and abort messages, the output-language selection, and default conversation agent labels, in **38** BCP47 language catalogs. This is an integration UI-string audit, not an automated translation of data from external providers.

## Root cause and correction

The original generator supplied generic, English-only `data_description` strings for the outdoor and weather steps, output language, notifications/TTS and player selection in **all five base language files**. It also reused English advanced-limit labels. The extra language generator included several English validation errors. Rendering the Greek Weather step therefore showed Greek headings next to English explanatory text.

These strings are now maintained in `custom_components/air_quality_advisor/config_i18n_overrides.json`, applied after both base and extended translations by `apply_config_i18n.py`. Re-running the generator no longer overwrites reviewed localizations. The native Home Assistant `translation_key` selector now translates the `auto` language choice.

## Verification checklist

- All 38 language files contain the same config/options keys, step sequence, error codes and selector options (38 language choices + `auto`).
- No non-English configuration/Options prose or validation text remains **identical to the English reference**. This is checked in `tests/test_config_i18n_audit.py`.
- Greek, German, French and Spanish each have detailed help, translated 18-threshold descriptions, default selector choices, error/abort messages, and localized Reconfigure menu text.
- The other 33 supported languages contain concise translated labels, guidance and action-oriented errors. Technical identifiers, units, emoji indicators and Home Assistant integration names are intentionally left consistent. Community/native proofreading is welcome.
- Explicitly ensure the screenshot case is covered: the Greek Weather provider helper and selected warnings helper must be in Greek.
- Do not translate live `weather.*` or provider warning entity names, user device/room labels or geographic names; those are intentionally supplied by HA/providers and not in the integration localization files.

## Regeneration

```bash
python generate_translations.py
python -m pytest -q tests/test_config_i18n_audit.py
git diff --exit-code -- custom_components/air_quality_advisor/strings.json custom_components/air_quality_advisor/translations
```

GitHub Actions remains manual-only and the release is published only when the explicit `Publish release` checkbox is enabled.
