"""The repeat setting is available in all 38 Home Assistant languages."""
import json
from pathlib import Path
from custom_components.enviroment_manager.languages import SUPPORTED_LANGUAGE_TAGS

ROOT = Path(__file__).resolve().parents[1] / "custom_components/enviroment_manager"

def test_every_language_exposes_repeat_minutes_and_validation():
    for tag in SUPPORTED_LANGUAGE_TAGS:
        doc = json.loads((ROOT / "translations" / f"{tag}.json").read_text(encoding="utf-8"))
        for scope in ("config", "options"):
            delivery = doc[scope]["step"]["delivery"]
            assert delivery["data"]["announcement_repeat_minutes"], tag
            assert delivery["data_description"]["announcement_repeat_minutes"], tag
            assert doc[scope]["error"]["invalid_repeat_minutes"], tag
    greek = json.loads((ROOT / "translations/el.json").read_text(encoding="utf-8"))
    assert "Επανάληψη" in greek["config"]["step"]["delivery"]["data"]["announcement_repeat_minutes"]
