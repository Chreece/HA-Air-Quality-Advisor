"""Beta25 HACS domain-switch and flat-tag payload contract."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def _builder():
    path = ROOT / "tools" / "build_beta25_payload.py"
    spec = importlib.util.spec_from_file_location("beta25_payload_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
    assert canonical["version"] == "0.6.0b25"

    # Mirror HACS integration.py for the exact failure shown by the user.
    remote = "custom_components/air_quality_advisor"
    if hacs["content_in_root"]:
        remote = ""
    manifest_path = (
        "manifest.json" if hacs["content_in_root"] else f"{remote}/manifest.json"
    )
    domain = root_manifest["domain"]
    local_path = f"/config/custom_components/{domain}"

    assert remote == ""
    assert manifest_path == "manifest.json"
    assert local_path == "/config/custom_components/environment_manager"


def test_flat_payload_contains_only_integration_root_plus_hacs_metadata():
    module = _builder()
    with tempfile.TemporaryDirectory() as tmp:
        payload = Path(tmp) / "payload"
        module.build_payload(payload)
        assert (payload / "__init__.py").is_file()
        assert (payload / "manifest.json").is_file()
        assert (payload / "services.yaml").is_file()
        assert (payload / "translations").is_dir()
        assert (payload / "frontend").is_dir()
        assert (payload / "brand" / "icon.png").is_file()
        assert (payload / "hacs.json").is_file()
        assert not (payload / "custom_components").exists()
        assert not (payload / "tests").exists()
        assert not (payload / ".github").exists()


def test_normal_hacs_tag_archive_extraction_lands_in_canonical_directory():
    """Mirror HACS download_repository_zip with content.path.remote == ''."""
    module = _builder()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = root / "payload"
        module.build_payload(payload)

        archive = root / "tag.zip"
        outer = "Chreece-HA-Home-Environment-Manager-deadbeef"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in payload.rglob("*"):
                if path.is_file():
                    zf.write(path, f"{outer}/{path.relative_to(payload).as_posix()}")

        destination = root / "config" / "custom_components" / "environment_manager"
        destination.mkdir(parents=True)
        remote = ""
        with zipfile.ZipFile(archive) as zf:
            extractable = []
            for info in zf.filelist:
                filename = "/".join(info.filename.split("/")[1:])
                if filename.startswith(remote) and filename != remote:
                    info.filename = filename.replace(remote, "", 1)
                    if info.filename == "/":
                        continue
                    extractable.append(info)
            assert extractable
            zf.extractall(destination, extractable)

        manifest = json.loads(
            (destination / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["domain"] == "environment_manager"
        assert manifest["version"] == "0.6.0b25"
        assert (destination / "__init__.py").is_file()
        assert not (destination / "custom_components").exists()


def test_beta25_publisher_creates_flat_branch_and_no_zip_release():
    workflow = (
        ROOT / ".github" / "workflows" / "beta25-hacs-flat-payload.yml"
    ).read_text(encoding="utf-8")
    assert "python tools/build_beta25_payload.py" in workflow
    assert "git checkout --orphan beta25-payload" in workflow
    assert "git push origin HEAD:refs/heads/beta/v0.6.0b25" in workflow
    assert "gh release create v0.6.0b25" in workflow
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs.get("zip_release") is not True
    assert "filename" not in hacs
