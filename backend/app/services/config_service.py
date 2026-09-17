"""Config service — Namespace, Draft Items, Release Publish, Diff, Rollback.

Also covers Client Evaluation with ETag and secret unmasking.
"""

import json
from typing import Any
from uuid import UUID

import jsonschema
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import MASKED_SECRET, decrypt_secret, encrypt_secret
from app.core.exceptions import FlagOpsError
from app.models.config import ConfigItem, ConfigNamespace, ConfigRelease
from app.models.enums import ApiKeyScope, ConfigFormat, ConfigValueType, MemberRole
from app.models.project import Environment
from app.models.user import User
from app.schemas.config import (
    ConfigItemInput,
    ConfigNamespaceCreate,
    ConfigReleaseCreate,
)
from app.services.config_diff import calculate_config_diff
from app.services.flag import bump_ruleset_version, create_audit_log


def _parse_item_value(raw_val: str, value_type: ConfigValueType) -> Any:
    """Parse string value into corresponding Python type for schema validation."""
    if value_type == ConfigValueType.INT:
        return int(raw_val)
    if value_type == ConfigValueType.FLOAT:
        return float(raw_val)
    if value_type == ConfigValueType.BOOL:
        lower = str(raw_val).lower().strip()
        if lower in ("true", "1"):
            return True
        if lower in ("false", "0"):
            return False
        raise ValueError(f"Invalid boolean value: '{raw_val}'")
    if value_type == ConfigValueType.JSON:
        return json.loads(raw_val)
    return str(raw_val)


def validate_item_schema(item: ConfigItem) -> str | None:
    """Validate item value against its JSON Schema if present. Returns error message or None."""
    if not item.json_schema:
        return None

    # If secret, decrypt first before validating against schema
    raw_val = item.value
    if item.is_secret:
        try:
            raw_val = decrypt_secret(raw_val)
        except Exception as exc:
            return f"Cannot decrypt secret value for validation: {exc}"

    try:
        parsed_val = _parse_item_value(raw_val, item.value_type)
    except Exception as exc:
        return f"Cannot parse value as {item.value_type.value}: {exc}"

    try:
        jsonschema.validate(instance=parsed_val, schema=item.json_schema)
    except jsonschema.ValidationError as exc:
        return exc.message
    except jsonschema.SchemaError as exc:
        return f"Invalid JSON schema definition: {exc.message}"

    return None


# ──────────────────────────────────────────────────────────────────────────────
# NAMESPACE OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────


