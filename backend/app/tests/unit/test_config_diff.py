"""Unit tests for config diff engine.

Covers calculate_config_diff:
- added keys
- removed keys
- changed keys
- unchanged keys
- all 4 cases simultaneously
- empty dicts (both empty, old empty, new empty)
- nested JSON values and types
"""

from app.services.config_diff import calculate_config_diff


def test_empty_dicts():
    result = calculate_config_diff({}, {})
    assert result == {
        "added": {},
        "removed": {},
        "changed": {},
        "unchanged": {},
    }


def test_old_empty_new_has_items():
    new = {"k1": "v1", "k2": 123}
    result = calculate_config_diff({}, new)
    assert result == {
        "added": {"k1": "v1", "k2": 123},
        "removed": {},
        "changed": {},
        "unchanged": {},
    }


def test_new_empty_old_has_items():
    old = {"k1": "v1", "k2": 123}
    result = calculate_config_diff(old, {})
    assert result == {
        "added": {},
        "removed": {"k1": "v1", "k2": 123},
        "changed": {},
        "unchanged": {},
    }


def test_unchanged_items():
    data = {"k1": "v1", "nested": {"a": 1, "b": [1, 2]}}
    result = calculate_config_diff(data, data)
    assert result == {
        "added": {},
        "removed": {},
        "changed": {},
        "unchanged": {"k1": "v1", "nested": {"a": 1, "b": [1, 2]}},
    }


def test_changed_items():
    old = {"k1": "old_val", "count": 10, "flag": True}
    new = {"k1": "new_val", "count": 20, "flag": False}
    result = calculate_config_diff(old, new)
    assert result == {
        "added": {},
        "removed": {},
        "changed": {
            "k1": {"old": "old_val", "new": "new_val"},
            "count": {"old": 10, "new": 20},
            "flag": {"old": True, "new": False},
        },
        "unchanged": {},
    }


def test_all_four_cases_simultaneously():
    old = {
        "keep_me": "same",
        "delete_me": 42,
        "change_me": {"version": 1},
    }
    new = {
        "keep_me": "same",
        "add_me": "new_item",
        "change_me": {"version": 2},
    }
    result = calculate_config_diff(old, new)
    assert result == {
        "added": {"add_me": "new_item"},
        "removed": {"delete_me": 42},
        "changed": {
            "change_me": {
                "old": {"version": 1},
                "new": {"version": 2},
            }
        },
        "unchanged": {"keep_me": "same"},
    }


def test_nested_json_structures():
    old = {
        "config": {"host": "localhost", "ports": [80, 443], "debug": True},
        "tags": ["a", "b"],
    }
    new = {
        "config": {"host": "127.0.0.1", "ports": [80, 443], "debug": True},
        "tags": ["a", "b"],
    }
    result = calculate_config_diff(old, new)
    assert result["unchanged"] == {"tags": ["a", "b"]}
    assert result["changed"]["config"]["old"] == {
        "host": "localhost",
        "ports": [80, 443],
        "debug": True,
    }
    assert result["changed"]["config"]["new"] == {
        "host": "127.0.0.1",
        "ports": [80, 443],
        "debug": True,
    }


def test_different_data_types_on_same_key():
    old = {"val": "100"}
    new = {"val": 100}
    result = calculate_config_diff(old, new)
    assert result["changed"] == {"val": {"old": "100", "new": 100}}


def test_none_values():
    old = {"a": None}
    new = {"a": None, "b": None}
    result = calculate_config_diff(old, new)
    assert result["unchanged"] == {"a": None}
    assert result["added"] == {"b": None}
