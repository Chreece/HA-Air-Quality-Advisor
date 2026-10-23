"""Build beta20: actual enviroment_manager domain + runtime/UI corrections.

One-use staging helper. Removed from final source.
"""
from __future__ import annotations
from pathlib import Path
import json, re, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
OLDPKG=ROOT/"custom_components"/"environment_manager"
NEWPKG=ROOT/"custom_components"/"enviroment_manager"

def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout

def require_replace(path, old, new, count=-1):
    text=path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Missing anchor in {path}: {old[:100]!r}")
    path.write_text(text.replace(old,new,count),encoding="utf-8")

def main():
    if not OLDPKG.is_dir() or NEWPKG.exists():
        raise RuntimeError("Expected canonical environment_manager staging package")
    subprocess.run(["git","mv",str(OLDPKG.relative_to(ROOT)),str(NEWPKG.relative_to(ROOT))],
                   cwd=ROOT,check=True)

    # User explicitly requested this HA domain spelling.
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py",".json",".yaml",".yml",".js",".md"}:
            continue
        text=path.read_text(encoding="utf-8")
        text=text.replace("custom_components.environment_manager","custom_components.enviroment_manager")
        text=text.replace("custom_components/environment_manager","custom_components/enviroment_manager")
        text=text.replace('"environment_manager"','"enviroment_manager"')
        text=text.replace("'environment_manager'","'enviroment_manager'")
        text=text.replace("refs/heads/beta/v0.6.0b19","refs/heads/beta/v0.6.0b20")
        path.write_text(text,encoding="utf-8")

    # ---- One General settings page only. ----
    room=NEWPKG/"room_setup.py"
    text=room.read_text(encoding="utf-8")
    text=text.replace('''        self._setup_general_draft = {}
        self._setup_general_rendered = {}
''','')
    text=text.replace('''        defaults.update(self._setup_general_draft)
''','')
    rerender='''            if self._setup_general_rendered.get(CONF_TTS_ENGINE) not in (None, value[CONF_TTS_ENGINE]):
                self._setup_general_draft = value
                self._setup_general_rendered[CONF_TTS_ENGINE] = value[CONF_TTS_ENGINE]
                return await self.async_step_setup_general()
            refreshed = False
            for prefix in ("occupied", "sleep"):
                entity_key, attr_key = f"general_{prefix}_rooms_entity", f"general_{prefix}_rooms_attribute"
                entity = value[entity_key]
                if entity == "none":
                    value[attr_key] = "__state__"
                    continue
                attrs = self._room_attribute_options(self.hass, entity)
                allowed = {a["value"] for a in attrs}
                if self._setup_general_rendered.get(entity_key) != entity:
                    value[attr_key] = value[attr_key] if value[attr_key] in allowed else attrs[0]["value"]
                    refreshed = True
                elif value[attr_key] not in allowed:
                    errors[attr_key] = "invalid_room_source"
            if not errors and refreshed:
                self._setup_general_draft = value
                return await self.async_step_setup_general()
'''
    replacement='''            # General settings is a single page. Dependent values are normalized
            # on submit instead of showing the exact same page a second time.
            for prefix in ("occupied", "sleep"):
                entity_key, attr_key = f"general_{prefix}_rooms_entity", f"general_{prefix}_rooms_attribute"
                entity = value[entity_key]
                if entity == "none":
                    value[attr_key] = "__state__"
                    continue
                attrs = self._room_attribute_options(self.hass, entity)
                allowed = {a["value"] for a in attrs}
                if value[attr_key] not in allowed:
                    value[attr_key] = "__state__"
'''
    if rerender not in text: raise RuntimeError("General re-render block changed")
    text=text.replace(rerender,replacement)
    text=text.replace('''                attrs = self._room_attribute_options(self.hass, value[key])
                chosen = value[attr_key] if value[attr_key] in {a["value"] for a in attrs} else attrs[0]["value"]
                fields[field(attr_key, chosen)] = select(attrs)
                self._setup_general_rendered[key] = value[key]
''','''                # Offer the union of relevant attributes from all room-list
                # candidates so entity + attribute can be chosen on this one page.
                attrs_by_value = {"__state__": {"value": "__state__", "label": "State"}}
                for candidate in options[key]:
                    entity_id = candidate["value"]
                    if entity_id == "none":
                        continue
                    for option in self._room_attribute_options(self.hass, entity_id):
                        attrs_by_value.setdefault(option["value"], option)
                attrs = list(attrs_by_value.values())
                chosen = value[attr_key] if value[attr_key] in attrs_by_value else "__state__"
                fields[field(attr_key, chosen)] = select(attrs)
''')
    text=text.replace('''        self._setup_general_rendered[CONF_TTS_ENGINE] = value[CONF_TTS_ENGINE]
''','')
    room.write_text(text,encoding="utf-8")

    # ---- No allow_power entity or backend setting. Control method owns it. ----
    sw=NEWPKG/"switch.py"
    text=sw.read_text(encoding="utf-8")
    text=re.sub(r'''    entities\.extend\(EquipmentQuietSwitch\(manager, spec, "allow_power"\)\n                    for spec in equipment\.specs\(manager\)\n                    if \(cap := equipment\.capabilities\(manager, spec\)\) is not None\n                    and cap\.domain in \("climate", "fan", "humidifier"\) and "off" in cap\.modes\)\n''','',text)
    text=text.replace('{"allow_power": "mdi:power-settings", "sensor_verified": "mdi:check-decagram-outline"}',
                      '{"sensor_verified": "mdi:check-decagram-outline"}')
    text=re.sub(r'''        if self\._key == "allow_power" and self\._key not in self\.controller_settings:\n(?:            .*\n){1,8}''','',text)
    sw.write_text(text,encoding="utf-8")

    model=NEWPKG/"equipment_model.py"
    text=model.read_text(encoding="utf-8")
    old='''    if "_native_authorization" in cfg:
        from .device_activation import authorized
        valid = cap.domain in ("climate", "fan", "humidifier") and authorized(manager, spec)
        return valid, valid and cfg.get("allow_power") is True and "off" in cap.modes
'''
    new='''    if "_native_authorization" in cfg:
        from .device_activation import authorized
        valid = cap.domain in ("climate", "fan", "humidifier") and authorized(manager, spec)
        # Automatic/PID/Manual is the explicit permission for this exact native
        # controller. There is no second power/HVAC-mode switch.
        active = cfg.get("control_mode") in ("automatic", "pid", "manual", "off")
        return valid and active, valid and active and "off" in cap.modes
'''
    if old not in text: raise RuntimeError("permission allow_power anchor")
    model.write_text(text.replace(old,new),encoding="utf-8")

    runtime=NEWPKG/"equipment_runtime.py"
    text=runtime.read_text(encoding="utf-8")
    text=text.replace('''                "fan_mode", "swing_mode", "swing_horizontal_mode",
                "allow_power", "sensor_verified", *model.DEVICE_SELECTS}
''','''                "fan_mode", "swing_mode", "swing_horizontal_mode",
                "sensor_verified", *model.DEVICE_SELECTS}
''')
    old='''            for key in ("allow_power", "sensor_verified"):
                if key in changes and type(changes[key]) is not bool:
                    raise HomeAssistantError("Device permission must be a boolean")
            if "allow_power" in changes and cap.domain not in ("climate", "fan", "humidifier"):
                raise HomeAssistantError("Raw relay/proportional hardware needs its existing explicit commissioning")
'''
    if old not in text: raise RuntimeError("runtime permission validation anchor")
    text=text.replace(old,'''            if "sensor_verified" in changes and type(changes["sensor_verified"]) is not bool:
                raise HomeAssistantError("Sensor verification must be a boolean")
''')
    old='''            if authorizing:
                new["_native_authorization"] = authority_context(self.manager, spec)
                # Choosing Automatic/PID is explicit consent for this exact
                # native climate/fan/humidifier to start/stop and switch its
                # real HVAC mode when demand/policy requires it. Raw relays
                # remain separately commissioned.
                if new["control_mode"] in ("automatic", "pid") and "off" in cap.modes:
                    new["allow_power"] = True
                else:
                    new.setdefault("allow_power", power)
                soft = True
                power = new["allow_power"] is True
            elif "_native_authorization" in new:
                soft = new["_native_authorization"] == authority_context(self.manager, spec)
                power = soft and new.get("allow_power") is True
            if "allow_power" in changes and new["allow_power"] and "off" not in cap.modes:
                raise HomeAssistantError("The physical device has no supported OFF mode")
'''
    new='''            if authorizing:
                new["_native_authorization"] = authority_context(self.manager, spec)
                soft = True
                power = "off" in cap.modes
            elif "_native_authorization" in new:
                soft = new["_native_authorization"] == authority_context(self.manager, spec)
                power = soft and new.get("control_mode") in ("automatic", "pid", "manual", "off") and "off" in cap.modes
'''
    if old not in text: raise RuntimeError("runtime authorizing anchor")
    text=text.replace(old,new)
    text=text.replace(
        'raise HomeAssistantError("Enable Allow power and HVAC mode control on this controller device before changing its physical mode")',
        'raise HomeAssistantError("This controller is not authorized to change the physical mode")')
    runtime.write_text(text,encoding="utf-8")

    activation=NEWPKG/"device_activation.py"
    text=activation.read_text(encoding="utf-8")
    text=text.replace('''Choosing a method is explicit consent for native setpoint/speed regulation.
Power/mode changes have a separate device switch; raw relay commissioning is
never inferred.''','''Choosing Automatic, PID or Manual is explicit consent for this exact native
controller to regulate setpoints/speed and to turn its supported native mode
on/off as needed. Raw relay commissioning is never inferred.''')
    activation.write_text(text,encoding="utf-8")

    gen=ROOT/"apply_equipment_i18n.py"
    text=gen.read_text(encoding="utf-8")
    text=re.sub(r'''        add\("switch", "allow_power",.*\n''','',text)
    gen.write_text(text,encoding="utf-8")
    test=ROOT/"tests"/"test_equipment_i18n.py"
    text=test.read_text(encoding="utf-8")
    text=text.replace('"switch": ("quiet_sleep", "quiet_occupied", "allow_power", "sensor_verified"),',
                      '"switch": ("quiet_sleep", "quiet_occupied", "sensor_verified"),')
    test.write_text(text,encoding="utf-8")

    # ---- Room-owned preset targets only. ----
    controls=NEWPKG/"device_controls.py"
    text=controls.read_text(encoding="utf-8")
    start=text.index("DEVICE_TARGET_NUMBERS = {")
    end=text.index("\nCLIMATE_POLICY_OPTIONS =",start)
    text=text[:start]+'''DEVICE_TARGET_NUMBERS = {
    # Device-specific environmental/fan settings only. Temperature preset
    # targets are owned by the Room Environment device.
    "humidity_target": (20.0, 80.0, 1.0, "%", 50.0),
    "sleep_humidity_target": (20.0, 80.0, 1.0, "%", 50.0),
    "fan_speed_percent": (10.0, 100.0, 1.0, "%", 60.0),
}
'''+text[end:]
    text=text.replace('''                if key != "manual_profile" or value not in (
                    "auto", "home", "unoccupied", "away", "sleep"
                ):
''','''                if key != "manual_profile" or value not in (
                    "auto", "comfort", "home", "away", "sleep", "eco"
                ):
''')
    # Remove climate-device target handling from device_target backend.
    text=text.replace('''            if ((domain == "climate" and not key.endswith(("_heat_c", "_cool_c"))) or
                    (domain == "humidifier" and key not in ("humidity_target", "sleep_humidity_target")) or
''','''            if ((domain == "climate") or
                    (domain == "humidifier" and key not in ("humidity_target", "sleep_humidity_target")) or
''')
    climate_block='''            if domain == "climate":
                for profile in ("home", "unoccupied", "away", "sleep"):
                    heat = float(device_cfg.get(f"{profile}_heat_c", DEVICE_TARGET_NUMBERS[f"{profile}_heat_c"][4]))
                    cool = float(device_cfg.get(f"{profile}_cool_c", DEVICE_TARGET_NUMBERS[f"{profile}_cool_c"][4]))
                    if cool-heat < 1:
                        raise HomeAssistantError("Heat/cool policy targets require at least a 1°C deadband")
            elif domain == "fan":
'''
    if climate_block not in text: raise RuntimeError("device climate target block")
    text=text.replace(climate_block,'''            if domain == "fan":
''')
    controls.write_text(text,encoding="utf-8")

    numbers=NEWPKG/"number.py"
    text=numbers.read_text(encoding="utf-8")
    # Climate controllers no longer get duplicated per-device temperature presets.
    text=text.replace('''                if prefix == "climate":
                    chosen = [key for key in DEVICE_TARGET_NUMBERS if key.endswith(("_heat_c", "_cool_c"))]
                elif prefix == "humidifier":
''','''                if prefix == "climate":
                    chosen = []
                elif prefix == "humidifier":
''')
    numbers.write_text(text,encoding="utf-8")

    # Legacy/advanced forms, if reached, use the same public preset names.
    flow=NEWPKG/"config_flow.py"
    text=flow.read_text(encoding="utf-8")
    text=text.replace('("auto","home","unoccupied","away","sleep")',
                      '("auto","comfort","home","away","sleep","eco")')
    text=text.replace('("auto", "home", "unoccupied", "away", "sleep")',
                      '("auto", "comfort", "home", "away", "sleep", "eco")')
    flow.write_text(text,encoding="utf-8")

    pkg=ROOT/"custom_components"/"enviroment_manager"
    manifest=json.loads((pkg/"manifest.json").read_text(encoding="utf-8"))
    manifest["domain"]="enviroment_manager"
    manifest["version"]="0.6.0b20"
    (pkg/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\\n",encoding="utf-8")

    # Tests for the exact regressions.
    (ROOT/"tests"/"test_beta20_regressions.py").write_text(r'''"""b20 user-reported regressions without requiring HA at import time."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/"custom_components/enviroment_manager"

def source(name):
    return (PKG/name).read_text(encoding="utf-8")

def test_exact_requested_domain_and_only_one_package():
    manifest=(PKG/"manifest.json").read_text()
    const=source("const.py")
    assert '"domain": "enviroment_manager"' in manifest
    assert 'DOMAIN = "enviroment_manager"' in const
    assert 'LEGACY_DOMAIN = "air_quality_advisor"' in const
    assert PKG.is_dir()
    assert not (ROOT/"custom_components/environment_manager").exists()
    assert not (ROOT/"custom_components/air_quality_advisor").exists()

def test_no_allow_power_backend_or_entity():
    for path in PKG.rglob("*.py"):
        assert "allow_power" not in path.read_text(), path
    assert "allow_power" not in (ROOT/"apply_equipment_i18n.py").read_text()

def test_room_owned_preset_inputs_and_no_device_temperature_duplicates():
    controls=source("device_controls.py")
    numbers=source("number.py")
    assert 'for profile in ("comfort", "home", "sleep", "eco")' in controls
    assert '"humidity_target"' in controls and '"fan_speed_percent"' in controls
    assert 'f"{profile}_{mode}_c"' not in controls
    assert 'chosen = []' in numbers

def test_automatic_preset_meanings_are_encoded():
    strategy=source("climate_strategy.py")
    assert 'return "away","nobody_home"' in strategy
    assert 'return "sleep","sleep_mode_active"' in strategy
    assert 'return "comfort","room_occupied"' in strategy
    assert 'return "home","someone_home_room_unoccupied"' in strategy
    assert 'if manual in ("comfort","home","away","sleep","eco")' in strategy

def test_eco_is_explicit_only_in_profile_selector():
    strategy=source("climate_strategy.py")
    automatic=strategy[strategy.index('def select_profile'):strategy.index('def capabilities')]
    assert automatic.count('"eco"') == 1
    assert 'manual in ("comfort","home","away","sleep","eco")' in automatic
''',encoding="utf-8")

    # Update release metadata.
    req=json.loads((ROOT/".github/release-request.json").read_text())
    req.update(version="0.6.0b20",channel="beta",release_branch="beta/v0.6.0b20",
               note="Actual enviroment_manager domain; single General settings page; no allow_power; room-owned automatic presets")
    (ROOT/".github/release-request.json").write_text(json.dumps(req,indent=2)+"\\n")

    readme=ROOT/"README.md"
    text=readme.read_text()
    text=text.replace("v0.6.0b19","v0.6.0b20")
    insertion='''## Beta 20 - actual enviroment_manager domain and automatic room presets

This is the first release whose installed Home Assistant integration domain is **enviroment_manager**. The b19 release was only the old-domain migration bridge. Existing air_quality_advisor entries are migrated through the new config flow while preserving room/device/entity registry identities.

General settings is now one page only: changing the TTS provider or occupied/sleep list source is normalized on submit instead of rendering General settings a second time.

The separate **Allow power and HVAC mode control** entity and backend flag are removed. Selecting Automatic, PID or Manual on an authorized native controller is the control permission; when its room policy and demand require it, the controller can turn the native device/mode on, regulate it and turn it off again under the existing availability, ownership, dwell, window and protection gates.

Room Environment owns the temperature setpoints:
- **Comfort**: room occupied.
- **Home**: somebody home but this room unoccupied.
- **Away**: nobody home; uses the Room Environment temperature min/max limits rather than duplicate setpoint inputs.
- **Sleep**: sleeping-room setpoints.
- **Eco**: explicit energy-saving override with its own room setpoints; it is never selected automatically from occupancy.

Per-device duplicated heating/cooling preset numbers are removed.

'''
    marker="## Beta 19"
    pos=text.find(marker)
    if pos<0: pos=text.find("\\n## ",text.find("# Home Environment Manager"))+1
    text=text[:pos]+insertion+text[pos:]
    readme.write_text(text)

    changelog=ROOT/"CHANGELOG.md"
    text=changelog.read_text().replace("# Changelog\\n","# Changelog\\n\\n## 0.6.0b20 - Actual enviroment_manager domain and automatic room presets\\n\\n- Install under the enviroment_manager Home Assistant domain; b19 remains the legacy bridge.\\n- Make General settings a single page.\\n- Remove allow_power_and_hvac_mode_control UI/backend; active control method owns native on/off/mode control.\\n- Room Environment owns Comfort/Home/Sleep/Eco temperature setpoints; Away uses room min/max limits.\\n- Remove duplicate per-device temperature preset numbers.\\n- Preserve availability, ownership, dwell/interlock and native safety gates.\\n",1)
    changelog.write_text(text)

    note=ROOT/".github/releases/v0.6.0b20.md"
    note.write_text('''# Home Environment Manager v0.6.0b20 - Actual domain migration and room presets

This opt-in beta is the first release installed under the Home Assistant domain **enviroment_manager**. Beta19 intentionally remained under air_quality_advisor as a migration bridge.

## Setup fixes
General settings is shown once. Dependent TTS-language and room-list attribute values are normalized during the same submit instead of reopening the page.

## Controller power semantics
The separate Allow power and HVAC mode control switch and backend setting are gone. Selecting Automatic, PID or Manual authorizes that exact selected native climate/fan/humidifier controller. When the controller is active, the physical device is available, its room occupancy policy allows operation and demand exists, Home Environment Manager may turn the native device/mode on, regulate setpoints/speed, and turn it off when demand ends. Existing minimum ON/OFF, max-runtime, open-window, defrost, manual-override, acknowledgement and ownership gates still apply. Raw relays/proportional actuators keep their separate hardware commissioning requirements.

## Room-owned setpoints
The Room Environment device owns heating/cooling inputs for:
- Comfort: occupied room.
- Home: somebody is home but this room is not occupied.
- Sleep: the room is sleeping.
- Eco: an explicit manual/automation energy-saving override; occupancy never chooses Eco automatically.

Away / nobody-home has no duplicate setpoint input. Heating uses the room minimum temperature limit and cooling uses the room maximum temperature limit. Per-device duplicated Home/Unoccupied/Away/Sleep temperature numbers are removed.

## Domain migration
The package contains only custom_components/enviroment_manager. The migration flow copies existing air_quality_advisor data/options/subentries and moves entity/device registry ownership without changing entity IDs, unique IDs, device IDs, disabled states or user customizations. Legacy service aliases and the old dashboard-card URL remain available after migration. If automatic bridge handoff is not possible on a particular HACS installation, adding Home Environment Manager once exposes the migration confirmation instead of creating a second independent home.

Back up Home Assistant before this beta because changing a config-entry domain is a structural migration. Software CI cannot reproduce the user's exact HACS filesystem or physical HVAC hardware.

Stable Latest remains v0.5.1.
''')

    # Distribution tests follow the real beta20 source/workflow.
    for rel in ("tests/test_beta_distribution.py","tests/test_readme_assets.py"):
        path=ROOT/rel
        if path.exists():
            body=path.read_text(encoding="utf-8")
            body=body.replace("0.6.0b19","0.6.0b20")
            body=body.replace("beta 19","beta 20")
            body=body.replace("beta19-domain-presets.yml","beta20-domain-runtime.yml")
            if rel.endswith("test_readme_assets.py") and '"v0.6.0b20"' not in body:
                body=body.replace('"v0.6.0b19")','"v0.6.0b19", "v0.6.0b20")')
            path.write_text(body,encoding="utf-8")

    # A single-page regression is intentionally source-level: dependent fields
    # must normalize on submit without hidden second-page state.
    beta20=ROOT/"tests"/"test_beta20_regressions.py"
    body=beta20.read_text(encoding="utf-8")
    body += """
def test_general_settings_has_no_submit_rerender_state():
    source=(ROOT/"custom_components/enviroment_manager/room_setup.py").read_text()
    assert "_setup_general_rendered" not in source
    assert "_setup_general_draft" not in source

"""
    beta20.write_text(body,encoding="utf-8")

    subprocess.run([sys.executable,"generate_translations.py"],cwd=ROOT,check=True)
    git("add","-A")
    print("BETA20_TREE="+git("write-tree").strip())

if __name__=="__main__":
    main()
