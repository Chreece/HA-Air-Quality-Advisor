"""Apply the pinned, locally tested area-hub patch on its exact source tree."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / ".github/changes/area-hubs"
BASE_TREE = "30860c36e107129bef89faa4ba6d7a45b301de27"
PATCH_SHA256 = "ff403e87d3f08f38fdb0eea7432fd97e20ba891a2e6808734f4df828bcd04894"
ALLOWED = {
    "custom_components/air_quality_advisor/__init__.py",
    "custom_components/air_quality_advisor/area_entities.py",
    "custom_components/air_quality_advisor/device_hierarchy.py",
    "custom_components/air_quality_advisor/number.py",
    "custom_components/air_quality_advisor/select.py",
    "custom_components/air_quality_advisor/switch.py",
    "custom_components/air_quality_advisor/time.py",
    "docs/DEVICE_CONTROLLER_CHECKPOINT.md",
    "tests/test_area_devices.py",
    "tests/test_device_hierarchy.py",
    "tests/test_legacy_entry_lifecycle.py",
}


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], input=data, cwd=ROOT, check=True, capture_output=True
    ).stdout


def main() -> None:
    if not PARTS.is_dir():
        print("No pending area-hub patch; validate committed source normally.")
        return
    if git("rev-parse", "HEAD^^{tree}").decode().strip() != BASE_TREE:
        raise RuntimeError("Refuse patch on an unexpected source tree")
    if git("status", "--porcelain").strip():
        raise RuntimeError("Patch application requires a clean checkout")
    if {p.name for p in PARTS.iterdir()} != {f"{i}.txt" for i in range(8)}:
        raise RuntimeError("Unexpected patch part list")
    encoded = "".join((PARTS / f"{i}.txt").read_text(encoding="ascii") for i in range(8))
    if len(encoded) != 14520:
        raise RuntimeError("Incomplete patch payload")
    patch = zlib.decompress(base64.b64decode(encoded, validate=True))
    if len(patch) != 42178 or hashlib.sha256(patch).hexdigest() != PATCH_SHA256:
        raise RuntimeError("Patch content checksum mismatch")
    git("apply", "--check", "--index", "-", data=patch)
    git("apply", "--index", "-", data=patch)
    changed = set(git("diff", "--cached", "--name-only", "-z").decode().strip("\0").split("\0"))
    if changed != ALLOWED:
        raise RuntimeError(f"Unexpected patch paths: {changed ^ ALLOWED}")
    print(f"Applied pinned area-hub checkpoint: {len(changed)} files, SHA-256 {PATCH_SHA256}")


if __name__ == "__main__":
    main()
