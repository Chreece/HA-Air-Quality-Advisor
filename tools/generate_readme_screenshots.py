#!/usr/bin/env python3
"""Render the bundled Lovelace card with deterministic SAMPLE Home Assistant data.

These are screenshots of the actual web-component implementation, not separate
illustrations. They are not captures of a user's live Home Assistant instance.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / ".github" / "assets" / "screenshots"
CARD_JS = ROOT / "custom_components" / "air_quality_advisor" / "frontend" / "air-quality-advisor-card.js"

CSS = """
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:Inter,Roboto,Arial,sans-serif}
body{background:#ebf3f6;color:#17313c}
body[data-theme=dark]{background:#101c28;color:#e2edf0;color-scheme:dark}
#frame{padding:32px 34px 34px;margin:0 auto}
#frame[data-mobile]{padding:14px 12px 18px}
.demo-label{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 5px 18px}
.demo-label span:first-child{font-size:12px;font-weight:800;letter-spacing:.12em;color:#537785}
.demo-label span:last-child{font-size:10px;font-weight:650;color:#698997;background:#dceef4;border:1px solid #c5dfe8;border-radius:12px;padding:6px 9px;white-space:nowrap}
[data-theme=dark] .demo-label span{color:#b8ccd6!important}
[data-theme=dark] .demo-label span:last-child{background:#172a37;border-color:#344a59}
#preview{--card-background-color:#fff;--primary-text-color:#163642;--secondary-text-color:#758b93;--divider-color:#dfeced}
[data-theme=dark] #preview{--card-background-color:#192a37;--primary-text-color:#e4f2f7;--secondary-text-color:#a2bac5;--divider-color:#334953}
ha-card{display:block}
ha-icon{display:inline-flex;align-items:center;justify-content:center;vertical-align:middle;line-height:1;min-width:1em;font-size:var(--mdc-icon-size,22px);width:var(--mdc-icon-size,22px);height:var(--mdc-icon-size,22px)}
"""

ICON_STUB = r"""
const icons={
'mdi:air-filter':'≋','mdi:home-check-outline':'⌂','mdi:home-alert-outline':'⌂',
'mdi:home-question-outline':'⌂','mdi:home-heart':'⌂','mdi:weather-sunny':'☀',
'mdi:weather-partly-cloudy':'⛅','mdi:weather-cloudy':'☁','mdi:weather-rainy':'☂',
'mdi:weather-windy':'≋','mdi:window-closed-variant':'▣',
'mdi:window-open-variant':'◩','mdi:molecule-co2':'◎','mdi:blur':'⋮',
'mdi:check-circle-outline':'✓','mdi:alert-circle-outline':'!',
'mdi:help-circle-outline':'?','mdi:check':'✓','mdi:alert':'!',
'mdi:water-percent':'♒','mdi:shield-check-outline':'✓','mdi:gauge-empty':'○',
'mdi:information-outline':'i','mdi:flask-outline':'⚗','mdi:weather-night':'☽',
'mdi:home-outline':'⌂','mdi:chevron-down':'⌄','mdi:chevron-up':'⌃'};
customElements.define('ha-card',class extends HTMLElement{});
customElements.define('ha-icon',class extends HTMLElement{
 connectedCallback(){this.textContent=icons[this.getAttribute('icon')]||'•';this.style.fontWeight='750';}
});
"""

ENTITY = "sensor.air_quality_advisor_window_recommendations"

def reading(metric: str, value: float, threshold: float, unit: str) -> dict:
    return {"entity_id":f"sensor.demo_{metric}","name":metric,"metric":metric,
            "value":value,"threshold":threshold,"unit":unit,"available":True,
            "exceeded":value >= threshold}

def window(room: str, opened: bool = False) -> dict:
    return {"name":f"{room} window",
            "entity_id":"binary_sensor."+room.lower().replace(" ","_")+"_window",
            "opened":opened}

def room(key: str, name: str, status: str, readings: list[dict],
         opened: bool = False, action: str | None = None) -> dict:
    contact = window(name, opened)
    return {"area_id":key,"name":name,"status":status,"action":action,
            "action_window_ids":[contact["entity_id"]] if action else [],
            "high_count":sum(bool(v["exceeded"]) for v in readings),
            "available_count":len(readings),"ventilating":opened and action!="close",
            "window_count":1,"open_count":int(opened),"readings":readings,
            "windows":[contact],"reasons":[]}

GOOD_ROOMS = [
    room("living","Living room","attention",
         [reading("co2",1385,1000,"ppm"),reading("pm25",13,25,"µg/m³"),
          reading("humidity",48,65,"%")],action="open"),
    room("bed","Bedroom","safe",
         [reading("co2",612,1000,"ppm"),reading("pm25",7,25,"µg/m³"),
          reading("humidity",46,65,"%")]),
    room("kitchen","Kitchen","safe",
         [reading("co2",742,1000,"ppm"),reading("humidity",44,65,"%")]),
    room("office","Office","unknown",[]),
]
GOOD_OUTSIDE = {
    "status":"safe","safe_to_ventilate":True,"data_complete":True,
    "readings":[reading("pm25",8,15,"µg/m³"),reading("aqi",28,50,"AQI")],
    "weather":[{"entity_id":"weather.demo","condition":"partlycloudy",
                "temperature_c":21.4,"humidity":49,"wind_kmh":9}],
    "warnings":[],"blockers":[],"unavailable_sensors":[]}
BAD_OUTSIDE = {
    "status":"unsafe","safe_to_ventilate":False,"data_complete":True,
    "readings":[reading("pm25",34,15,"µg/m³"),reading("aqi",91,50,"AQI")],
    "weather":[{"entity_id":"weather.demo","condition":"rainy",
                "temperature_c":12.3,"humidity":85,"wind_kmh":32}],
    "warnings":[{"entity_id":"binary_sensor.storm_alert",
                 "name":"Wind and rain advisory","active":True}],
    "blockers":[{"code":"outside_pm25","label":"Outdoor particles",
                 "value":"34 µg/m³"}],"unavailable_sensors":[]}
SCENARIOS = [
    ("dashboard-overview-light.png", 990, "light", "en",
     "DESKTOP · LIGHT THEME", GOOD_ROOMS, GOOD_OUTSIDE),
    ("dashboard-greek-dark.png", 940, "dark", "el",
     "ΕΛΛΗΝΙΚΑ · ΣΚΟΥΡΟ ΘΕΜΑ", GOOD_ROOMS[:3], GOOD_OUTSIDE),
    ("dashboard-mobile.png", 396, "light", "en",
     "MOBILE · RESPONSIVE CARD", GOOD_ROOMS[:3], GOOD_OUTSIDE),
    ("dashboard-outdoor-alert.png", 900, "dark", "en",
     "OUTDOOR WARNING · CLOSE WINDOWS", [
         room("living","Living room","attention",
              [reading("co2",1370,1000,"ppm"),reading("pm25",13,25,"µg/m³")],
              opened=True,action="close"),
         room("bed","Bedroom","safe",
              [reading("co2",675,1000,"ppm"),reading("humidity",49,65,"%")]),
     ], BAD_OUTSIDE),
]

def main() -> None:
    ASSETS.mkdir(parents=True,exist_ok=True)
    script = CARD_JS.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True,args=["--no-sandbox"])
        for filename,width,theme,language,caption,rooms,outside in SCENARIOS:
            page = browser.new_page(
                viewport={"width":width,"height":900},
                device_scale_factor=2 if width<500 else 1.5)
            page.set_content(
                '<!doctype html><html><head><meta charset="utf-8"><style>'
                +CSS+'</style></head><body><main id="frame"><div class="demo-label">'
                +'<span>'+caption+'</span><span>DEMO SENSOR DATA</span>'
                +'</div><div id="preview"></div></main></body></html>')
            page.locator("body").evaluate("(el,theme)=>el.dataset.theme=theme",theme)
            if width<500:
                page.locator("#frame").evaluate("(el)=>el.dataset.mobile=''")
            page.evaluate(ICON_STUB)
            page.add_script_tag(content=script)
            state={"version":1,"summary":{
                "total":len(rooms),
                "safe":sum(r["status"]=="safe" for r in rooms),
                "attention":sum(r["status"]=="attention" for r in rooms),
                "unknown":sum(r["status"]=="unknown" for r in rooms)},
                "rooms":rooms,"outdoor":outside}
            page.evaluate("""({language,data,entity})=>{
                const card=document.createElement('air-quality-advisor-card');
                card.setConfig({entity});
                card.hass={language,states:{[entity]:{state:'open',attributes:{dashboard:data}}}};
                document.getElementById('preview').appendChild(card);
            }""",{"language":language,"data":state,"entity":ENTITY})
            page.wait_for_timeout(120)
            assert page.locator("air-quality-advisor-card").count()==1
            assert page.locator("air-quality-advisor-card").evaluate(
                "(el)=>Boolean(el.shadowRoot?.querySelector('.donut'))"
            ),f"Failed to render Lovelace card: {filename}"
            with tempfile.TemporaryDirectory() as temp:
                original=Path(temp)/"raw.png"
                page.locator("#frame").screenshot(
                    path=str(original),animations="disabled")
                with Image.open(original) as im:
                    rgb=im.convert("RGB")
                    reduced=rgb.resize(
                        (round(rgb.width*.75),round(rgb.height*.75)),
                        Image.Resampling.LANCZOS)
                    # 128-color indexed PNG keeps text readable and README light.
                    optimized=reduced.quantize(
                        colors=128,method=Image.Quantize.FASTOCTREE,
                        dither=Image.Dither.NONE)
                    target=ASSETS/filename
                    optimized.save(target,format="PNG",optimize=True,
                                   compress_level=9)
                    print(f"{target.relative_to(ROOT)}: "
                          f"{optimized.width}x{optimized.height}, "
                          f"{target.stat().st_size:,} bytes")
            page.close()
        browser.close()

if __name__=="__main__":
    main()
