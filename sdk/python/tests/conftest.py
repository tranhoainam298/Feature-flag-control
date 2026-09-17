"""Pytest fixtures and test helpers for FlagOps SDK."""

import pytest

SAMPLE_RULESET_PAYLOAD = {
    "environmentId": "env-test-123",
    "rulesetVersion": 42,
    "flags": {
        "checkout-v2": {
            "flagId": "flag-001",
            "flagKey": "checkout-v2",
            "flagType": "BOOLEAN",
            "enabled": True,
            "variations": [
                {"id": "var-on", "key": "on", "value": True},
                {"id": "var-off", "key": "off", "value": False},
            ],
            "defaultVariation": {"id": "var-off", "key": "off", "value": False},
            "offVariation": {"id": "var-off", "key": "off", "value": False},
            "bucketingKey": "targetingKey",
            "rules": [
                {
                    "id": "rule-beta-users",
                    "priority": 1,
                    "description": "Beta testers enable checkout-v2",
                    "conditions": [
                        {"attribute": "is_beta", "operator": "EQ", "value": True}
                    ],
                    "distribution": [{"variationId": "var-on", "weight": 100.0}],
                }
            ],
            "overrides": [
                {"id": "ov-1", "contextKey": "user-vip", "variationId": "var-on"}
            ],
        },
        "banner-color": {
            "flagId": "flag-002",
            "flagKey": "banner-color",
            "flagType": "STRING",
            "enabled": True,
            "variations": [
                {"id": "c-blue", "key": "blue", "value": "blue"},
                {"id": "c-red", "key": "red", "value": "red"},
            ],
            "defaultVariation": {"id": "c-blue", "key": "blue", "value": "blue"},
            "offVariation": {"id": "c-blue", "key": "blue", "value": "blue"},
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
        "max-items": {
            "flagId": "flag-003",
            "flagKey": "max-items",
            "flagType": "INTEGER",
            "enabled": True,
            "variations": [
                {"id": "n-50", "key": "50", "value": 50},
                {"id": "n-100", "key": "100", "value": 100},
            ],
            "defaultVariation": {"id": "n-50", "key": "50", "value": 50},
            "offVariation": {"id": "n-50", "key": "50", "value": 50},
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
        "feature-config": {
            "flagId": "flag-004",
            "flagKey": "feature-config",
            "flagType": "JSON",
            "enabled": True,
            "variations": [
                {"id": "j-1", "key": "cfg1", "value": {"theme": "dark", "retries": 3}},
            ],
            "defaultVariation": {"id": "j-1", "key": "cfg1", "value": {"theme": "dark", "retries": 3}},
            "offVariation": None,
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
        "disabled-flag": {
            "flagId": "flag-005",
            "flagKey": "disabled-flag",
            "flagType": "BOOLEAN",
            "enabled": False,
            "variations": [
                {"id": "d-on", "key": "on", "value": True},
                {"id": "d-off", "key": "off", "value": False},
            ],
            "defaultVariation": {"id": "d-on", "key": "on", "value": True},
            "offVariation": {"id": "d-off", "key": "off", "value": False},
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
    },
    "segments": {},
}


@pytest.fixture
def sample_ruleset():
    return SAMPLE_RULESET_PAYLOAD.copy()
