"""The opt-in v0.6 beta 6 must not alter stable distribution guarantees."""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "air_quality_advisor"


def test_beta_distribution_manifest_hacs_and_readme():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["version"] != "0.6.0b6":
        return  # Stable and future feature branches have their own version.
    assert manifest["domain"] == "air_quality_advisor"
    assert manifest["name"] == "Home Environment Manager"
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] == manifest["name"]
    assert hacs.get("zip_release") is not True  # Tagged source-tree install.
    req = json.loads((ROOT / ".github/release-request.json").read_text(encoding="utf-8"))
    assert (req["version"], req["channel"], req["release_branch"]) == (
        "0.6.0b6", "beta", "beta/v0.6.0b6"
    )
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Show beta versions" in text and "v0.5.1" in text
    assert "home_environment_manager.climate_diagnostics" in text
    assert "disabled by default" in text.lower()
    note = ROOT / ".github" / "releases" / "v0.6.0b6.md"
    assert note.stat().st_size > 1500
    assert "physical" in note.read_text(encoding="utf-8").lower()


def test_branded_icons_and_beta_action_icons_have_valid_dimensions():
    required = (
        ("icon.png", (256, 256)), ("dark_icon.png", (256, 256)),
        ("icon@2x.png", (512, 512)), ("dark_icon@2x.png", (512, 512)),
        ("logo.png", (768, 192)), ("dark_logo.png", (768, 192)),
        ("logo@2x.png", (1536, 384)), ("dark_logo@2x.png", (1536, 384)),
    )
    for name, expected in required:
        data = (COMPONENT / "brand" / name).read_bytes()
        assert data[:8] == bytes.fromhex("89504e470d0a1a0a"), name
        assert struct.unpack(">II", data[16:24]) == expected, name
    icons = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))
    assert set(icons["services"]) == {
        "announce", "pid_control", "climate_control", "climate_diagnostics"
    }
    assert set(icons["entity"]["sensor"]["recommendation"]["state"]) == {
        "open", "close", "idle", "blocked"
    }


def test_beta_workflow_uses_prerelease_and_never_changes_latest():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    if (COMPONENT / "manifest.json").read_text(encoding="utf-8").find(
        '"version": "0.6.0b6"'
    ) < 0:
        return
    assert "github.ref == 'refs/heads/beta/v0.6.0b6'" in workflow
    assert "--prerelease --latest=false" in workflow
    assert "gh release create v0.6.0b6" in workflow
