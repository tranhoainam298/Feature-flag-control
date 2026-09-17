"""Unit tests for FlagOps OpenFeature Provider compliance.

Verifies:
1. Standard OpenFeature metadata name "FlagOps".
2. Resolution for all 5 types: boolean, string, integer, float, object.
3. Reason code mapping (TARGETING_MATCH, SPLIT, DEFAULT, DISABLED, ERROR).
4. Error code mapping (FLAG_NOT_FOUND, TYPE_MISMATCH, PROVIDER_NOT_READY, GENERAL).
5. OpenFeature EvaluationContext (targeting_key + attributes) mapping to FlagOps bucketing_key.
6. Fail-safe behavior: non-existent flags return default + error_code without raising.
7. Type mismatch: requesting wrong type returns TYPE_MISMATCH + default value.
8. Provider not ready: uninitialized client returns PROVIDER_NOT_READY.
9. Strict parity: direct FlagOpsClient vs OpenFeature client yield identical evaluation results.
"""

from typing import Any
import httpx
import pytest

from openfeature import api
from openfeature.evaluation_context import EvaluationContext as OFEvaluationContext
from openfeature.exception import ErrorCode as OFErrorCode
from openfeature.flag_evaluation import Reason as OFReason

from flagops.client import FlagOpsClient
from flagops.openfeature import FlagOpsProvider


