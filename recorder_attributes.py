"""Bound the Recorder footprint of the window recommendation entity.

The complete multi-room dashboard is requested on demand via WebSocket. Its
size can grow with sensors, windows and climate controllers and therefore
must never be placed into a Home Assistant state attribute. This helper
preserves legacy *small* recommendation attributes when possible, and
replaces oversized lists with clearly identified partial previews.
"""
from __future__ import annotations

import json
from typing import Any

# Home Assistant's Recorder rejects state attributes at 16384 UTF-8 bytes.
# Reserve room for HA serialization differences and future metadata fields.
MAX_RECORDED_BYTES = 12000


def _size(attributes: dict[str, Any]) -> int:
    return len(json.dumps(
        attributes, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8"))


def bounded_attributes(
    required: dict[str, Any], optional: dict[str, Any],
    *,
    max_bytes: int = MAX_RECORDED_BYTES,
) -> dict[str, Any]:
    """Fit all attributes within a safe size, never losing summary counts.

    Optional list fields get the longest byte-safe prefix, keeping their
    existing type and names for small installations. Truncation is explicit
    and the unabridged content stays available from the read-only WebSocket
    API. Do not blindly split a string or expose incomplete JSON.
    """
    result = dict(required)
    result["truncated_fields"] = {}
    if _size(result) > max_bytes:
        raise ValueError("Recorder-safe metadata unexpectedly exceeds limit")
    # The optional field map has a fixed small set of names, but partial-list
    # counts must still fit after adding the last optional field.
    payload_budget = max_bytes - 1024

    for key, value in optional.items():
        trial = {**result, key: value}
        if _size(trial) <= payload_budget:
            result[key] = value
            continue
        if isinstance(value, list):
            low, high, best = 0, len(value), 0
            while low <= high:
                mid = (low + high) // 2
                trial = {**result, key: value[:mid]}
                if _size(trial) <= payload_budget:
                    best = mid
                    low = mid + 1
                else:
                    high = mid - 1
            result[key] = value[:best]
            result["truncated_fields"][key] = len(value) - best
        elif isinstance(value, dict):
            result["truncated_fields"][key] = len(value)
        else:
            result["truncated_fields"][key] = 1

        # Reserve room for future truncated-field annotations too. A very
        # large source collection must not accidentally exceed the cap.
        if _size(result) > max_bytes:
            result.pop(key, None)
            result["truncated_fields"][key] = len(value) if isinstance(value, (list, dict)) else 1

    if not result["truncated_fields"]:
        result.pop("truncated_fields")
    assert _size(result) <= max_bytes
    return result
