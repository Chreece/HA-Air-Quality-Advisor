"""Import pure logic without installing the multi-gigabyte Home Assistant runtime."""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components"
if "custom_components" not in sys.modules:
    pkg = types.ModuleType("custom_components")
    pkg.__path__ = [str(ROOT)]
    sys.modules[pkg.__name__] = pkg
if "custom_components.air_quality_advisor" not in sys.modules:
    pkg = types.ModuleType("custom_components.air_quality_advisor")
    pkg.__path__ = [str(ROOT / "air_quality_advisor")]
    sys.modules[pkg.__name__] = pkg
