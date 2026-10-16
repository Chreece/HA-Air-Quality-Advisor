# Release checklist

1. Verify all Python checks and the frontend smoke test locally: `python -m pytest -q tests && node --check custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js && node tests/card_test.cjs`.
2. Validate shipped JSON and compile Python: `python -m compileall -q custom_components && python -m json.tool hacs.json >/dev/null`.
3. In GitHub **Actions → Validate (manual only) → Run workflow**, check `test`, `hacs`, and `hassfest` all pass. There are **no push, PR, cron or daily triggers**.
4. Install from HACS as a **custom integration** on Home Assistant 2026.10+; confirm setup and options screens work, and the logo renders.
5. Verify the window sensor exclusion picker: likely virtual thermostat/auxiliary entities are preselected, genuine contacts can be unchecked, deliberately empty exclusions persist across reconfiguration, and excluded entities never appear in area counts, recommendations or the dashboard. Verify room/device assignment, supported outdoor-sensor filtering, weather warning logic, timestamps, stable open recommendations, urgent close recommendations, and unload/reload. Confirm the single recommendation sensor exposes `dashboard` with all rooms and outside measurements.
6. After a Home Assistant restart, verify Air Quality Advisor appears in the dashboard card picker, loads its JavaScript without copying into `www`, displays safe/attention/unknown counts, and follows different HA user interface languages. Check narrow mobile and desktop layouts in light and dark mode.
7. Verify manual `air_quality_advisor.announce` (with different languages) and both direct outputs and Announcement Hub routes with real devices. Do not claim output success from accepted service calls alone.
8. When all gates pass, create a **GitHub Release** tagged `v0.1.4`, noting supported HA versions, features and any untested providers. Public HACS catalog listing requires a separate submission after release.

Never enable automatic window actuation without an additional independently audited integration.