EXTENDED_RULESET_PAYLOAD = {
    "environmentId": "env-test-openfeature",
    "rulesetVersion": 101,
    "flags": {
        "checkout-v2": {
            "flagId": "f-bool",
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
                    "id": "rule-beta",
                    "priority": 1,
                    "description": "Beta testers get checkout-v2",
                    "conditions": [
                        {"attribute": "is_beta", "operator": "EQ", "value": True}
                    ],
                    "distribution": [{"variationId": "var-on", "weight": 100.0}],
                },
                {
                    "id": "rule-rollout",
                    "priority": 2,
                    "description": "50-50 rollout for free users",
                    "conditions": [
                        {"attribute": "plan", "operator": "EQ", "value": "free"}
                    ],
                    "distribution": [
                        {"variationId": "var-on", "weight": 50.0},
                        {"variationId": "var-off", "weight": 50.0},
                    ],
                },
            ],
            "overrides": [
                {"id": "ov-vip", "contextKey": "user-vip", "variationId": "var-on"}
            ],
        },
        "banner-text": {
            "flagId": "f-str",
            "flagKey": "banner-text",
            "flagType": "STRING",
            "enabled": True,
            "variations": [
                {"id": "s-def", "key": "default-text", "value": "Welcome to FlagOps"},
                {"id": "s-promo", "key": "promo-text", "value": "Black Friday Sale!"},
            ],
            "defaultVariation": {"id": "s-def", "key": "default-text", "value": "Welcome to FlagOps"},
            "offVariation": {"id": "s-def", "key": "default-text", "value": "Welcome to FlagOps"},
            "bucketingKey": "targetingKey",
            "rules": [
                {
                    "id": "rule-promo",
                    "priority": 1,
                    "conditions": [
                        {"attribute": "country", "operator": "EQ", "value": "VN"}
                    ],
                    "distribution": [{"variationId": "s-promo", "weight": 100.0}],
                }
            ],
            "overrides": [],
        },
        "max-connections": {
            "flagId": "f-int",
            "flagKey": "max-connections",
            "flagType": "NUMBER",
            "enabled": True,
            "variations": [
                {"id": "n-20", "key": "20", "value": 20},
                {"id": "n-100", "key": "100", "value": 100},
            ],
            "defaultVariation": {"id": "n-20", "key": "20", "value": 20},
            "offVariation": {"id": "n-20", "key": "20", "value": 20},
            "bucketingKey": "targetingKey",
            "rules": [
                {
                    "id": "rule-tier",
                    "priority": 1,
                    "conditions": [
                        {"attribute": "tier", "operator": "EQ", "value": "enterprise"}
                    ],
                    "distribution": [{"variationId": "n-100", "weight": 100.0}],
                }
            ],
            "overrides": [],
        },
        "tax-rate": {
            "flagId": "f-float",
            "flagKey": "tax-rate",
            "flagType": "NUMBER",
            "enabled": True,
            "variations": [
                {"id": "fl-base", "key": "standard", "value": 0.0825},
                {"id": "fl-reduced", "key": "reduced", "value": 0.05},
            ],
            "defaultVariation": {"id": "fl-base", "key": "standard", "value": 0.0825},
            "offVariation": {"id": "fl-base", "key": "standard", "value": 0.0825},
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
        "ui-theme-config": {
            "flagId": "f-obj",
            "flagKey": "ui-theme-config",
            "flagType": "JSON",
            "enabled": True,
            "variations": [
                {
                    "id": "j-def",
                    "key": "theme-v1",
                    "value": {"primaryColor": "#6366f1", "darkMode": True, "borderRadius": 8},
                }
            ],
            "defaultVariation": {
                "id": "j-def",
                "key": "theme-v1",
                "value": {"primaryColor": "#6366f1", "darkMode": True, "borderRadius": 8},
            },
            "offVariation": None,
            "bucketingKey": "targetingKey",
            "rules": [],
            "overrides": [],
        },
        "disabled-flag": {
            "flagId": "f-dis",
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


def _create_test_client(ruleset_payload: dict[str, Any] = EXTENDED_RULESET_PAYLOAD) -> FlagOpsClient:
    """Create in-memory FlagOpsClient with pre-loaded mock ruleset."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=ruleset_payload, headers={"ETag": '"v101"'})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="fo_srv_test_key_123",
        base_url="http://testserver",
        http_client=mock_http,
        polling_interval=3600.0,
        enable_streaming=False,
    )
    return client


@pytest.fixture(autouse=True)
def reset_openfeature_api():
    """Reset OpenFeature state before and after each test."""
    yield
    api.clear_providers()


# ──────────────────────────────────────────────────────────────────────────────
# 1. PROVIDER METADATA
# ──────────────────────────────────────────────────────────────────────────────

def test_provider_metadata():
    """Verify provider get_metadata() returns name 'FlagOps'."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    metadata = provider.get_metadata()
    assert metadata.name == "FlagOps"

    api.set_provider(provider)
    assert api.get_provider_metadata().name == "FlagOps"
    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 2. RESOLVE ALL 5 TYPES (BOOLEAN, STRING, INTEGER, FLOAT, OBJECT)
# ──────────────────────────────────────────────────────────────────────────────

def test_resolve_all_types():
    """Verify all 5 OpenFeature types resolve accurately with expected reasons and values."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    # 1. Boolean
    bool_details = of_client.get_boolean_details("checkout-v2", False)
    assert bool_details.value is False
    assert bool_details.reason == OFReason.DEFAULT
    assert bool_details.error_code is None

    # Boolean with targeting rule match
    ctx_beta = OFEvaluationContext(targeting_key="u1", attributes={"is_beta": True})
    bool_beta = of_client.get_boolean_details("checkout-v2", False, ctx_beta)
    assert bool_beta.value is True
    assert bool_beta.reason == OFReason.TARGETING_MATCH
    assert bool_beta.variant == "on"

    # 2. String
    str_details = of_client.get_string_details("banner-text", "fallback")
    assert str_details.value == "Welcome to FlagOps"
    assert str_details.reason == OFReason.DEFAULT

    ctx_vn = OFEvaluationContext(targeting_key="u2", attributes={"country": "VN"})
    str_vn = of_client.get_string_details("banner-text", "fallback", ctx_vn)
    assert str_vn.value == "Black Friday Sale!"
    assert str_vn.reason == OFReason.TARGETING_MATCH

    # 3. Integer
    int_details = of_client.get_integer_details("max-connections", 5)
    assert int_details.value == 20
    assert isinstance(int_details.value, int)
    assert int_details.reason == OFReason.DEFAULT

    ctx_ent = OFEvaluationContext(targeting_key="u3", attributes={"tier": "enterprise"})
    int_ent = of_client.get_integer_details("max-connections", 5, ctx_ent)
    assert int_ent.value == 100
    assert isinstance(int_ent.value, int)
    assert int_ent.reason == OFReason.TARGETING_MATCH

    # 4. Float
    fl_details = of_client.get_float_details("tax-rate", 0.0)
    assert fl_details.value == 0.0825
    assert isinstance(fl_details.value, float)
    assert fl_details.reason == OFReason.DEFAULT

    # 5. Object
    obj_details = of_client.get_object_details("ui-theme-config", {})
    assert obj_details.value == {"primaryColor": "#6366f1", "darkMode": True, "borderRadius": 8}
    assert obj_details.reason == OFReason.DEFAULT

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 3. NON-EXISTENT FLAG -> DEFAULT + FLAG_NOT_FOUND, NO RAISE
# ──────────────────────────────────────────────────────────────────────────────

def test_flag_not_found_returns_default_without_raising():
    """Verify non-existent flags return default value and FLAG_NOT_FOUND error code without raising."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    # Boolean
    res_bool = of_client.get_boolean_details("missing-flag-key", False)
    assert res_bool.value is False
    assert res_bool.error_code == OFErrorCode.FLAG_NOT_FOUND
    assert res_bool.reason == OFReason.ERROR

    val_bool = of_client.get_boolean_value("missing-flag-key", True)
    assert val_bool is True

    # String
    res_str = of_client.get_string_details("missing-str", "default-str")
    assert res_str.value == "default-str"
    assert res_str.error_code == OFErrorCode.FLAG_NOT_FOUND
    assert res_str.reason == OFReason.ERROR

    # Integer
    res_int = of_client.get_integer_details("missing-int", 42)
    assert res_int.value == 42
    assert res_int.error_code == OFErrorCode.FLAG_NOT_FOUND

    # Float
    res_fl = of_client.get_float_details("missing-fl", 3.14)
    assert res_fl.value == 3.14
    assert res_fl.error_code == OFErrorCode.FLAG_NOT_FOUND

    # Object
    res_obj = of_client.get_object_details("missing-obj", {"k": "v"})
    assert res_obj.value == {"k": "v"}
    assert res_obj.error_code == OFErrorCode.FLAG_NOT_FOUND

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 4. TYPE MISMATCH -> TYPE_MISMATCH ERROR CODE
# ──────────────────────────────────────────────────────────────────────────────

def test_type_mismatch_returns_type_mismatch_error():
    """Calling resolve on incompatible type returns default value and TYPE_MISMATCH."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    # 1. Calling get_string on a boolean flag
    str_on_bool = of_client.get_string_details("checkout-v2", "str-fallback")
    assert str_on_bool.value == "str-fallback"
    assert str_on_bool.error_code == OFErrorCode.TYPE_MISMATCH
    assert str_on_bool.reason == OFReason.ERROR

    val_str_on_bool = of_client.get_string_value("checkout-v2", "str-fallback")
    assert val_str_on_bool == "str-fallback"

    # 2. Calling get_boolean on a string flag
    bool_on_str = of_client.get_boolean_details("banner-text", False)
    assert bool_on_str.value is False
    assert bool_on_str.error_code == OFErrorCode.TYPE_MISMATCH
    assert bool_on_str.reason == OFReason.ERROR

    # 3. Calling get_integer on a boolean flag
    int_on_bool = of_client.get_integer_details("checkout-v2", 99)
    assert int_on_bool.value == 99
    assert int_on_bool.error_code == OFErrorCode.TYPE_MISMATCH

    # 4. Calling get_object on a string flag
    obj_on_str = of_client.get_object_details("banner-text", {"default": 1})
    assert obj_on_str.value == {"default": 1}
    assert obj_on_str.error_code == OFErrorCode.TYPE_MISMATCH

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 5. PROVIDER NOT READY -> PROVIDER_NOT_READY ERROR CODE
# ──────────────────────────────────────────────────────────────────────────────

def test_provider_not_ready_returns_default_and_error_code():
    """Uninitialized provider returns default value with PROVIDER_NOT_READY error code."""
    # Transport that fails initial fetch
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503, text="Service Unavailable")

    mock_http = httpx.Client(transport=httpx.MockTransport(failing_handler))
    uninitialized_client = FlagOpsClient(
        api_key="fo_srv_test",
        base_url="http://offline-server",
        http_client=mock_http,
        timeout=0.1,
    )

    provider = FlagOpsProvider(client=uninitialized_client)
    assert provider.is_ready is False

    api.set_provider(provider)
    of_client = api.get_client()

    details = of_client.get_boolean_details("checkout-v2", False)
    assert details.value is False
    assert details.error_code == OFErrorCode.PROVIDER_NOT_READY
    assert details.reason == OFReason.ERROR

    str_details = of_client.get_string_details("banner-text", "offline-default")
    assert str_details.value == "offline-default"
    assert str_details.error_code == OFErrorCode.PROVIDER_NOT_READY

    uninitialized_client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 6. TARGETING KEY MAPPED TO BUCKETING KEY & INDIVIDUAL OVERRIDES
# ──────────────────────────────────────────────────────────────────────────────

def test_targeting_key_mapped_to_bucketing_key():
    """OpenFeature EvaluationContext targeting_key is correctly routed to FlagOps bucketing."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    # 1. Individual override mapped via targeting_key
    vip_ctx = OFEvaluationContext(targeting_key="user-vip")
    vip_res = of_client.get_boolean_details("checkout-v2", False, vip_ctx)
    assert vip_res.value is True
    assert vip_res.reason == OFReason.TARGETING_MATCH
    assert vip_res.variant == "on"

    # 2. Ordinary user receives 50-50 rollout or default
    reg_ctx = OFEvaluationContext(targeting_key="user-regular-12345")
    reg_res = of_client.get_boolean_details("checkout-v2", False, reg_ctx)
    assert isinstance(reg_res.value, bool)
    assert reg_res.reason in (OFReason.SPLIT, OFReason.DEFAULT)

    # 3. Attributes alongside targeting_key
    beta_ctx = OFEvaluationContext(targeting_key="user-99", attributes={"is_beta": True})
    beta_res = of_client.get_boolean_details("checkout-v2", False, beta_ctx)
    assert beta_res.value is True
    assert beta_res.reason == OFReason.TARGETING_MATCH

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 7. PARITY TEST: DIRECT SDK CALL VS OPENFEATURE CALL
# ──────────────────────────────────────────────────────────────────────────────

def test_direct_sdk_vs_openfeature_parity():
    """Calling through direct FlagOpsClient and through OpenFeature API yields identical results."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    test_contexts = [
        {"targetingKey": "user-vip"},
        {"targetingKey": "user-123", "country": "VN", "is_beta": True, "tier": "enterprise"},
        {"targetingKey": "user-456", "country": "US", "is_beta": False, "tier": "standard"},
        {},
    ]

    for ctx_dict in test_contexts:
        t_key = ctx_dict.get("targetingKey", "")
        attrs = {k: v for k, v in ctx_dict.items() if k != "targetingKey"}
        of_ctx = OFEvaluationContext(targeting_key=t_key, attributes=attrs)

        # 1. Boolean flag
        sdk_bool = client.get_boolean("checkout-v2", context=ctx_dict, default=False)
        of_bool = of_client.get_boolean_value("checkout-v2", False, of_ctx)
        assert sdk_bool == of_bool, f"Boolean parity mismatch for context: {ctx_dict}"

        # 2. String flag
        sdk_str = client.get_string("banner-text", context=ctx_dict, default="def")
        of_str = of_client.get_string_value("banner-text", "def", of_ctx)
        assert sdk_str == of_str, f"String parity mismatch for context: {ctx_dict}"

        # 3. Number/Integer flag
        sdk_int = client.get_number("max-connections", context=ctx_dict, default=0)
        of_int = of_client.get_integer_value("max-connections", 0, of_ctx)
        assert int(sdk_int) == of_int, f"Integer parity mismatch for context: {ctx_dict}"

        # 4. JSON/Object flag
        sdk_obj = client.get_json("ui-theme-config", context=ctx_dict, default={})
        of_obj = of_client.get_object_value("ui-theme-config", {}, of_ctx)
        assert sdk_obj == of_obj, f"Object parity mismatch for context: {ctx_dict}"

        # 5. Disabled flag
        sdk_dis = client.get_boolean("disabled-flag", context=ctx_dict, default=True)
        of_dis = of_client.get_boolean_value("disabled-flag", True, of_ctx)
        assert sdk_dis == of_dis, f"Disabled flag mismatch for context: {ctx_dict}"

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 8. DISABLED FLAG EVALUATION
# ──────────────────────────────────────────────────────────────────────────────

def test_disabled_flag_evaluation():
    """Disabled flag resolves to its off_variation with DISABLED reason."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    of_client = api.get_client()

    details = of_client.get_boolean_details("disabled-flag", True)
    assert details.value is False
    assert details.reason == OFReason.DISABLED
    assert details.variant == "off"
    assert details.error_code is None

    client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 9. PROVIDER SHUTDOWN
# ──────────────────────────────────────────────────────────────────────────────

def test_provider_shutdown():
    """Provider shutdown stops background workers cleanly."""
    client = _create_test_client()
    provider = FlagOpsProvider(client=client)
    api.set_provider(provider)
    api.shutdown()
    assert client._stop_event.is_set()
