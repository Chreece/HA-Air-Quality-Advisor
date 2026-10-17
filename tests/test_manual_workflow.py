"""GitHub Actions must never launch on a push or silently release."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_only_manual_dispatch_starts_validation_and_release():
    text = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text
    assert "publish_release:" in text
    assert "default: false" in text
    assert "inputs.publish_release == true" in text
    assert "needs: [test, hassfest, hacs]" in text


def test_release_notes_and_manifest_match_without_triggering_ci_on_commit():
    import json

    manifest = json.loads(
        (ROOT / "custom_components/air_quality_advisor/manifest.json").read_text()
    )
    request = json.loads(
        (ROOT / ".github/release-request.json").read_text(encoding="utf-8")
    )
    version = manifest["version"]
    assert request["version"] == version
    notes = ROOT / ".github" / "releases" / f"v{version}.md"
    assert notes.is_file()
    assert notes.stat().st_size > 200
