"""Automatic post-push CI must validate before publishing a single release."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_push_triggers_release_with_validation_gates():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert "on:\n  push:\n    branches:\n      - main\n" in workflow
    assert "workflow_dispatch:" in workflow
    assert "default: false" in workflow  # manual dispatch validates by default
    assert "cancel-in-progress: true" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "inputs.publish_release == true" in workflow
    assert "needs: [test, hassfest, hacs, room_registry]" in workflow
    assert "gh release create" in workflow
    assert "steps.eligibility.outputs.should_publish == 'true'" in workflow


def test_release_skips_superseded_commits_and_existing_versions():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert 'current_sha="$(gh api "repos/$GITHUB_REPOSITORY/branches/main"' in workflow
    assert '[[ "$current_sha" != "$GITHUB_SHA" ]]' in workflow
    assert 'gh release view "$RELEASE_TAG"' in workflow
    assert 'git/ref/tags/$RELEASE_TAG' in workflow
    assert 'echo "should_publish=false"' in workflow
    assert 'echo "should_publish=true"' in workflow


def test_manifest_release_request_and_notes_match():
    manifest = json.loads(
        (ROOT / "custom_components/air_quality_advisor/manifest.json").read_text(encoding="utf-8")
    )
    request = json.loads(
        (ROOT / ".github/release-request.json").read_text(encoding="utf-8")
    )
    version = manifest["version"]
    assert request["version"] == version
    notes = ROOT / ".github" / "releases" / f"v{version}.md"
    assert notes.is_file()
    assert notes.stat().st_size > 200
