import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ConfigFormat, ConfigValueType


class ConfigNamespace(Base, TimestampMixin):
    __tablename__ = "config_namespace"
    __table_args__ = (UniqueConstraint("environment_id", "name", name="uq_namespace_env_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("environment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    format: Mapped[ConfigFormat] = mapped_column(
        Enum(ConfigFormat, name="config_format", create_type=True),
        default=ConfigFormat.JSON,
        nullable=False,
    )
    current_release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "config_release.id",
            use_alter=True,
            name="fk_namespace_current_release",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


class ConfigItem(Base, TimestampMixin):
    __tablename__ = "config_item"
    __table_args__ = (
        UniqueConstraint("namespace_id", "key", name="uq_item_namespace_key"),
        CheckConstraint(
            "key ~ '^[a-zA-Z0-9._-]+$'",
            name="chk_config_item_key_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    namespace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_namespace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[ConfigValueType] = mapped_column(
        Enum(ConfigValueType, name="config_value_type", create_type=True),
        default=ConfigValueType.STRING,
        nullable=False,
    )
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    json_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConfigRelease(Base, TimestampMixin):
    __tablename__ = "config_release"
    __table_args__ = (
        UniqueConstraint("namespace_id", "version", name="uq_release_namespace_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    namespace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_namespace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    released_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_rollback_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_release.id", ondelete="SET NULL"),
        nullable=True,
    )
