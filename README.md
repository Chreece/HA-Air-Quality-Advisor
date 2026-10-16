<p align="center">
  <img src=".github/assets/air-quality-advisor-banner.jpg" alt="Air Quality Advisor — local window and ventilation advice" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-Air-Quality-Advisor/releases"><img src="https://img.shields.io/github/v/release/Chreece/HA-Air-Quality-Advisor?include_prereleases&amp;display_name=tag" alt="Release"></a>
  <a href="https://www.hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5" alt="HACS"></a>
  <a href="https://github.com/Chreece/HA-Air-Quality-Advisor/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-2aa198" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&amp;repository=HA-Air-Quality-Advisor&amp;category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open in HACS">
  </a>
</p>

# Air Quality Advisor for Home Assistant

**One recommendation entity for all the rooms you select.** It compares indoor CO₂, AQI, particles, VOCs and humidity against outdoor air quality, current weather and selected weather-warning entities, then recommends **which windows to open or close and why**. Announcements are entirely optional.

> This project is an advisor, **not an automatic window actuator**, medical device, emergency warning system, or authoritative weather alert. It never controls covers. Outdoor warnings and uncertain conditions are intentionally treated as blockers.

<p align="center">
  <img src=".github/assets/how-it-works.svg" alt="Air quality, weather and warning sensors feed one window recommendation entity and optional announcement outputs" width="100%">
</p>

## What it provides

