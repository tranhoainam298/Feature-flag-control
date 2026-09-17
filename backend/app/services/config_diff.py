"""Config diff engine — calculates differences between two configuration dictionaries.

Pure Python, zero I/O.
"""

from typing import Any


def calculate_config_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Calculate key-value diff between old and new configuration dictionaries.

    Returns:
        {
            "added": {key: val},
            "removed": {key: val},
            "changed": {key: {"old": old_val, "new": new_val}},
            "unchanged": {key: val},
        }
    """
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    unchanged: dict[str, Any] = {}

    all_keys = set(old.keys()) | set(new.keys())

    for key in sorted(all_keys):
        if key not in old:
            added[key] = new[key]
        elif key not in new:
            removed[key] = old[key]
        elif old[key] == new[key]:
            unchanged[key] = new[key]
        else:
            changed[key] = {"old": old[key], "new": new[key]}

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }
