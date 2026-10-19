<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/home-environment-manager-banner.svg" alt="Home Environment Manager — room-aware ventilation recommendations for Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://ko-fi.com/chreece"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="480"></a>
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-Air-Quality-Advisor/releases"><img alt="Release" src="https://img.shields.io/github/v/release/Chreece/HA-Air-Quality-Advisor?include_prereleases&display_name=tag"></a>
  <a href="https://github.com/Chreece/HA-Air-Quality-Advisor/actions/workflows/validate.yml"><img alt="Validation" src="https://img.shields.io/github/actions/workflow/status/Chreece/HA-Air-Quality-Advisor/validate.yml?label=Validation"></a>
  <a href="https://www.hacs.xyz/"><img alt="HACS compatible" src="https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5"></a>
  <a href="https://github.com/Chreece/HA-Air-Quality-Advisor/blob/main/LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-2aa198"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Air-Quality-Advisor&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open Home Environment Manager in HACS">
  </a>
</p>

# Home Environment Manager for Home Assistant

**Home Environment Manager** combines local sensor data, international environmental sources,
building physics and optional advanced comfort models to recommend how to keep a room
comfortable while balancing ventilation, air quality, moisture and potential
pollutant exposure. **PID climate control is optional and initially disabled.** When enabled by the
user for an explicitly chosen room and thermostat, it adjusts only the target
temperature while keeping heating/cooling modes under device control.
The Home Assistant integration domain, existing entity unique IDs and all
saved configuration remain `air_quality_advisor` for upgrade compatibility.


**One compatibility-preserving Home Assistant recommendation entity and one expandable dashboard card for all selected rooms.** It compares indoor CO₂, AQI, particles, VOCs and either room RH or an optional calibrated mold indicator against outdoor air quality, current weather and selected weather-warning entities, then recommends **which windows to open or close and why**. Announcements are entirely optional.

> This project is an advisor, **not an automatic window actuator**, medical device, emergency warning system, or authoritative weather alert. It never controls covers. Outdoor warnings and uncertain conditions are intentionally treated as blockers.

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/home-environment-manager-workflow.svg" alt="Indoor sensors, outdoor air quality and weather feed a single recommendation sensor, with optional announcements" width="100%"></p>

## Dashboard screenshots

The examples below are **real renders of the bundled Lovelace card** using *sample sensor values*, not screenshots of a live Home Assistant installation. They demonstrate the available room summary, ventilation recommendations, outdoor warnings, responsive layout and Greek localization.

### Desktop overview — light theme

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-overview-light.png" alt="Home Environment Manager light-theme dashboard: outdoor air conditions, good and attention rooms, four-room infographic and recommendation to open a window" width="850">
</p>

### Greek localization — dark theme

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-greek-dark.png" alt="Greek Home Environment Manager dashboard in Home Assistant dark theme, with measured CO2 and a window recommendation" width="800">
</p>

### Mobile view and outdoor warning

<table>
  <tr>
    <td align="center" width="38%"><b>Responsive mobile dashboard</b></td>
    <td align="center"><b>Unsafe outdoor conditions — close windows</b></td>
  </tr>
  <tr>
    <td valign="top" align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-mobile.png" alt="Home Environment Manager mobile dashboard with room cards and sensor gauges" width="340"></td>
    <td valign="top" align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-outdoor-alert.png" alt="Home Environment Manager dark-theme outdoor weather and air-quality warning, with close-window recommendation" width="550"></td>
  </tr>
</table>

*Demo sensor values are illustrative; actual recommendations always use your configured Home Assistant entities. The card does not operate windows.*

Screenshots are generated with the bundled card source using [`tools/generate_readme_screenshots.py`](tools/generate_readme_screenshots.py). To refresh them after changing the card, run the one-time [README screenshots workflow](.github/workflows/readme-screenshots.yml) manually; it does not run on routine development pushes.


### Scientific environment details — desktop and mobile

The following examples show the **actual bundled Lovelace card** with
illustrative, explicitly simulated sensor values and advanced room analysis.
They are not screenshots from a live user's home.

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-science-desktop.png" width="850" alt="Home Environment Manager Lovelace scientific room metrics for ventilation, comfort, moisture, pollutants and energy"></p>
<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/screenshots/dashboard-science-mobile.png" width="360" alt="Home Environment Manager responsive mobile scientific room card"></p>

## What it provides

