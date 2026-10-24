"""Build the HACS content_in_root payload for beta25."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "environment_manager"


def build_payload(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    for item in SOURCE.iterdir():
        if item.name == "__pycache__":
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        else:
            shutil.copy2(item, target)

    shutil.copy2(ROOT / "hacs.json", destination / "hacs.json")

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((destination / "hacs.json").read_text(encoding="utf-8"))
    if manifest.get("domain") != "environment_manager":
        raise RuntimeError("Flat payload has the wrong Home Assistant domain")
    if manifest.get("version") != "0.6.0b25":
        raise RuntimeError("Flat payload has the wrong beta version")
    if hacs.get("content_in_root") is not True:
        raise RuntimeError("Flat payload must use HACS content_in_root")
    if hacs.get("zip_release") is True or "filename" in hacs:
        raise RuntimeError("Flat payload must not use HACS zip_release")
    if not (destination / "__init__.py").is_file():
        raise RuntimeError("Flat payload is missing __init__.py")
    if (destination / "custom_components").exists():
        raise RuntimeError("Flat payload must not contain a custom_components parent")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_beta25_payload.py DESTINATION")
    build_payload(Path(sys.argv[1]).resolve())
