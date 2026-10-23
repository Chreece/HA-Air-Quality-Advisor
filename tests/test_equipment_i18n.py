"""Native per-device entity labels/help are localized and reproducible."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/air_quality_advisor"


def test_all_38_device_controller_catalogs_have_native_labels_and_explanations():
    labels = json.loads((COMPONENT / "equipment_labels.json").read_text())
    help_text = runpy.run_path(str(COMPONENT / "equipment_text.py"))["DEVICE_HELP"]
    assert len(labels) == 38 and set(labels) == set(help_text)
    for lang in labels:
        doc = json.loads((COMPONENT / "translations" / f"{lang}.json").read_text())
        entities = doc["entity"]
        for domain, names in {
            "climate": ("climate",), "button": ("resume",),
            "select": ("control_mode", "quiet_fan_mode", "fan_purpose", "presence_requirement", "sleep_behavior"),
            "switch": ("quiet_sleep", "quiet_occupied", "allow_power", "sensor_verified"),
            "number": ("kp", "ki", "kd", "sample_seconds", "cycle_seconds", "quiet_percentage", "min_on_seconds", "min_off_seconds", "max_on_seconds"),
        }.items():
            for key in names:
                name = entities[domain]["equipment_" + key]["name"]
                assert name.startswith("{channel}") and len(name) > len("{channel}"), (lang, domain, key)
        assert set(entities["select"]["equipment_control_mode"]["state"]) == {
            "existing", "automatic", "manual", "off", "pid"}
        assert len(help_text[lang]) > 150, lang
        if lang != "en":
            assert labels[lang]["quiet_sleep"] != labels["en"]["quiet_sleep"]
            assert help_text[lang] != help_text["en"]
    assert (COMPONENT / "strings.json").read_bytes() == (COMPONENT / "translations/en.json").read_bytes()


def test_equipment_translation_final_pass_is_idempotent(tmp_path, monkeypatch):
    # Run the actual final generator against complete catalogs, not a toy sample.
    monkeypatch.syspath_prepend(str(ROOT))
    from apply_equipment_i18n import apply_equipment_i18n
    for filename in ("equipment_labels.json", "compact_locales.json", "strings.json", "equipment_text.py"):
        shutil.copy(COMPONENT / filename, tmp_path / filename)
    shutil.copytree(COMPONENT / "translations", tmp_path / "translations")
    files = [tmp_path / "strings.json", tmp_path / "equipment_text.py", *sorted((tmp_path / "translations").glob("*.json"))]
    before = {p.relative_to(tmp_path): p.read_bytes() for p in files}
    apply_equipment_i18n(tmp_path)
    assert {p.relative_to(tmp_path): p.read_bytes() for p in files} == before