- A single `sensor.air_quality_advisor_window_recommendations` (actual entity ID may vary with user settings). States: `open`, `close`, `idle`, `blocked`.
- Attributes: `open_windows`, `close_windows`, structured `recommendations` with windows, room/area, sensor reason, value and localised message, `outside_blockers`, `diagnostics`, `outdoor_safe`, `announcement_hub_available`.
- Event-driven updates and periodic 5-minute freshness checks. No external APIs, daemons, cloud credentials or Home Assistant tokens. Uses existing entities only.
- **Optional calibrated mold indicator with automatic RH fallback:** per-room measured cold-surface temperature plus a room temperature sensor and an outdoor weather temperature are used to calibrate a surface-humidity estimate. When unavailable, the average of valid room RH sensors automatically substitutes as the ventilation trigger (default 65% RH); the room remains marked incomplete and the card explicitly says RH fallback is active. Unavailable, zero, stale and out-of-range RH sources are excluded.
- A guided setup with editable, automatically suggested window exclusions, room selection, outdoor measurements and weather warnings. Indoor measurements and genuine window contacts are discovered using HA's entity/device area assignments. Configurable thresholds are tucked into **Configure → Advanced thresholds**.
- Optional room-aware [Announcement Hub](https://github.com/Chreece/HA-Announcement-Hub) output (`notify.announcement_hub`), **or** direct `notify.send_message` and `tts.speak` via supported entities. Not installing Announcement Hub does not affect the recommendation sensor.
- **One optional AI setting** for both delivery paths. With Announcement Hub configured, it explicitly forwards `use_ai: true/false` and optionally `ai_agent`; otherwise the selected Home Assistant conversation agent rewrites direct notification/TTS text. AI never changes the window decisions and is off by default. Only a **not-running/unavailable Hub** permits Home Assistant direct/persistent notification fallback. A **running Hub** owns room/output routing and rejections; Advisor reports enqueue failure but never creates a second native notification.
- Auto notifications/TTS can each be enabled or disabled independently. Open announcements wait 90 seconds for conditions to stay stable; close announcements are immediate. Repeated open recommendations have a 15-minute cooldown during the current HA process. New urgent close recommendations are not suppressed by that cooldown, even if the same window was reopened. No notification is generated on every unchanged sensor reading.
- Manual `air_quality_advisor.announce` action with an independent language override across **38 supported Home Assistant language choices**. Speech requires a compatible TTS voice.
- A responsive **Home Environment Manager dashboard card**: safe/attention/unknown room counts, current outdoor weather and pollution, threshold meters, window states, and room-specific advice. Card text follows your **Home Assistant user language**, independently of voice/notification language.

## International environmental intelligence (v0.4.0)

**Works internationally:** no German/Greek-only integrations, coordinates, AQI
scales or pollen sources are hard-coded. All optional provider information
comes from sensors and integrations *already connected to Home Assistant*.
Users supply and explicitly identify which scale and units each sensor uses.

### New science available in each room

| Capability | Inputs and methods | Output and evidence limits |
| --- | --- | --- |
| Region-specific AQI | Explicit per-entity EPA 0–500, European categorical 1–6, or custom provider scale | Never guesses the country or misuses another scale. Unspecified scales remain *unknown* rather than declaring safe air. |
| Outdoor gases | Actual NO₂, O₃ and SO₂ sensors in µg/m³ | Configurable operational screening, not equivalent to a regulatory 24-hour or 8-hour mean. |
| Pollen-aware airing | A user-selected numeric pollen forecast from any HA integration; user declares scale and high threshold | Informational by default. Blocking ventilation on high pollen is an **explicit opt-in** policy, not a global default. |
| Ventilation learning | Real NDIR CO₂, calibrated history, window contacts | Reports *indicative* declining CO₂ and time to an operational target if the trend remains stable; no arbitrary prediction if windows are closed or data insufficient. |
| Particle filtration | User-measured room volume and purifier's *particle CADR* (m³/h), optional operation sensor | Nominal equivalent clean-air changes per hour. Does not claim removal of gases, infections, or measured causal benefit. |
| Moisture events | Time history of indoor RH, optional extractor state | Detects rapid RH rises and suggests checking extraction. A shower/cooking source is **not** inferred from RH alone. |
| Indoor/outdoor PM | Indoor + outdoor PM2.5 and overlapping 24-hour qualified history | Descriptive concentration ratio, explicitly **not** a calibrated particle infiltration fraction. |
| Radon | A verified dedicated radon sensor, Bq/m³ or pCi/L | Long-term screening only after about a year of sufficient daily averages. The local monitoring reference is configurable; regulatory levels depend on the jurisdiction. |
| Formaldehyde | Verified real HCHO measurement, µg/m³ or mg/m³ | 30-minute observed concentration; comparison is disabled for cheap estimated HCHO/eCO₂ proxies. |
| Acoustic environment | Calibrated A-weighted equivalent sound readings in dB(A) | Proper logarithmic acoustic-energy averaging, optionally the preceding local nighttime period for sleeping rooms. Peak-only meters are unsuitable. |
| Lighting | Calibrated photopic lux measurements; independently measured melanopic EDI only | Daylight-exposure history. Ordinary lux is **never** converted into a fake circadian/melanopic result. |
| Thermal comfort | Actual radiant temperature, air speed, occupant activity (met) and clothing (clo), opt-in | ISO 7730:2025 PMV / PPD computed locally using an independently verified scalar Fanger model, without Numba or LLVM. Missing inputs suppress the result. |
| Overheating | Time history of room temperature | Observed temperature degree-hours above a chosen reference, not TM52/TM59 building-certification compliance. |

Existing modules from v0.3.0 remain, including humidity-ratio calculations,
surface-condensation margin, measured PM 24-hour averages, adaptive comfort,
passive cooling, controlled CO₂ decay estimation and local bounded history.
New specialist sensors, comfort assumptions and equipment measurements are
**optional**. Most households can benefit without buying extra hardware.

### Clear configuration

In **Home Assistant → Settings → Devices & services → Home Environment Manager → Configure**:

1. **Rooms and safety:** retain your window contacts, sensor exclusions, indoor and outdoor readings, optional mold calibration, weather warnings and existing notification settings.
2. **International air quality & pollen:** choose your outdoor AQI provider's published scale and optionally a pollen forecast. Unknown AQI scales cannot be silently interpreted.
3. **Room environmental measurements:** select **one room at a time**, then configure optional temperature-source override, actual air volume, purifier CADR, extractor state and real CO₂ technology.
4. **Specialist measurements:** choose validated radon, formaldehyde, noise and daylight sensors, verifying hardware/calibration where required.
5. **Advanced comfort:** enable PMV/PPD **only** when all physical inputs exist; otherwise rely on the simpler adaptive comfort indication with its applicability limits.

Every module uses **evidence statuses** such as not configured, invalid units,
insufficient history, unverified sensing hardware and calculated. Missing
data never justifies an invented positive health result. All calculations are
local; selected external forecasts come from Home Assistant's existing providers.

### Compatibility and the upcoming PID phase

The public title, integration manifest and dashboard branding use
**Home Environment Manager**, but the internal domain remains
`air_quality_advisor`; its original service `air_quality_advisor.announce` (plus the new
`home_environment_manager.announce` alias),
existing entity unique IDs, area selections, statistics storage and prior
configurations are preserved. Existing
`custom:air-quality-advisor-card` Lovelace dashboards still work; new
cards may use `custom:home-environment-manager-card`.

**PID-based climate control is not enabled in v0.4.0.** In the next phase,
climate actuators will need explicit device selection, safety constraints,
anti-windup, deadbands, duty limits, manual-override respect, safe fallbacks
and independent validation before any control can be enabled. None of the
current advice triggers an actuator directly.

**Research and frameworks:**
[ASHRAE Standard 55](https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy),
[ISO 7730:2025](https://www.iso.org/standard/79804.html),
[WHO 2021 air-quality guidelines](https://www.who.int/publications/i/item/9789240034228),
[European Environment Agency air quality index](https://airindex.eea.europa.eu/),
[US EPA AQI](https://www.airnow.gov/aqi/aqi-basics/),
[WHO radon](https://www.who.int/news-room/fact-sheets/detail/radon-and-health),
[CIE S 026](https://cie.co.at/publications/cie-system-metrology-optical-radiation-iprgc-influenced-responses-light-0).


## Installation

### HACS (versioned releases)

1. In HACS, open **Custom repositories**; enter `https://github.com/Chreece/HA-Air-Quality-Advisor` and choose **Integration**.
2. Install **Home Environment Manager**, restart Home Assistant and add it under **Settings → Devices & services → Add integration**. The dashboard card is bundled and registered automatically when Home Assistant starts; no separate HACS frontend repository or copy to `www` is required.
3. No YAML configuration is required. After updating from a version that was classified as a Helper, **restart Home Assistant** so the new manifest type takes effect. The existing configuration and entity ID are kept; the integration should now appear under **Settings → Devices & services → Integrations** instead of being categorized under Helpers.

### Manual

Copy `custom_components/air_quality_advisor/` to `<your Home Assistant config>/custom_components/air_quality_advisor/`, restart HA, then add the integration from the UI. Alternatively, from the extracted repository run:

```bash
HA_CONFIG=/path/to/homeassistant/config bash ./install.sh
```

The installer writes **only** the integration directory, makes a rollback backup of an older installation and does not restart HA or end your SSH session.

## HACS releases

**Latest published stable release:** see [GitHub Releases](https://github.com/Chreece/HA-Air-Quality-Advisor/releases). Each push to `main` runs Python and frontend tests, translations, Hassfest and HACS validation; a new version is automatically published only when all gates pass.

Update through [HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Air-Quality-Advisor&category=integration), then restart Home Assistant. Existing config entries and the single recommendation sensor retain their IDs. The bundled Lovelace card is refreshed automatically.

## Internationalization — 38 languages

Home Environment Manager supports **38 Home Assistant language choices**, including 33 new locale packs for setup, reconfiguration, room states, notification messages, announcement text and the built-in dashboard card. The card follows the signed-in **Home Assistant user's language**, while `air_quality_advisor.announce` can override message language independently.

**Languages:** English, German, Greek, French, Spanish, Italian, Dutch, Portuguese (Portugal and Brazil), Polish, Russian, Ukrainian, Turkish, Czech, Slovak, Hungarian, Romanian, Bulgarian, Croatian, Serbian, Swedish, Norwegian Bokmål, Danish, Finnish, Indonesian, Vietnamese, Thai, Hindi, Simplified/Traditional Chinese, Japanese, Korean, Arabic, Hebrew, Persian, Bengali, Urdu and Tamil.

BCP47 support distinguishes `pt-BR` from `pt-PT`, and `zh-Hans` from `zh-Hant` (`zh-CN` and `zh-TW` are also recognized). Unsupported locales fall back to English. The dashboard uses right-to-left layout for Arabic, Hebrew, Persian and Urdu.

**Translation audit (v0.2.4):** All 38 language files now provide localized configuration and Reconfigure field labels, help text, validation errors, the settings-selection menu, abort messages, and the language selector's **Home Assistant default** option. Greek, German, French and Spanish include fully translated advanced-threshold labels and detailed explanations. The other 33 languages use short translated safety guidance and error messages with technical terms and symbols; native-speaker review is welcome. **Dynamic weather warnings, device names, room names, geographic names, sensor readings and IDs come from the user's Home Assistant or the weather provider and are not translated by this integration.** Actual spoken language still depends on the installed TTS voice.

Locale sources are in `custom_components/air_quality_advisor/locale_pack_*.py` and the reviewed, centralized `config_i18n_overrides.json` file. After editing either source, run `python generate_translations.py` and `python -m pytest -q tests/test_config_i18n_audit.py`. The generator applies the localized configuration overrides, then the optional mold-room translations, **last**, so it cannot silently restore English helper text. Native-speaker improvements are welcome.

### Config-flow translation quality assurance

The full UI localization audit checks **all seven setup/Reconfigure sections**: Rooms, Window sensor exclusions, Per-room indoor sensors, Outdoor air, Weather/warnings, Announcements and Advanced thresholds. It also covers every helper description, every validation/abort message, the independent Options menu and dropdown option labels.

For example, the Greek Weather page explains directly that at least one weather provider is required, that unsafe weather prevents opening, and that active/unavailable warnings block opening. German, French, Spanish and the additional language packs receive corresponding localized instructions. [Audit details](TRANSLATION_AUDIT.md).

## Guided configuration and reconfiguration

**Initial setup** starts with Rooms, then window exclusions, followed by the remaining guided steps:

1. **Areas / rooms (multi-select).** Start by choosing which rooms to monitor. Rooms with Window-class `binary_sensor` contacts are suggested and automatically preselected. Window-class `cover` entities are never considered window contacts. You can remove unwanted rooms before continuing.
2. **Window sensor exclusions (multi-select).** Next, review recognized window contacts. Likely thermostat-derived or virtual window signals are preselected for exclusion; uncheck any actual window contacts or add other exclusions. If these exclusions remove the last usable contact from a selected room, setup returns to Rooms for review. If all contacts would be excluded, setup explains that at least one must remain. Your choices—including an explicitly empty exclusion list—are saved.
3. **Indoor air-quality exclusions (one page per selected room).** Each room with supported indoor sensors has its own multi-select. Available candidates include **humidity, CO₂, US AQI, PM2.5, PM10, total VOC mass concentration and VOC parts concentration**, using only the supported device classes or recognized sensor IDs with compatible units. Options show **device name › entity name · measurement · entity ID**; entities without a registered device still show entity name, metric and ID. Select sensors to **exclude** from that specific room; **leave empty to monitor them all**. On reconfiguration the saved exclusions are checked. Previously excluded but now missing sensors remain selectable, so you can remove obsolete exclusions. Rooms without supported indoor sensors are skipped rather than showing a useless blank menu.
4. **Outdoor air quality.** Select recognized outdoor entities not associated with monitored rooms. Unknown, unavailable and stale readings are reported as missing, not treated as dangerous. Valid high readings still block opening.
5. **Weather and warnings.** Select one or more `weather.*` entities and optional recognized warning sensors. Unsafe weather and active or unknown warnings block window opening.
6. **Announcements (optional).** Configure spoken/visual delivery, language and optional [Announcement Hub](https://github.com/Chreece/HA-Announcement-Hub) routing. Advanced thresholds are edited separately through Configure.

Indoor exclusions and mold calibrations are stored **by Home Assistant area**, used for both recommendations and the dashboard snapshot. An excluded indoor sensor remains available in Home Assistant; the integration does not disable, delete or modify it. Areas with no remaining active indoor measurements are shown as **unknown**, never silently marked safe. Only the single existing window-recommendation entity is generated.

For an installed integration, open **Settings → Devices & services → Integrations → Home Environment Manager → Configure**. A translated menu lets you choose exactly which section to edit: Rooms, Window sensor exclusions, Per-room indoor air sensors, Outdoor air sensors, Weather and warnings, Announcements, or Advanced thresholds. Only the selected section opens. Indoor sensor exclusions continue room by room, but every other section saves immediately without forcing the rest of setup. Your saved selections are prefilled; cancelling leaves existing settings unchanged. The full flow uses the same five Home Assistant UI languages (English, German, Greek, French and Spanish).

### Mold indication instead of RH (optional)

Check **Use mold indication instead of raw room RH** on the first **Rooms** setup page. The legacy 65% room-RH rule remains unchanged until you enable it. When enabled, the Advisor **prefers** the estimated relative humidity **at the coldest surface** (default trigger 70%); when mold estimation is unavailable, it **automatically falls back to the valid room RH average** (default trigger 65%). Both limits can be changed independently in **Advanced thresholds**. The mold indicator is a moisture/mold-growth indication, not a probability of having mold.

For each room, first open **Weather and warnings** (second option in **Configure**) and choose a weather entity providing a current `temperature` attribute (°C/°F). The Advisor reads this attribute as outdoor temperature; it does **not** obtain temperature from the humidity sensor or the outdoor air-quality/pollution sensors. Then open **Room settings — indoor air and mold** (third option in Configure), choose a room temperature sensor (°C or °F), and measure the room's **coldest wall surface**, usually an outside corner or window frame, with a contact/infrared thermometer. Enter the measured critical-point temperature in **°C**. Measure at the same time as the room temperature sensor and selected weather entity's outdoor temperature. They should differ by at least 3 °C for a stable calibration. The integration calculates the same factor as Home Assistant's [Mold Indicator](https://www.home-assistant.io/integrations/mold_indicator/):

```text
calibration_factor = (temperature_indoors - temperature_outdoors)
                   / (temperature_coldest_surface - temperature_outdoors)
estimated_surface_temp = temperature_outdoors
                       + (temperature_indoors - temperature_outdoors) / calibration_factor
```

Until the coldest-surface measurement is entered, the mold indication is unavailable. **If there is at least one valid room RH reading, the card now displays an active RH fallback reading and its own 65% threshold**. The fallback is always an average of available valid room RH sensors, never a mold surface-humidity percentage. The room remains **partially verified (not green/safe)** while mold is missing; PM2.5, AQI, CO₂ and VOC continue independently. An RH average at or above its threshold can still recommend opening a closed window when outdoor conditions are suitable.

On the dashboard, the compact mold gauge uses readable labels, for example **“Μέση υγρασία: 55% · 2 αισθητήρες”** and **“Εκτιμώμενη επιφάνεια: 17,1°C”** in Greek. The count is the number of valid room RH sensors, **not** the calibration factor. Select **More details** for the room—even when it has only three measurement cards—to view the saved **calibration factor** and the current indoor/outdoor temperatures used by the estimate. The factor is preserved at full floating-point precision in the sensor's dashboard metadata; the card formats it to up to six decimal places (minimum two) without changing the calculation.

The room's humidity sensors are discovered and filtered through the normal per-room exclusion list. **Only valid RH readings above 0% and at most 100% are averaged**; `unknown`, `unavailable`, out-of-range, NaN, stale and excluded readings do not contribute. The indoor average and the room/outdoor temperatures determine dew point and estimated surface RH via the Magnus formula. The dashboard shows the calculated indicator, number of valid RH contributors, their average and estimated surface temperature.

The original calibration factor is **preserved** when sensors, conditions or excluded entities change, including the particular selected weather source used for that calibration. If that weather entity is removed or stops providing temperature, the mold estimate becomes unavailable and reports the missing outdoor temperature instead of silently using another source; **the room switches to its valid averaged RH fallback when possible**. Use **Recalibrate** only after physically measuring the surface again. If indoor temperature, outdoor temperature or calibration is missing, the mold reading remains unavailable; an RH fallback works as long as at least one valid RH reading exists. With no valid RH, neither humidity method can trigger ventilation. Bad weather continues to take priority and requires closing any open monitored windows.

During initial setup, the wizard already selects **Outdoor air** and **Weather and warnings** before the per-room cold-surface calibration. On an existing installation, select **Configure → Rooms** to enable mold mode, then **Configure → Weather and warnings** (second menu option) to verify that a weather entity provides outdoor temperature, followed by **Configure → Room settings** (third option) for each room.

If calibration, room temperature, weather temperature, usable nonzero room humidity, or the mathematical estimate is missing, the room card displays a separate actionable warning for each missing input; the recommendation sensor also exposes `mold_input_warnings` and detailed `diagnostics` attributes. Bad weather and missing data do not suppress these warnings. The card explicitly says **RH fallback active** with its current mean and threshold when available. A missing mold input **alone** does not generate a spoken announcement, but a valid averaged RH measurement crossing the ventilation threshold can produce the existing delayed open-window recommendation and optional announcement. Incomplete calibration does not falsely mark a room safe.

### Supported indoor and outdoor measurements

| Measurement | Supported unit(s) | Outdoor good at or below | Indoor requires ventilation at or above |
|---|---|---:|---:|
| AQI — **US scale 0–500** | index / none / AQI | 50 | 100 |
| CO₂ | ppm | 800 | 1,000 |
| PM2.5 | µg/m³ or mg/m³ | 15 | 25 |
| PM10 | µg/m³ or mg/m³ | 45 | 45 |
| Total VOC | µg/m³ or mg/m³ | 500 | 500 |
| VOC concentration (parts) | ppb or ppm | 500 ppb | 500 ppb |
| Relative humidity (legacy mode) | % | — | 65% |
| Averaged room RH fallback (mold unavailable) | % | — | 65% |
| Mold indication (opt-in, available) | estimated surface RH, % | — | 70% |

Sensor values are normalised to the units above. Outdoor temperatures from weather entities must remain from **5–32 °C**, humidity at most **85%** and wind at most **35 km/h** when those attributes are provided. Supported fair weather states: `sunny`, `clear-night`, `partlycloudy`, `cloudy`. All other states, including rain, snow, thunderstorms, fog and high wind, block opening. Selected warnings that are active **or cannot be verified** also block opening. Weather providers with unknown state block opening. Selected outdoor data older than 90 minutes (using `last_reported` when available) are reported as unavailable, without blocking opening. Adjust the freshness interval by checking **Edit advanced thresholds** on the announcements page.

**AQI scales differ internationally.** A European 1–5 index is *not* the US 0–500 AQI. For 1–5 index sensors, change the outdoor AQI limit (for example `2`) and indoor AQI trigger (for example `3`) using **Edit advanced thresholds**, or use the measured pollutant sensors instead. Numeric thresholds are configurable per installation, not per sensor, and do not represent exposure-duration standards.

### Decision policy

| Outdoor state | Indoor state and windows | Recommendation |
|---|---|---|
| Good, no selected warnings | Indoor CO₂/particles/VOC/AQI/humidity exceed a threshold and all room windows are closed | **Open** the room's recognized windows, with the measured reason |
| Bad, rainy, extreme, warning active or unknown | Any recognized window is actually open | **Close** each open window, with outdoor blocker(s) |
| Good | Room already has a window open | No further open action (ventilation already underway) |
| Good | Indoor values acceptable | `idle` |
| Missing weather or unknown weather-warning status | No windows verified open | `blocked`; no open recommendation |
| An outside air-quality sensor is unknown/unavailable | Otherwise good known conditions | No blocker from that sensor; diagnostics show missing data |
| No room sensor or window contact | Missing information | No guessed recommendation; diagnostics attribute identifies the gap |

Only **non-excluded** `binary_sensor` entities with device class `window` count as windows. A `cover` is never counted, even if its device class is `window`. Excluded entities are ignored by room suggestions, window counts, open/close recommendations, automatic announcements, and the dashboard. The automatic suggestions are based on entity and device metadata, **not a guaranteed physical-contact identification**; review them for your hardware. Missing outside readings do not themselves block opening/require closure, but appear in `unavailable_outdoor_sensors` and set `outdoor_data_complete: false`. Missing weather or an unknown weather-warning status still blocks opening.

## Home Environment Manager dashboard card

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/dashboard-card-preview.svg" alt="Illustrative Home Environment Manager Lovelace card with outdoor weather, safe rooms, attention counts, sensors and windows" width="100%"></p>

**Add it from the dashboard card picker**: Edit your dashboard → **Add card** → **Home Environment Manager**. The integration registers the card JavaScript automatically after a Home Assistant restart, and the card discovers the recommendation sensor if you have exactly one Home Environment Manager instance. The card picker also suggests it for your recommendation entity. A built-in graphical editor lets you select the sensor, rename the card and toggle the outdoor panel and detailed metrics.

The equivalent YAML is:

```yaml
type: custom:air-quality-advisor-card
# Optional when exactly one Home Environment Manager integration exists:
entity: sensor.air_quality_advisor_window_recommendations
# Optional card settings:
show_outside: true
show_metrics: true
```

Use the actual entity ID from **Developer tools → States** if it differs from the example. The card reads `attributes.dashboard` from the integration's **single existing recommendation sensor**; it creates **no additional entities** and never controls windows. It works in Sections and masonry dashboards, light/dark themes, phones and desktop. It shows:

- An **outdoor status panel** with the current weather, temperature, wind, humidity, selected outdoor pollution readings and warnings. *Unsafe* means a known hazard; *unknown* means required weather/warning information is missing; *partial* means a selected air sensor is unavailable even though available readings do not block ventilation.
- A **donut chart and totals** for rooms marked **Good**, **Needs attention** and **No data**. Rooms with high indoor pollutants, or an urgent close-window recommendation, require attention. Rooms with missing measurements or unknown window contacts are never counted as good. Already-open windows with bad indoor air remain visible as requiring attention.
- **Room panels** with CO₂/PM/AQI/VOC/humidity gauges against the thresholds in your integration settings, plus actual window contacts and open/close recommendations. Extra readings can be expanded without leaving the dashboard.

The card automatically uses **Home Assistant's per-user interface language** (`hass.language`), not the separately configured announcement language. It includes native text for English, German, Greek, French, Spanish, Italian, Dutch, Portuguese, Polish, Russian and Turkish; unsupported languages fall back to English. Sensor names and room names remain as named in Home Assistant.

If the card doesn't appear after updating via HACS, **restart Home Assistant**, reload the browser and reopen the card picker. It also exposes a normal JS resource endpoint at `/air_quality_advisor/air-quality-advisor-card.js` for installations where automatic frontend loading has been disabled; there is no need to copy it to `/config/www`.

## Building-physics and exposure diagnostics

Home Environment Manager also derives **optional, deterministic environmental context** from
real Home Assistant measurements. The existing window safety rules, weather alerts
and Announcement Hub routing remain authoritative. These are **engineering
indicators**, not a medical assessment, building certification, or an automatic
window actuator.

| Indicator | Inputs | Interpretation and limits |
| --- | --- | --- |
| Moisture and drying potential | Indoor air temperature + relative humidity and one valid outdoor weather temperature/RH source | Actual vapor content in g/kg dry air; positive drying potential means outside air carries less water. Shows predicted RH if outside air were warmed indoors without adding vapor. Cold 90% outdoor RH can still be drying. |
| Adaptive comfort | Indoor temperature and **at least seven days** of sufficiently complete outdoor temperature samples | Indicative ASHRAE 55 80% band, only relevant to naturally conditioned spaces with occupant-controlled windows. Room air temperature is a proxy for operative temperature, *not proof of compliance*. |
| Passive cooling and energy | Above comfort inputs and indoor/outdoor temperature difference | Opportunistic cooling only when outdoor safety policy also passes; approximate Wh **per cubic meter for one complete air exchange**, not measured heating energy or savings. |
| Condensation and mold moisture exposure | Indoor temp/RH and optional existing calibrated mold surface temperature | Dew-point/surface margin and recorded hours at estimated surface RH ≥80%. Not a VTT mold index, mold probability, or verified wall measurement. |
| 24-hour particles | PM2.5 and PM10 sensors | Time-weighted average with at least 80% observed coverage and no bridging gaps over 15 minutes. Shows WHO 2021 **24-hour** references (15/45 µg/m³), not instantaneous exposure compliance. |
| CO₂ slope and tentative ACH | Real indoor/outdoor CO₂; open window contact; a confirmed vacant-state sensor | Trend requires at least 10 minutes of observations. ACH requires a vacant, open-window decay interval with sufficient measurements; occupancy uncertainty or no measured outdoor CO₂ means *no ACH estimate*. True NDIR sensor technology must be independently verified. |
| Observed nighttime overheating | Valid room temperature, local timezone, 7 days of samples | Hours above 26°C between 22:00 and 07:00, reported only with adequate coverage. **Not** a CIBSE TM59:2026 design-stage assessment. |

### Sensor selection, accuracy and persistence

The advisor automatically discovers an indoor temperature sensor **only if exactly
one current valid candidate exists in a room**. When there are several, it uses
the explicitly configured temperature sensor from that room's mold calibration
(if present); otherwise temperature-dependent metrics remain unavailable rather
than randomly combining sources. Outdoor psychrometrics similarly require
one unambiguous current weather temperature source with relative humidity.

The historical indicators start in a **warming-up / insufficient-coverage** state.
The integration saves a compact, capped collection of room observations in
Home Assistant's **local storage**, retaining up to eight days and sampling at
most every five minutes except when window/occupancy state changes. To calculate
conditional ACH, the local history includes the occupancy boolean and window
contact state. No cloud analytics are used. Changes to HA Recorder retention do
not automatically delete the separate bounded history storage.

Missing, stale and physically implausible CO₂/RH readings remain unknown; a
measurement labeled CO₂ does **not** establish that the hardware contains an
NDIR sensor. Outdoor PM2.5 = 15 and PM10 = 45 in the legacy configurable
instantaneous decision rules remain operational screening cutoffs and must
not be described as WHO 24-hour guideline compliance. Humidity-only opening
is suppressed when reliable current paired readings indicate that outside air
contains *more* vapor. This does not override rain, wind, cold-weather or
severe-weather safety restrictions.

These diagnostics are available inside the existing room dashboard's
**Building physics** section and in the recommendation sensor's
`dashboard.rooms[].environment` attributes; no extra devices are created.
The card shows German, Greek and English labels, with English fallback for
additional locales.

**Scientific references:**
[ASHRAE Standard 55](https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy),
[ISO 13788](https://www.iso.org/standard/51615.html),
[WHO 2021 global AQ guidelines](https://www.who.int/publications/i/item/9789240034228),
[EPA indoor sensor limitations](https://www.epa.gov/indoor-air-quality-iaq/low-cost-air-pollution-monitors-and-indoor-air-quality),
[CIBSE TM59:2026](https://www.cibse.org/knowledge-research/knowledge-portal/tm59-overheating-risk-in-dwellings-a-design-stage-methodology-2026).

**Not implemented as a purported validated result:** Fanger PMV/PPD (would require
measured radiant temperature/air speed and supplied clothing/activity inputs),
Finnish VTT mold index (requires surface moisture history *and* verified
material properties), or reliable heat-loss prediction without measured
airflow/room geometry. Rather than manufacture these quantities from weather
and RH alone, the advisor displays only the defensible indicators above.

## The single backward-compatible recommendation sensor

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/.github/assets/recommendation-preview.svg" alt="Illustrative Home Environment Manager close-window recommendation" width="100%"></p>

Typical state when CO₂ is high but outdoor air and weather are good:

```yaml
state: open
attributes:
  outdoor_safe: true
  outdoor_data_complete: true
  unavailable_outdoor_sensors: []
  open_windows:
    - binary_sensor.living_room_window
  close_windows: []
  recommendations:
    - action: open
      area_id: living_room
      area: Living room
      windows:
        - binary_sensor.living_room_window
      reasons:
        - code: inside_co2
          entity: Living room CO₂
          value: 1,200 ppm
      message: "Open Living room window in Living room: Living room CO₂ is high (1,200 ppm). Outdoor conditions are suitable."
```

The system automatically updates this entity. You can display `recommendations`, `open_windows`, `close_windows` and `outside_blockers` in dashboards or automations. No duplicate per-area sensors.

## Repeating persistent window recommendations

Under **Home Environment Manager → Configure → Announcements**, set **Repeat announcements (minutes)** to any whole number from **0 to 1440**. The default is **10 minutes** for new and existing installations; **0 means never repeat**. This applies only if automatic notifications or automatic TTS are enabled. Manually invoked announcements are not scheduled for repetition.

- A **new open-window** recommendation still waits 90 seconds for stable conditions; a **close-window** recommendation is announced immediately. Repeats run at the configured interval **after the previous automatic submission finishes**, so slower AI/Hub calls do not cause overlapping reminders.
- A reminder is sent only while **the same room, window action and cause remain actionable**. Before each reminder, the sensors and window contacts are checked again. When the window is opened/closed or air/weather conditions recover, remaining timers are cancelled.
- Each monitored **room has its own reminder timer**. A CO₂ value fluctuating above its threshold does not reset the timer, but a different sensor reason or weather category starts a fresh interval. The existing 15-minute anti-flapping cooldown applies only to newly reappearing open-window recommendations; it **does not block timed reminders**.
- On Home Assistant restart, an already-urgent close recommendation still announces immediately; an existing open recommendation receives its first reminder after one full repeat interval rather than immediately on boot.

The setting works with Announcement Hub, direct TTS, native notification entities and persistent Home Assistant notifications. It does not alter pollutant thresholds, AI permissions or actual window control.

## AI-enhanced announcements and fallback

Open **Home Environment Manager → Configure → Announcements**. **Use AI for announcements** is a single checkbox for both routes, off by default. The automatic notification and TTS switches still independently control whether anything is announced. Existing saved AI settings are preserved during upgrades.

- **Announcement Hub selected:** This checkbox sends an explicit `use_ai: true` (or `use_ai: false` when unchecked) with the room-specific `notify.announcement_hub` action. A custom conversation agent is forwarded as `ai_agent`; leaving **Home Assistant default** selected omits the field so the Hub uses its own configured agent. The Hub performs the rewriting and controls delivery; the advisor does not rewrite the same message again.
- **Announcement Hub not selected:** The advisor uses `conversation.process` to rewrite the original text before sending it to direct `notify.send_message` and/or `tts.speak` outputs. The agent choice defaults to Home Assistant's default conversation agent; other `conversation.*` entities can be selected. Failed or invalid rewrites use the unchanged original message (up to eight seconds for opening and three seconds for urgent closing recommendations).

**When the Hub option appears:** It is offered **only if Announcement Hub has a Home Assistant configuration entry**. Merely having an action named `notify.announcement_hub` is not enough. If Hub is removed, unconfigured, stopped or not loaded, Advisor uses native Home Assistant delivery instead. **When Hub is running**, Advisor forwards the recommendation and actual Home Assistant area display name, then stops: even if Hub rejects the request, cannot route it, returns no acknowledgement, or exceeds the acknowledgement safety timeout, **Advisor does not create any native notifications or TTS**. A rejected Hub job is reported in the manual action response and logged, **not falsely counted as queued**. Resolve the routing problem in Announcement Hub, not by broadcasting from Advisor.

**Fallback order, used ONLY without a running Hub:** configured `notify.send_message` outputs and/or `tts.speak` engines/players → built-in `persistent_notification.create` (one updated notification per room) if nothing was delivered. A persistent notification is **visual only**. Hub owns its own queue and delivery once it is running; Advisor never duplicates failed Hub routes or AI jobs with a persistent Home Assistant notification.

**AI safeguards and privacy:** Window/room selection, weather limits, sensor reasons and alert timing stay deterministic. The advisor validates direct AI text to preserve the action, room, window names and measurements; failures fall back to the original message. Home Assistant conversation agents can have device-control privileges and may execute tools even when asked to rewrite text only. Use a text-only/low-permission agent, and review cloud-agent data sharing (room and window names and sensor readings can leave your Home Assistant). The built-in non-generative Assist agent may not rephrase arbitrary text.

## Announcing in a different language on each action

```yaml
action: air_quality_advisor.announce
data:
  language: el  # any supported locale, e.g. el, de or pt-BR
  channels: both  # both, tts, notification
  areas:
    - living_room
```

Omit `areas` to report every room with an actionable recommendation. The manual action can be called even when automatic TTS/notifications are disabled. Passing `language` changes the **generated recommendation text** and requests the matching speech language. Actual spoken voice availability depends on the selected TTS provider. The service may report accepted/submitted requests; this does not guarantee a physical speaker played audio or a notification was displayed.

Announcement Hub delivery uses the established action:

```yaml
action: notify.announcement_hub
data:
  text: "Schließe das Fenster in Küche wegen schlechten Wetters."
  area:
    - Küche  # HA area display name, not internal ID 'kouzina'
  level: warning
  use_ai: true
```

When both channels are enabled, Advisor submits the common `text` field, exactly as in this example. For notification-only or TTS-only settings it sends `text_notify` or `text_tts` respectively so the other channel is not silently activated. In every case, `area` uses the **actual Home Assistant area name** from the Area Registry (`Küche`), while Hub resolves that name back to its internal area ID and decides which devices/routes are eligible. Advisor does **not** override `occupied_only` or manually choose notification or audio devices. The example text is illustrative; live messages contain the real room, window names and sensor reasons.

**Important:** Sending `Küche` instead of `kouzina` makes the handoff readable, but does not create a missing Hub output. If Hub reports `The selected text has no configured matching output`, **configure room/global delivery in Announcement Hub**; Advisor will report the refusal without an unwanted native Home Assistant event notification.

## Testing, validation, and publishing

```bash
python -m pytest -q tests
python -m compileall -q custom_components
bash ./publish.sh
```

`publish.sh` is an optional local publishing script requiring an authenticated GitHub CLI (`gh auth status`). It **never force-pushes** or mutates other repositories. **GitHub Actions automatically validates every completed push to `main`** and creates a new GitHub/HACS Release after Python, JavaScript, translation, HACS and Hassfest checks pass. Superseded commits and already published version tags cannot create duplicate releases. Push the complete code, translations and release notes with matching manifest and release-request versions; no manual action is required. Manual validation remains available through [Actions → Validate and release (after push)](https://github.com/Chreece/HA-Air-Quality-Advisor/actions/workflows/validate.yml), without publishing by default. See [RELEASING.md](RELEASING.md).

## Opt-in PID climate control (v0.5.0)

Home Environment Manager can now **control explicitly authorized Home Assistant
`climate.*` entities** using a bounded supervisory PID controller.

**Important:** Unlike a direct compressor or heater relay PID, this is an
*outer-loop thermostat setpoint regulator*. It changes only
`climate.set_temperature` with a single `temperature` value.
It never sends `climate.set_hvac_mode`, `climate.turn_on` or `climate.turn_off`.
The climate device retains its own safety protections and compressor cycling.
Not all thermostat models support safe nested PID control; test behavior carefully.

### Configure a room

Open **Settings → Devices & services → Home Environment Manager → Configure
→ Climate PID**. Choose one monitored room, then provide:

| Input | Why it is required |
| --- | --- |
| Enable PID | Explicit opt-in; disabled for every existing and new room by default. |
| Authorized climate devices | Select only the target `climate.*` entities that are allowed to be controlled in this particular Home Assistant room. No area-wide service broadcast. |
| Independent room temperature sensor | Required current `sensor.*` measurement, normalized from °C or °F; older than 10 minutes stops control. |
| Existing HVAC mode | Choose heat or cool; the physical thermostat must already be in that mode. No automatic mode or compressor switching. |
| Desired room temperature | Current fixed room-temperature goal in °C. |
| Pause when window open/unknown | Enabled by default. Open or unknown window contacts suppress commands without turning climate hardware on or off. |

The next **Advanced PID tuning** page contains Kp, Ki and Kd gains, the
maximum permitted setpoint trim, minimum/maximum thermostat targets, sample
interval, maximum step change and minimum meaningful change. Defaults are
conservative: **300 seconds per cycle, up to 0.5°C change per cycle, 1.5°C
maximum trim**. The controller waits for enough fresh measurements before its
first command.

Kp is measured in percentage points of PID demand per °C; Ki in percentage
points per (°C·minute), and Kd in percentage points·minute per °C. The derivative
is taken from observed room temperature, and an anti-windup guard prevents
further integral growth into a saturated output. Demand maps into a heating
setpoint between `target` and `target + offset`, or a cooling setpoint
between `target - offset` and `target`. It is not a compressor duty cycle.

### Manual controls and failure safety

- A user changing thermostat target or HVAC mode pauses that room's PID.
  Such pauses are saved across Home Assistant restarts; the user must explicitly
  resume after checking the current thermostat state.
- Use the **Pause PID / Resume PID** button on the room's Lovelace card or
  the action `home_environment_manager.pid_control` with an explicit
  `area` and `action: pause | resume | reset`. Reset clears PID history and
  remains paused until separately resumed.
- Missing or stale sensor input, open/unknown windows, active thermostat presets,
  unsupported single-setpoint devices, wrong-area targets, duplicate climate
  assignments and invalid device units cause control to stop rather than guess.
  A Home Assistant service-write failure requires manual resume.
- Thermostat setpoint acknowledgements are checked against the exact entity
  selected. Unacknowledged writes or an unexpected manual setpoint change
  result in a persistent pause, not repeated commands.
- An integration reload cancels pending PID tasks. PID calculations and
  manual pause state use local Home Assistant storage and do not require a cloud
  controller. Restored PID state is never used to power on or restart hardware.

All existing sensor entities, native announcement actions, room calibration,
environmental-science observations and Lovelace card identifiers are preserved.
One room may control multiple explicitly selected thermostats, but the same
climate entity cannot be assigned to more than one enabled PID room.

**Safety:** Home Environment Manager is not a certified heater, boiler,
compressor, frost-prevention or life-safety controller. Leave independent
hardware overtemperature/frost/compressor protections in place. It is not
recommended to put medical, industrial or freeze-sensitive loads under this
experimental supervisory controller without independent safeguards. No climate
commands are sent until the user enables PID for that room.

## Climate room profiles and automatic control (development branch)

The next Home Environment Manager climate update builds on v0.5.0's
conservative thermostat-setpoint PID. It distinguishes **four controller
strategies by actual Home Assistant capabilities**, rather than equating a
thermostat with a relay:

| Equipment and strategy | Commands | Hard limitations |
| --- | --- | --- |
| Built-in thermostat (`climate.*`) | `climate.set_temperature`; optionally `climate.set_hvac_mode` | Requires TARGET_TEMPERATURE support. Automatic heat/cool mode changes need a *second* explicit opt-in, minimum mode dwell and acknowledgement. An OFF thermostat is not restarted. |
| Native heat/cool range thermostat (`climate.*`) | `climate.set_temperature` with both `target_temp_low` and `target_temp_high` | Requires TARGET_TEMPERATURE_RANGE feature and an *already active* `heat_cool` mode; preserves device's compressor safety, bounds both setpoints and pauses on manual range changes. |
| Existing v0.5 setpoint PID (`climate.*`) | Rate-limited `climate.set_temperature` only | Can never run alongside another enabled room controller. |
| Non-compressor heating/cooling relay (`switch.*`) | `switch.turn_on`/`turn_off` | Explicit non-compressor/independent-protection attestation, room ownership, hysteresis, minimum ON/OFF intervals and maximum ON watchdog. |
| Slow thermal PWM relay (`switch.*`) | Bounded time-proportioning ON/OFF | Only loads documented as safe for repeated switching; fixed PWM period and minimum pulse durations. **Never attach a compressor or unprotected resistive heater.** |
| True proportional actuator (`number.*`) | `number.set_value` | Sensor must expose a verified 0–100% output with unit `%`, range 0–100 and valid step; rate-limited commands. |

A `climate.*` entity that only exposes heat/off control is **not** assumed
to be safe for rapid relay PWM. Direct actuators must be assigned to the
actual HA room, with explicit heat/cool output selectors and confirmation of
hardware type. The integration does not discover or infer compressor safety.

### Configure temperatures, occupancy and schedules

Open **Home Environment Manager → Configure → Climate**. For each monitored
room:

1. Select a real temperature sensor, controller strategy and target devices.
   Enable the room and then separately authorize actuator commands if wanted.
   Optional automatic native heat/cool switching is another distinct setting.
2. Select a subset of occupancy sensors or leave it empty to use **all
   Home Assistant presence/occupancy binary sensors assigned to that room**.
   Any occupied sensor wins. All known-off sensors must remain off for the
   configured vacancy delay before an unoccupied setback takes effect.
   Stale/unknown readings do not automatically prove vacancy.
3. Choose any supported `person.*`, `device_tracker.*`, or explicitly
   selected home-presence `binary_sensor.*` entities for whole-home
   home/away decisions. A named zone such as work is considered away.
4. Configure an optional **local-time sleeping schedule**, manual profile
   override, and your desired temperature control basis.
5. Set **separate heating/cooling bands** for *home, unoccupied, away
   and sleep*. Heat and cool thresholds must remain separated by a deadband;
   mode changes are filtered through hysteresis. The default example
   setpoints (20/26°C at home, 18/28°C unoccupied, 16/30°C away and
   18/26°C sleeping) are only starting points, not universal comfort targets.
6. If choosing a relay, PWM or proportional driver, a separate **Direct
   Actuators** page collects exact entities, hardware attestation,
   minimum-on/off times, maximum runtime and applicable PID/PWM bounds.

Each room is configured independently. All global and local settings work
with any supported Home Assistant provider and local timezone; no German,
Greek or other national integration is hardcoded.

### Optional scientific comfort targeting

Two target-selection modes are supported:

- **Temperature:** use the explicit profile heating/cooling bands.
- **ISO 7730 PMV:** when enabled in the room's advanced environmental
  measurements, require a genuine mean radiant temperature, humidity,
  measured/explicit air speed, clothing insulation (clo), and activity (met).
  The bundled dependency-free Fanger implementation solves a bounded air
  temperature corresponding approximately to PMV 0. The correction to the
  owner's chosen temperature bands is capped; without valid current physical
  inputs the fixed profile targets remain in force. No PMV-based correction
  is applied to away/unoccupied setbacks.

ISO 7730 is a *population thermal-comfort model*, not a personalized
guarantee. A PMV-derived target assumes the other model inputs stay fixed;
actual indoor radiant temperature and airflow can change with HVAC operation.
See the [pythermalcomfort model documentation](https://pythermalcomfort.readthedocs.io/en/stable/documentation/models.html).

### Safety and scope

Direct actuator control requires real-world commissioning. The code contains
restart-persistent manual pauses, output acknowledgement, explicit room/device
ownership, heating/cooling interlocks, short service-call timeouts, a
maximum-on safeguard and best-effort safe-off on controller pause or reload
for devices it previously operated. Unowned active outputs are *not* silently
overwritten. If a relay cannot be verified OFF or an integration becomes
unresponsive, hardware cutouts remain indispensable.

**This v0.6 climate expansion is currently a draft implementation, not a
released update.** Integration and simulation tests must pass before
publication, followed by controlled testing with representative actual
hardware. Direct relay/PWM modes are for slow, safely protected thermal
loads; they must not control compressor power circuits or serve as the sole
frost/overtemperature protection.


### Multi-device room equipment (v0.6 development branch)

The **Climate** options now include an additional equipment page. You can
assign a dedicated heating climate (such as a radiator), cooling climate
(such as an AC or reversible heat pump), native DRY/FAN_ONLY climate entities,
a humidifier, dehumidifier, extraction fan and purifier fan. The wizard
restricts options to the selected Home Assistant area and can select a single
known humidity sensor for configurable humidity bands and hysteresis.

Each candidate is checked against its actual Home Assistant `hvac_modes`,
`supported_features` or humidifier `device_class`. The planner identifies
active opposing heating/cooling, missing measurements and ownership conflicts
if a device is assigned to multiple rooms. Climate-only rooms need not have a
window contact; existing monitored rooms still block control if their required
window contact disappears.

**Native humidity setpoint (extra opt-in):** With climate actuation and
**Allow native humidity setpoint changes** enabled, the integration may
adjust the target on an already-on selected `humidifier.*` or
`dehumidifier.*`. It requires a fresh, explicitly chosen same-room humidity
sensor, the verified device class and native limits. Commands are bounded,
rate-limited and acknowledged; manual target changes suspend control until
explicit resume. It never turns the device on or off or changes its mode.

**Remaining limits:** The existing primary thermostat retains its own native
heat/cool control. Additional radiator/AC/heat-pump routing, switching into
DRY/FAN_ONLY, and operating extraction/purifier fans are still **advisory**:
no unverified device mode or compressor-power commands are issued. Actual
hardware commissioning and restart tests are still mandatory before releasing
v0.6.

## Known limitations

- Only the named supported metric/device classes and units are interpreted. Unrecognized AQI variants, CO/ozone/NO₂/SO₂, arbitrary provider attributes and event-based weather alerts are not guessed at. Add a normalized HA template sensor where necessary.
- The thresholds apply to individual current readings, rather than averaging over standardized pollutant exposure windows. Relative humidity alone does not account for absolute outdoor humidity; the advice is a useful home automation signal, not a guaranteed best ventilation strategy.
- Advisory window names/rooms depend on HA registry assignments. If window contacts are missing, a recommendation cannot name a window.
- Direct TTS is a standard `tts.speak` call and may interrupt the chosen media player; use Announcement Hub for its queued/synchronized room audio policies.
- Dynamic Home Assistant environment tests (config flow and live TTS/notifications) require a Home Assistant instance; the included automated tests cover the pure policy, not all integrations/providers.

## License

MIT © 2026 Chreece

## Project status, compatibility and releases

- **Home Assistant 2026.10+**; modern UI config/options flow and a bundled Lovelace dashboard card. The component ships local `custom_components/air_quality_advisor/brand/` assets for Home Assistant 2026.3+ as well as repository-level HACS assets.
- **HACS custom integration repository:** `hacs.json`, `manifest.json` and conventional `custom_components/` layout are included. Public HACS catalog inclusion is a separate community-review process.
- **Validations:** `pytest`, static syntax checks, JSON checks, HACS action and Hassfest run automatically on each completed push to main (plus optional manual validation). Actual platform compatibility and output delivery require a Home Assistant integration test; see the [release checklist](RELEASING.md).
- **Versions:** see [CHANGELOG.md](CHANGELOG.md). This release is a first testable version, not an independently verified stable integration. No automatic window opening/closing is performed.

## Support this project

If this integration helps, you can support ongoing development on [Ko-fi](https://ko-fi.com/chreece). Contributions and bug reports are welcome through the repository's [issues](https://github.com/Chreece/HA-Air-Quality-Advisor/issues).


### Home Assistant Python 3.14 installation (v0.5.1)

The v0.5.1 production hotfix removes the required `pythermalcomfort`/
Numba/`llvmlite` installation chain. `pmv_core.py` uses a compact,
reference-tested ISO 7730 Fanger scalar implementation without binary
scientific dependencies, preserving advanced thermal comfort calculations
in Home Assistant's Alpine/musl Python 3.14 environment. The experimental
v0.6 climate-device controls remain on the draft branch.


### Multi-device climate status in the Lovelace room panel (v0.6 draft)

The room's climate panel now reports **primary thermostat**, **secondary
heating/cooling**, and **native humidity target supervision** separately.
Selecting a secondary AC no longer makes the primary thermostat's hold
status appear as if all climate control has failed. The selected equipment,
room humidity evidence and pause/resume state remain visible with English,
German and Greek labels. Device ID and diagnostic reason are shown for audit.
All operations remain entity-targeted and retain the existing climate-control
pause/resume action; secondary DRY/FAN modes are still advisory.


### Climate air-treatment and verified fan speed (v0.6 draft)

The new room air-treatment wizard selects actual same-room CO₂ and PM2.5
sensors, an explicitly chosen short-term **operational** PM2.5 action threshold
(not a WHO exposure threshold), and desired upper fan speeds. It records the
user's NDIR/particle-sensor verification and only provides automatic
percentage changes after separate consent. Indoor–outdoor moisture-ratio
evidence determines whether ventilation would remove or add moisture.

The coordinator reports distinct **extraction** and **filtration** intentions.
When CO₂ is high, extraction is recommended only if outside air was assessed
safe; verified NDIR inputs and a specific sensor are required for actual fan
speed control. When PM2.5 indoors exceeds the configured action threshold,
filtration remains an option even while windows should stay closed.
Moisture-only extraction remains **advisory** until outdoors sensors and fan
physical behavior can be commissioned.

An enabled fan speed controller uses `fan.set_percentage` on an already-on
room fan only, increases by at most 10 percentage points per five-minute
interval, requires a known native speed step and command acknowledgments,
pauses on a manual speed change and never sets 0% or sends on/off/preset
actions. Unverified devices remain advisory and the controller will not
power any purifier or ventilation equipment on.


### Climate-only rooms without window sensors

Climate can be configured for a Home Assistant area even when there is no
window contact in the room. These areas now appear as dedicated **climate
cards** in the Lovelace view with their controller and equipment diagnostics.
They are not automatically counted as air-quality safe (or unsafe), do not
receive invented window recommendations, and do not change the number of
monitored areas or Announcement Hub delivery targets. Existing monitored
rooms continue to use strict window-contact interlocks.
