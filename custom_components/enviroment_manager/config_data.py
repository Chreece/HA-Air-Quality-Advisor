"""Copy HA's read-only configuration as isolated mutable JSON containers."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def mutable_copy(value: Any) -> Any:
    """Unwrap MappingProxyType recursively; never mutate a live config entry.

    Python deepcopy attempts to pickle mappingproxy. HA exposes read-only
    entry data/options, including snapshots passed through other integrations.
    Lists/tuples retain their structure; nested mappings become independent dicts.
    """
    if isinstance(value, Mapping):
        return {key: mutable_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mutable_copy(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mutable_copy(item) for item in value)
    if isinstance(value, set):
        return {mutable_copy(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(mutable_copy(item) for item in value)
    return deepcopy(value)
