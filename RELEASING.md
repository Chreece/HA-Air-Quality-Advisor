# Release checklist

1. Verify all 26+ pure-logic and discovery tests locally: `python -m pytest -q tests`.
2. Validate shipped JSON and compile Python: `python -m compileall -q custom_components && python -m json.tool hacs.json >/dev/null`.
3. In GitHub **Actions → Validate (manual only) → Run workflow**, check `test`, `hacs`, and `hassfest` all pass. There are **no push, PR, cron or daily triggers**.
4. Install from HACS as a **custom integration** on Home Assistant 2026.10+; confirm setup and options screens work, and the logo renders.
5. Verify room/device assignment, supported outdoor-sensor filtering, weather warning logic, timestamps, stable open recommendations, urgent close recommendations, and unload/reload.
6. Verify manual `air_quality_advisor.announce` (with different languages) and both direct outputs and Announcement Hub routes with real devices. Do not claim output success from accepted service calls alone.
7. When all gates pass, create a **GitHub Release** tagged `v0.1.0`, noting supported HA versions, features and any untested providers. Public HACS catalog listing requires a separate submission after release.

Never enable automatic window actuation without an additional independently audited integration.
