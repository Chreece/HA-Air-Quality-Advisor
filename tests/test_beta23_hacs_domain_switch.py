"""Beta23 HACS domain-switch packaging contract."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def test_hacs_root_discovery_breaks_cached_old_remote_path():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    canonical = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))

    assert hacs["content_in_root"] is True
    assert hacs["zip_release"] is True
    assert hacs["filename"] == "environment_manager.zip"
    assert hacs["hide_default_branch"] is True
    assert root_manifest == canonical
    assert canonical["domain"] == "environment_manager"
    assert canonical["version"] == "0.6.0b23"

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


def test_hacs_zip_is_built_from_integration_contents_not_parent_folder():
    workflow = (ROOT / ".github" / "workflows" / "beta23-hacs-domain-switch.yml").read_text(
        encoding="utf-8"
    )
    assert "dist/environment_manager.zip" in workflow
    assert "cd custom_components/environment_manager" in workflow
    assert "assert 'custom_components/' not in name" in workflow
    assert "assert 'manifest.json' in names" in workflow
    assert "assert '__init__.py' in names" in workflow


def test_root_hacs_discovery_brand_exists():
    icon = ROOT / "brand" / "icon.png"
    assert icon.is_file()
    data = icon.read_bytes()
    assert data[:8] == bytes.fromhex("89504e470d0a1a0a")
    assert len(data) > 100
