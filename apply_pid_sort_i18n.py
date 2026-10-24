"""Last-pass PID entity display-name normalization in all 38 HA locales.

The names of PID *parameter* entities, not physical devices or non-PID
controls, must sort together under "PID" in Home Assistant. Keep localized
descriptions, exact unique IDs, translation keys, options and actual settings
unchanged. Called LAST by generate_translations.py so later generators cannot
restore names that begin with a device channel or a local adjective.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The translation keys are internal identifiers. Renaming an entity or
# changing its unique ID to influence alphabetical sorting is prohibited.
DEVICE_PID_NUMBER_KEYS = frozenset({
    "equipment_kp", "equipment_ki", "equipment_kd",
    "equipment_sample_seconds", "equipment_cycle_seconds",
    "equipment_pid_process_gain", "equipment_pid_time_constant_minutes",
    "equipment_pid_dead_time_minutes", "equipment_pid_lambda_minutes",
    *(f"equipment_pid_capacity_stage_{i}" for i in range(1, 5)),
    *(f"equipment_pid_capacity_speed_{i}" for i in range(1, 4)),
    *(f"equipment_pid_capacity_output_{i}" for i in range(1, 4)),
})
DEVICE_PID_SELECT_KEYS = frozenset({
    "equipment_pid_calibration_method",
    "equipment_pid_fan_capacity_mode",
    "equipment_pid_fan_capacity_for_mode",
    "area_pid_gain_source",
})
DEVICE_PID_BUTTON_KEYS = frozenset({
    "equipment_pid_apply_calibration",
    "equipment_pid_apply_fan_capacity",
})


def _is_pid_parameter(domain: str, key: str) -> bool:
    if domain == "number":
        return (key in DEVICE_PID_NUMBER_KEYS or
                key.startswith(("area_pid_", "area_direct_tuning_")))
    if domain == "select":
        return key in DEVICE_PID_SELECT_KEYS
    if domain == "button":
        return key in DEVICE_PID_BUTTON_KEYS
    return False


def pid_first(name: str) -> str:
    """Produce a PID-first name without duplicating existing PID wording.

    Equipment labels use an optional {channel} placeholder when a physical
    device has several independently controlled channels. Move that after
    the PID prefix; the replacement must stay intact and localized.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("PID parameter translation requires a real name")
    raw = name.strip()
    channel = "{channel}" if raw.startswith("{channel}") else ""
    if channel:
        raw = raw[len(channel):].strip()

    # PID is a language-independent technical acronym already present in
    # some labels, but not always at the start. Keep its one leading
    # occurrence, retaining all surrounding localized explanatory words.
    clean = re.sub(r"(?<![\w])PID(?![\w])", "", raw, flags=re.IGNORECASE)
    clean = clean.strip(" \t\n:·–—-")
    clean = re.sub(r" {2,}", " ", clean)
    return "PID" if not clean and not channel else (
        f"PID · {channel}{clean}" if clean else f"PID · {channel.rstrip()}"
    )


def apply_pid_sort_i18n(root: Path) -> None:
    paths = [root / "strings.json", *sorted((root / "translations").glob("*.json"))]
    if len(paths) != 39:
        raise ValueError("PID naming requires canonical strings and all 38 locales")
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        entity = doc.setdefault("entity", {})
        for domain in ("number", "select", "button"):
            for key, payload in entity.get(domain, {}).items():
                if _is_pid_parameter(domain, key):
                    if not isinstance(payload, dict) or "name" not in payload:
                        raise ValueError(f"Missing PID entity display name: {path.name}/{domain}/{key}")
                    payload["name"] = pid_first(payload["name"])
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
