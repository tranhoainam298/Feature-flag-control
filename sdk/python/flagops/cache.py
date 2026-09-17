"""In-memory thread-safe RulesetCache for FlagOps SDK."""

import threading
import time
from typing import Any

from .engine.types import (
    DistributionEntry,
    FlagRuleset,
    IndividualOverride,
    Ruleset,
    TargetingRule,
    Variation,
)
from .errors import RulesetParseError


def parse_ruleset(payload: dict[str, Any]) -> Ruleset:
    """Safely parse a JSON ruleset payload from the server into an Engine Ruleset dataclass."""
    try:
        env_id = str(payload.get("environmentId", ""))
        version = int(payload.get("rulesetVersion", 0))
        segments = dict(payload.get("segments", {}))

        flags_dict: dict[str, FlagRuleset] = {}
        raw_flags = payload.get("flags", {})

        for flag_key, f_data in raw_flags.items():
            # Parse variations
            variations_list: list[Variation] = []
            var_by_id: dict[str, Variation] = {}
            var_by_key: dict[str, Variation] = {}

            for v in f_data.get("variations", []):
                v_obj = Variation(
                    id=str(v["id"]) if v.get("id") else None,
                    key=v["key"],
                    value=v.get("value"),
                    name=v.get("name"),
                    description=v.get("description"),
                )
                variations_list.append(v_obj)
                if v_obj.id:
                    var_by_id[v_obj.id] = v_obj
                var_by_key[v_obj.key] = v_obj

            def _resolve_var(raw_v: dict[str, Any] | None) -> Variation | None:
                if not raw_v:
                    return None
                if "id" in raw_v and str(raw_v["id"]) in var_by_id:
                    return var_by_id[str(raw_v["id"])]
                if "key" in raw_v and raw_v["key"] in var_by_key:
                    return var_by_key[raw_v["key"]]
                return Variation(
                    id=str(raw_v["id"]) if raw_v.get("id") else None,
                    key=raw_v.get("key", ""),
                    value=raw_v.get("value"),
                )

            default_var = _resolve_var(f_data.get("defaultVariation"))
            off_var = _resolve_var(f_data.get("offVariation"))

            # Parse targeting rules
            rules_list: list[TargetingRule] = []
            for r in f_data.get("rules", []):
                dist_list: list[DistributionEntry] = []
                for d in r.get("distribution", []):
                    var_id = str(d.get("variationId", ""))
                    matched_var = var_by_id.get(var_id) or (
                        default_var or Variation(key="", value=None)
                    )
                    dist_list.append(
                        DistributionEntry(
                            variation=matched_var,
                            weight=float(d.get("weight", 0.0)),
                        )
                    )

                rule_obj = TargetingRule(
                    id=str(r.get("id", "")),
                    priority=int(r.get("priority", 0)),
                    conditions=r.get("conditions", []),
                    distribution=dist_list,
                    segment_id=str(r["segmentId"]) if r.get("segmentId") else None,
                    description=r.get("description"),
                )
                rules_list.append(rule_obj)

            # Parse individual overrides
            overrides_list: list[IndividualOverride] = []
            for o in f_data.get("overrides", []):
                var_id = str(o.get("variationId", ""))
                matched_var = var_by_id.get(var_id) or (
                    default_var or Variation(key="", value=None)
                )
                overrides_list.append(
                    IndividualOverride(
                        id=str(o.get("id", "")) if o.get("id") else None,
                        context_key=str(o.get("contextKey", "")),
                        variation=matched_var,
                    )
                )

            flag_obj = FlagRuleset(
                flag_id=str(f_data.get("flagId", "")),
                flag_key=str(f_data.get("flagKey", flag_key)),
                flag_type=str(f_data.get("flagType", "BOOLEAN")),
                enabled=bool(f_data.get("enabled", False)),
                bucketing_key=str(f_data.get("bucketingKey", "targetingKey")),
                default_variation=default_var,
                off_variation=off_var,
                variations=variations_list,
                rules=rules_list,
                overrides=overrides_list,
            )
            flags_dict[flag_key] = flag_obj

        return Ruleset(
            environment_id=env_id,
            ruleset_version=version,
            flags=flags_dict,
            segments=segments,
        )
    except Exception as exc:
        raise RulesetParseError(f"Error parsing ruleset payload: {exc}") from exc


class RulesetCache:
    """Thread-safe in-memory cache for the environment ruleset."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ruleset: Ruleset | None = None
        self._etag: str | None = None
        self._last_updated_at: float = 0.0

    def get(self) -> Ruleset | None:
        """Retrieve the current ruleset, or None if not initialized."""
        with self._lock:
            return self._ruleset

    def get_flag(self, flag_key: str) -> FlagRuleset | None:
        """Directly retrieve a flag ruleset by key."""
        with self._lock:
            if self._ruleset is None:
                return None
            return self._ruleset.get_flag(flag_key)

    def get_etag(self) -> str | None:
        """Retrieve the current ETag."""
        with self._lock:
            return self._etag

    def update(self, ruleset: Ruleset, etag: str | None = None) -> None:
        """Atomically update the cached ruleset and ETag."""
        with self._lock:
            self._ruleset = ruleset
            if etag is not None:
                self._etag = etag
            self._last_updated_at = time.time()

    def is_initialized(self) -> bool:
        """Check if ruleset has been loaded at least once."""
        with self._lock:
            return self._ruleset is not None

    def last_updated_at(self) -> float:
        """Timestamp of last successful update."""
        with self._lock:
            return self._last_updated_at