- A single `sensor.air_quality_advisor_window_recommendations` (actual entity ID may vary with user settings). States: `open`, `close`, `idle`, `blocked`.
- Attributes: `open_windows`, `close_windows`, structured `recommendations` with windows, room/area, sensor reason, value and localised message, `outside_blockers`, `diagnostics`, `outdoor_safe`, `announcement_hub_available`.
- Event-driven updates and periodic 5-minute freshness checks. No external APIs, daemons, cloud credentials or Home Assistant tokens. Uses existing entities only.
- A guided four-step setup. Indoor measurements and window contacts are automatically discovered from each selected area's HA entity/device registry assignments. Configurable thresholds are tucked into **Configure → Advanced thresholds**.
- Optional room-aware [Announcement Hub](https://github.com/Chreece/HA-Announcement-Hub) output (`notify.announcement_hub`), **or** direct `notify.send_message` and `tts.speak` via supported entities. Not installing Announcement Hub does not affect the recommendation sensor.
- Auto notifications/TTS can each be enabled or disabled independently. Open announcements wait 90 seconds for conditions to stay stable; close announcements are immediate. Repeated open recommendations have a 15-minute cooldown during the current HA process. New urgent close recommendations are not suppressed by that cooldown, even if the same window was reopened. No notification is generated on every unchanged sensor reading.
- Manual `air_quality_advisor.announce` action, with independent **English, German, Greek, French or Spanish** language selection every time.

## Installation

### HACS (custom repository)

1. In HACS, open **Custom repositories**; enter `https://github.com/Chreece/HA-Air-Quality-Advisor` and choose **Integration**.
2. Install **Air Quality Advisor**, restart Home Assistant and add it under **Settings → Devices & services → Add integration**.
3. No YAML configuration is required.

### Manual

Copy `custom_components/air_quality_advisor/` to `<your Home Assistant config>/custom_components/air_quality_advisor/`, restart HA, then add the integration from the UI. Alternatively, from the extracted repository run:

```bash
HA_CONFIG=/path/to/homeassistant/config bash ./install.sh
```

The installer writes **only** the integration directory, makes a rollback backup of an older installation and does not restart HA or end your SSH session.

## Guided configuration

1. **Areas — multi-select.** Select your monitored rooms. They need a Window-class binary sensor or Window-class cover, plus room air-quality sensors. Select an area and assign entities to it in Home Assistant's entity/device settings; arbitrary names are not interpreted as room mappings.
2. **Outdoor air-quality sensors — multi-select.** Only supported sensors with recognizable metric and compatible units are selectable. Sensors assigned to the monitored indoor areas are excluded from the outdoor choices. A sensor without a device class can be recognized by a strictly matched suffix like `_co2`, `_pm25`, `_pm2_5`, `_pm10`, `_aqi` or `_tvoc`, *and* an appropriate unit. Assign outdoor sensors to an Outside area, or leave them unassigned. All selected sensors must be safe and fresh for an open recommendation.
3. **Weather and warnings — multi-select.** Pick one or more `weather.*` entities and optionally warning sensors. Relevant `binary_sensor`/`sensor` warnings are discovered by common names used by DWD, Meteoalarm, NINA and other providers; no vendor-specific services or APIs are assumed. If your provider exposes only a special event type or differently named entity, first create a normal binary or numeric warning sensor in HA.
4. **Announcements (optional).** Choose a language and enable automatic notifications and/or speech. When Announcement Hub is present, the wizard can route announcements through it, respecting selected area IDs. Otherwise select `notify.*` recipients, a `tts.*` engine and `media_player.*` output(s). Room-assigned direct outputs receive only their own room's recommendation; unassigned outputs receive all recommendations.

Click **Configure** on the integration to open a short three-choice menu: **Areas / Outdoor / Weather**, **Announcements**, or **Advanced thresholds**. Changing one section doesn't require stepping through the others. One integration instance covers the selected rooms; no entity per room is generated.

### Supported indoor and outdoor measurements

| Measurement | Supported unit(s) | Outdoor good at or below | Indoor requires ventilation at or above |
|---|---|---:|---:|
| AQI — **US scale 0–500** | index / none / AQI | 50 | 100 |
| CO₂ | ppm | 800 | 1,000 |
| PM2.5 | µg/m³ or mg/m³ | 15 | 25 |
| PM10 | µg/m³ or mg/m³ | 45 | 45 |
| Total VOC | µg/m³ or mg/m³ | 500 | 500 |
| VOC concentration (parts) | ppb or ppm | 500 ppb | 500 ppb |
| Relative humidity | % | — | 65% |

Sensor values are normalised to the units above. Outdoor temperatures from weather entities must remain from **5–32 °C**, humidity at most **85%** and wind at most **35 km/h** when those attributes are provided. Supported fair weather states: `sunny`, `clear-night`, `partlycloudy`, `cloudy`. All other states, including rain, snow, thunderstorms, fog and high wind, block opening. Selected warnings that are active **or cannot be verified** also block opening. Weather providers with unknown state block opening. Selected outdoor data older than 90 minutes (using `last_reported` when available) block opening; adjust the time in advanced options.

**AQI scales differ internationally.** A European 1–5 index is *not* the US 0–500 AQI. For 1–5 index sensors, change the outdoor AQI limit (for example `2`) and indoor AQI trigger (for example `3`) in advanced options, or use the measured pollutant sensors instead. Numeric thresholds are configurable per installation, not per sensor, and do not represent exposure-duration standards.

### Decision policy

| Outdoor state | Indoor state and windows | Recommendation |
|---|---|---|
| Good, no selected warnings | Indoor CO₂/particles/VOC/AQI/humidity exceed a threshold and all room windows are closed | **Open** the room's recognized windows, with the measured reason |
| Bad, rainy, extreme, warning active or unknown | Any recognized window is actually open | **Close** each open window, with outdoor blocker(s) |
| Good | Room already has a window open | No further open action (ventilation already underway) |
| Good | Indoor values acceptable | `idle` |
| Uncertain outside | No windows verified open | `blocked`; no open recommendation |
| No room sensor or window contact | Missing information | No guessed recommendation; diagnostics attribute identifies the gap |

A `cover` with the `window` device class is recognized as open/closed, but the integration **never calls** `cover.open_cover` or `cover.close_cover`. Other sensors (door/motion/etc.) are intentionally not treated as windows. When a selected outside sensor is missing/unavailable/unsupported or a warning cannot be interpreted reliably, safe opening cannot be asserted.

## The one sensor

<p align="center">
  <img src=".github/assets/recommendation-preview.svg" alt="Illustrated recommendation for closing a window during a weather warning" width="100%">
</p>


Typical state when CO₂ is high but outdoor air and weather are good:

```yaml
state: open
attributes:
  outdoor_safe: true
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

## Announcing in a different language on each action

```yaml
action: air_quality_advisor.announce
data:
  language: el  # en, de, el, fr, es
  channels: both  # both, tts, notification
  areas:
    - living_room
```

Omit `areas` to report every room with an actionable recommendation. The manual action can be called even when automatic TTS/notifications are disabled. Passing `language` changes the **generated recommendation text** and requests the matching speech language. Actual spoken voice availability depends on the selected TTS provider. The service may report accepted/submitted requests; this does not guarantee a physical speaker played audio or a notification was displayed.

Announcement Hub delivery uses the established action:

```yaml
action: notify.announcement_hub
data:
  text_notify: "...localized room recommendation..."
  text_tts: "...localized room recommendation..."
  output:
    - living_room
  level: warning
  occupied_only: false
```

This integration emits that action automatically when enabled. Explicit room routing is intentionally not filtered by occupancy; messages about windows needing to be closed must be able to reach the room's configured outputs. If the Hub action is missing or rejects a submission, explicit standalone notification/TTS outputs can be used instead.

## Testing, validation, and publishing

```bash
python -m pytest -q tests
python -m compileall -q custom_components
bash ./publish.sh
```

`publish.sh` requires a previously authenticated GitHub CLI (`gh auth status`) and creates `Chreece/HA-Air-Quality-Advisor` if absent. It **never force-pushes** or mutates other repositories. GitHub Actions are **manual-only** (`workflow_dispatch`) to prevent push/PR notification spam during development. Before publishing a release, manually trigger **Validate (manual only)** and check all jobs. A GitHub release (`v0.1.0` recommended) and registered Home Assistant brand assets may still be needed for HACS *default-store listing*; use as a custom repository immediately after publishing.

## Known limitations

- Only the named supported metric/device classes and units are interpreted. Unrecognized AQI variants, CO/ozone/NO₂/SO₂, arbitrary provider attributes and event-based weather alerts are not guessed at. Add a normalized HA template sensor where necessary.
- The thresholds apply to individual current readings, rather than averaging over standardized pollutant exposure windows. Relative humidity alone does not account for absolute outdoor humidity; the advice is a useful home automation signal, not a guaranteed best ventilation strategy.
- Advisory window names/rooms depend on HA registry assignments. If window contacts are missing, a recommendation cannot name a window.
- Direct TTS is a standard `tts.speak` call and may interrupt the chosen media player; use Announcement Hub for its queued/synchronized room audio policies.
- Dynamic Home Assistant environment tests (config flow and live TTS/notifications) require a Home Assistant instance; the included automated tests cover the pure policy, not all integrations/providers.

## Compatibility and release readiness

**Home Assistant 2026.10+** is the declared minimum. The integration ships its own brand files under `custom_components/air_quality_advisor/brand` for Home Assistant 2026.3+ and keeps HACS-compatible assets at repository level. HACS can install directly from the default branch without a formal GitHub release. Automated tests pass locally; the `Validate (manual only)` workflow offers HACS and Hassfest checks. Please validate the configuration UI and real TTS/notification outputs in a live HA instance before labeling this a stable release. See [CHANGELOG](CHANGELOG.md) and [RELEASING](RELEASING.md).

## Support the development

<a href="https://ko-fi.com/chreece"><img src=".github/assets/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="500"></a>

## License

MIT © 2026 Chreece