async def list_namespaces(db: AsyncSession, env_id: UUID) -> list[ConfigNamespace]:
    """List all namespaces for an environment."""
    stmt = (
        select(ConfigNamespace)
        .where(ConfigNamespace.environment_id == env_id)
        .order_by(ConfigNamespace.name.asc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def create_namespace(
    db: AsyncSession,
    env: Environment,
    payload: ConfigNamespaceCreate,
    user: User,
) -> ConfigNamespace:
    """Create a new configuration namespace in an environment."""
    existing = await db.scalar(
        select(ConfigNamespace).where(
            ConfigNamespace.environment_id == env.id,
            ConfigNamespace.name == payload.name,
        )
    )
    if existing:
        raise FlagOpsError(
            code="NAMESPACE_ALREADY_EXISTS",
            message=f"Namespace '{payload.name}' already exists in this environment",
            status_code=409,
        )

    ns = ConfigNamespace(
        environment_id=env.id,
        name=payload.name,
        format=payload.format or ConfigFormat.JSON,
    )
    db.add(ns)
    await db.flush()

    await create_audit_log(
        db=db,
        actor_id=user.id,
        action="config.namespace_created",
        entity_type="config_namespace",
        entity_id=str(ns.id),
        project_id=env.project_id,
        environment_id=env.id,
        after={"name": ns.name, "format": ns.format.value},
    )
    await db.commit()
    await db.refresh(ns)
    return ns


# ──────────────────────────────────────────────────────────────────────────────
# DRAFT ITEMS OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────


async def list_draft_items(
    db: AsyncSession,
    namespace: ConfigNamespace,
    reveal: bool,
    user_role: MemberRole,
    user: User,
) -> list[ConfigItem]:
    """List current draft items for a namespace.

    If reveal=True, user must have role ADMIN or OWNER. Returns decrypted secret values
    and logs an audit entry. Otherwise secret values are returned as '••••••'.
    """
    stmt = (
        select(ConfigItem)
        .where(ConfigItem.namespace_id == namespace.id)
        .order_by(ConfigItem.key.asc())
    )
    result = await db.scalars(stmt)
    items = list(result.all())

    revealed_secret_keys: list[str] = []

    if reveal:
        if user_role not in (MemberRole.ADMIN, MemberRole.OWNER):
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Only ADMIN or OWNER can reveal secret config values",
                status_code=403,
            )
        for item in items:
            db.expunge(item)
            if item.is_secret:
                revealed_secret_keys.append(item.key)
                try:
                    item.value = decrypt_secret(item.value)
                except Exception:
                    pass

        if revealed_secret_keys:
            await create_audit_log(
                db=db,
                actor_id=user.id,
                action="config.secret_revealed",
                entity_type="config_namespace",
                entity_id=str(namespace.id),
                environment_id=namespace.environment_id,
                after={"revealed_keys": revealed_secret_keys},
            )
            await db.commit()
    else:
        for item in items:
            db.expunge(item)
            if item.is_secret:
                item.value = MASKED_SECRET

    return items


async def update_draft_items(
    db: AsyncSession,
    namespace: ConfigNamespace,
    items_input: list[ConfigItemInput],
    user: User,
) -> list[ConfigItem]:
    """Replace all draft items for a namespace with the provided items."""
    # Load existing items to preserve unchanged secret ciphertexts
    existing_stmt = select(ConfigItem).where(ConfigItem.namespace_id == namespace.id)
    existing_items = list((await db.scalars(existing_stmt)).all())
    existing_map = {item.key: item for item in existing_items}

    # Delete old draft items
    await db.execute(delete(ConfigItem).where(ConfigItem.namespace_id == namespace.id))

    new_items: list[ConfigItem] = []
    for inp in items_input:
        val_to_save = inp.value
        if inp.is_secret:
            # If client sent the masked string and we already had this secret, keep ciphertext
            is_prev_secret = inp.key in existing_map and existing_map[inp.key].is_secret
            if inp.value == MASKED_SECRET and is_prev_secret:
                val_to_save = existing_map[inp.key].value
            else:
                val_to_save = encrypt_secret(inp.value)

        item = ConfigItem(
            namespace_id=namespace.id,
            key=inp.key,
            value=val_to_save,
            value_type=inp.value_type,
            is_secret=inp.is_secret,
            json_schema=inp.json_schema,
            comment=inp.comment,
        )
        db.add(item)
        new_items.append(item)

    await create_audit_log(
        db=db,
        actor_id=user.id,
        action="config.draft_updated",
        entity_type="config_namespace",
        entity_id=str(namespace.id),
        environment_id=namespace.environment_id,
        after={"item_count": len(new_items), "keys": [i.key for i in new_items]},
    )
    await db.commit()

    # Mask secrets before returning - expunge first so setting item.value = MASKED_SECRET
    # does NOT get written back to the DB when get_db auto-commits on request exit
    for item in new_items:
        await db.refresh(item)
        db.expunge(item)
        if item.is_secret:
            item.value = MASKED_SECRET

    return new_items


# ──────────────────────────────────────────────────────────────────────────────
# PENDING DIFF
# ──────────────────────────────────────────────────────────────────────────────


async def get_pending_diff(db: AsyncSession, namespace: ConfigNamespace) -> dict[str, Any]:
    """Compare current draft items against current active release snapshot."""
    # 1. Fetch draft items
    draft_stmt = select(ConfigItem).where(ConfigItem.namespace_id == namespace.id)
    draft_items = list((await db.scalars(draft_stmt)).all())
    draft_configs: dict[str, Any] = {
        item.key: (MASKED_SECRET if item.is_secret else item.value) for item in draft_items
    }

    # 2. Fetch current release
    old_configs: dict[str, Any] = {}
    if namespace.current_release_id is not None:
        rel = await db.scalar(
            select(ConfigRelease).where(ConfigRelease.id == namespace.current_release_id)
        )
        if rel is not None:
            raw_old = rel.snapshot.get("configs", rel.snapshot)
            secret_keys = set(rel.snapshot.get("secrets", []))
            old_configs = {
                k: (MASKED_SECRET if k in secret_keys else v) for k, v in raw_old.items()
            }

    return calculate_config_diff(old_configs, draft_configs)


# ──────────────────────────────────────────────────────────────────────────────
# RELEASE PUBLISH & ROLLBACK
# ──────────────────────────────────────────────────────────────────────────────


async def publish_release(
    db: AsyncSession,
    namespace: ConfigNamespace,
    payload: ConfigReleaseCreate,
    user: User,
) -> ConfigRelease:
    """Validate JSON schemas, snapshot draft items, create ConfigRelease, and bump version."""
    draft_stmt = select(ConfigItem).where(ConfigItem.namespace_id == namespace.id)
    draft_items = list((await db.scalars(draft_stmt)).all())

    # 1. Validate all items against JSON schemas
    validation_errors: dict[str, str] = {}
    for item in draft_items:
        err = validate_item_schema(item)
        if err:
            validation_errors[item.key] = err

    if validation_errors:
        raise FlagOpsError(
            code="CONFIG_VALIDATION_FAILED",
            message="Configuration validation failed against JSON schema",
            status_code=400,
            details={"errors": validation_errors},
        )

    # 2. Calculate next version
    max_ver = await db.scalar(
        select(func.max(ConfigRelease.version)).where(ConfigRelease.namespace_id == namespace.id)
    )
    new_version = (max_ver or 0) + 1

    # 3. Create snapshot (secrets stored encrypted)
    snapshot = {
        "configs": {item.key: item.value for item in draft_items},
        "items": [
            {
                "key": item.key,
                "value": item.value,
                "value_type": item.value_type.value,
                "is_secret": item.is_secret,
                "json_schema": item.json_schema,
                "comment": item.comment,
            }
            for item in draft_items
        ],
        "secrets": [item.key for item in draft_items if item.is_secret],
    }

    release = ConfigRelease(
        namespace_id=namespace.id,
        version=new_version,
        snapshot=snapshot,
        comment=payload.comment,
        released_by=user.id,
    )
    db.add(release)
    await db.flush()

    # 4. Update namespace pointer
    namespace.current_release_id = release.id

    # 5. Bump environment ruleset version (invalidates Redis + publishes Pub/Sub)
    await bump_ruleset_version(db, namespace.environment_id)

    # 6. Audit log
    await create_audit_log(
        db=db,
        actor_id=user.id,
        action="config.published",
        entity_type="config_release",
        entity_id=str(release.id),
        environment_id=namespace.environment_id,
        after={"version": new_version, "item_count": len(draft_items)},
    )
    await db.commit()
    await db.refresh(release)
    return release


async def list_releases(db: AsyncSession, namespace: ConfigNamespace) -> list[ConfigRelease]:
    """List releases for a namespace ordered by version DESC."""
    stmt = (
        select(ConfigRelease)
        .where(ConfigRelease.namespace_id == namespace.id)
        .order_by(ConfigRelease.version.desc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_releases_diff(
    db: AsyncSession,
    namespace: ConfigNamespace,
    v1: int,
    v2: int,
) -> dict[str, Any]:
    """Calculate diff between two published releases."""
    r1 = await db.scalar(
        select(ConfigRelease).where(
            ConfigRelease.namespace_id == namespace.id,
            ConfigRelease.version == v1,
        )
    )
    r2 = await db.scalar(
        select(ConfigRelease).where(
            ConfigRelease.namespace_id == namespace.id,
            ConfigRelease.version == v2,
        )
    )
    if not r1:
        raise FlagOpsError(
            code="RELEASE_NOT_FOUND",
            message=f"Release version {v1} not found",
            status_code=404,
        )
    if not r2:
        raise FlagOpsError(
            code="RELEASE_NOT_FOUND",
            message=f"Release version {v2} not found",
            status_code=404,
        )

    raw1 = r1.snapshot.get("configs", r1.snapshot)
    raw2 = r2.snapshot.get("configs", r2.snapshot)
    sec1 = set(r1.snapshot.get("secrets", []))
    sec2 = set(r2.snapshot.get("secrets", []))

    masked1 = {k: (MASKED_SECRET if k in sec1 else v) for k, v in raw1.items()}
    masked2 = {k: (MASKED_SECRET if k in sec2 else v) for k, v in raw2.items()}

    return calculate_config_diff(masked1, masked2)


async def rollback_release(
    db: AsyncSession,
    namespace: ConfigNamespace,
    target_version: int,
    user: User,
) -> ConfigRelease:
    """Rollback to a previous release by creating a NEW release with the target's snapshot."""
    target_release = await db.scalar(
        select(ConfigRelease).where(
            ConfigRelease.namespace_id == namespace.id,
            ConfigRelease.version == target_version,
        )
    )
    if not target_release:
        raise FlagOpsError(
            code="RELEASE_NOT_FOUND",
            message=f"Release version {target_version} not found",
            status_code=404,
        )

    max_ver = await db.scalar(
        select(func.max(ConfigRelease.version)).where(ConfigRelease.namespace_id == namespace.id)
    )
    new_version = (max_ver or 0) + 1

    # Create new release with target's snapshot, is_rollback_of pointing to target
    new_release = ConfigRelease(
        namespace_id=namespace.id,
        version=new_version,
        snapshot=target_release.snapshot,
        comment=f"Rollback to v{target_version}",
        released_by=user.id,
        is_rollback_of=target_release.id,
    )
    db.add(new_release)
    await db.flush()

    # Update namespace current_release pointer
    namespace.current_release_id = new_release.id

    # Synchronize draft items to match the rolled back release
    await db.execute(delete(ConfigItem).where(ConfigItem.namespace_id == namespace.id))
    snapshot_items = target_release.snapshot.get("items", [])
    if snapshot_items:
        for itm in snapshot_items:
            db.add(
                ConfigItem(
                    namespace_id=namespace.id,
                    key=itm["key"],
                    value=itm["value"],
                    value_type=ConfigValueType(itm["value_type"]),
                    is_secret=itm["is_secret"],
                    json_schema=itm.get("json_schema"),
                    comment=itm.get("comment"),
                )
            )
    else:
        # Fallback to configs dict
        raw_configs = target_release.snapshot.get("configs", target_release.snapshot)
        for k, v in raw_configs.items():
            db.add(
                ConfigItem(
                    namespace_id=namespace.id,
                    key=k,
                    value=v,
                    value_type=ConfigValueType.STRING,
                    is_secret=False,
                )
            )

    # Bump version (invalidates Redis cache and Pub/Sub)
    await bump_ruleset_version(db, namespace.environment_id)

    # Audit log
    await create_audit_log(
        db=db,
        actor_id=user.id,
        action="config.rolled_back",
        entity_type="config_release",
        entity_id=str(new_release.id),
        environment_id=namespace.environment_id,
        after={"version": new_version, "rollback_of": target_version},
    )
    await db.commit()
    await db.refresh(new_release)
    return new_release


# ──────────────────────────────────────────────────────────────────────────────
# CLIENT EVALUATION / READ ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────


async def get_client_config(
    db: AsyncSession,
    env_id: UUID,
    namespace_name: str,
    scope: ApiKeyScope,
) -> tuple[int, dict[str, Any]]:
    """Return published configurations for client SDK with secrets decrypted for SERVER scope."""
    ns = await db.scalar(
        select(ConfigNamespace).where(
            ConfigNamespace.environment_id == env_id,
            ConfigNamespace.name == namespace_name,
        )
    )
    if not ns:
        raise FlagOpsError(
            code="NAMESPACE_NOT_FOUND",
            message=f"Namespace '{namespace_name}' not found in this environment",
            status_code=404,
        )

    if ns.current_release_id is None:
        return 0, {}

    release = await db.scalar(
        select(ConfigRelease).where(ConfigRelease.id == ns.current_release_id)
    )
    if not release:
        return 0, {}

    raw_configs = release.snapshot.get("configs", release.snapshot)
    secret_keys = set(release.snapshot.get("secrets", []))

    resolved: dict[str, Any] = {}
    for k, v in raw_configs.items():
        if k in secret_keys:
            if scope == ApiKeyScope.SERVER:
                try:
                    resolved[k] = decrypt_secret(v)
                except Exception:
                    resolved[k] = v
            else:
                resolved[k] = MASKED_SECRET
        else:
            resolved[k] = v

    return release.version, resolved
