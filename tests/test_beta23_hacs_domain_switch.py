"""Beta24 HACS domain-switch packaging contract."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def test_hacs_root_discovery_breaks_cached_old_remote_path():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    canonical = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))

    assert hacs["content_in_root"] is True
    assert hacs.get("zip_release") is not True
    assert "filename" not in hacs
    assert hacs["hide_default_branch"] is True
    assert root_manifest == canonical
    assert canonical["domain"] == "environment_manager"
    assert canonical["version"] == "0.6.0b24"

    # Mirror the relevant HACS integration repository logic. An existing HACS
    # record may still carry the previous remote directory. content_in_root
    # must override it before the selected-version manifest is requested.
    remote = "custom_components/air_quality_advisor"
    if hacs["content_in_root"]:
        remote = ""
    manifest_path = "manifest.json" if hacs["content_in_root"] else f"{remote}/manifest.json"
    domain = root_manifest["domain"]
    local_path = f"/config/custom_components/{domain}"

    assert remote == ""
    assert manifest_path == "manifest.json"
    assert local_path == "/config/custom_components/environment_manager"


def test_hacs_flat_tag_payload_is_built_from_integration_contents():
    workflow = (ROOT / ".github" / "workflows" / "beta24-hacs-flat-payload.yml").read_text(
        encoding="utf-8"
    )
    assert "cp -a custom_components/environment_manager/. \"$payload/\"" in workflow
    assert "cp hacs.json \"$payload/hacs.json\"" in workflow
    assert "git checkout --orphan beta24-payload" in workflow
    assert "git push origin HEAD:refs/heads/beta/v0.6.0b24" in workflow
    assert "zip_release" not in json.dumps(json.loads((ROOT / "hacs.json").read_text()))


def test_root_hacs_discovery_brand_exists():
    icon = ROOT / "brand" / "icon.png"
    assert icon.is_file()
    data = icon.read_bytes()
    assert data[:8] == bytes.fromhex("89504e470d0a1a0a")
    assert len(data) > 100
