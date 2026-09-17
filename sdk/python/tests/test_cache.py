"""Unit tests for RulesetCache and parser."""

import pytest

from flagops.cache import RulesetCache, parse_ruleset
from flagops.errors import RulesetParseError


def test_parse_ruleset_valid(sample_ruleset):
    """Test parsing complete ruleset payload."""
    ruleset = parse_ruleset(sample_ruleset)
    assert ruleset.environment_id == "env-test-123"
    assert ruleset.ruleset_version == 42
    assert "checkout-v2" in ruleset.flags

    flag = ruleset.get_flag("checkout-v2")
    assert flag is not None
    assert flag.flag_key == "checkout-v2"
    assert flag.enabled is True
    assert len(flag.variations) == 2
    assert len(flag.rules) == 1
    assert len(flag.overrides) == 1


def test_parse_ruleset_invalid_raises():
    """Test parse_ruleset raises RulesetParseError on malformed structure."""
    with pytest.raises(RulesetParseError):
        parse_ruleset({"flags": "not-a-dict"})


def test_ruleset_cache_lifecycle(sample_ruleset):
    """Test RulesetCache operations."""
    cache = RulesetCache()
    assert cache.is_initialized() is False
    assert cache.get() is None
    assert cache.get_etag() is None

    ruleset = parse_ruleset(sample_ruleset)
    cache.update(ruleset, etag="etag-123")

    assert cache.is_initialized() is True
    assert cache.get() == ruleset
    assert cache.get_etag() == "etag-123"
    assert cache.get_flag("checkout-v2") is not None
    assert cache.get_flag("non-existent") is None
    assert cache.last_updated_at() > 0
