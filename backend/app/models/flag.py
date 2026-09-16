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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FlagType, ToggleKind


class Flag(Base, TimestampMixin):
    __tablename__ = "flag"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_flag_project_key"),
        CheckConstraint(
            "key ~ '^[a-zA-Z0-9._-]+$'",
            name="chk_flag_key_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[FlagType] = mapped_column(
        Enum(FlagType, name="flag_type", create_type=True),
        nullable=False,
    )
    toggle_kind: Mapped[ToggleKind] = mapped_column(
        Enum(ToggleKind, name="toggle_kind", create_type=True),
        default=ToggleKind.RELEASE,
        nullable=False,
    )
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_client_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    variations: Mapped[list["Variation"]] = relationship(
        "Variation",
        back_populates="flag",
        cascade="all, delete-orphan",
        order_by="Variation.created_at.asc()",
    )


class Variation(Base, TimestampMixin):
    __tablename__ = "variation"
    __table_args__ = (UniqueConstraint("flag_id", "key", name="uq_variation_flag_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flag.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    flag: Mapped["Flag"] = relationship("Flag", back_populates="variations")
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class FlagEnvironmentSetting(Base, TimestampMixin):
    __tablename__ = "flag_environment_setting"
    __table_args__ = (UniqueConstraint("flag_id", "environment_id", name="uq_fes_flag_env"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flag.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("environment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variation.id", ondelete="SET NULL"),
        nullable=True,
    )
    off_variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variation.id", ondelete="SET NULL"),
        nullable=True,
    )
    bucketing_key: Mapped[str] = mapped_column(String(60), default="userId", nullable=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    targeting_rules: Mapped[list["TargetingRule"]] = relationship(
        "TargetingRule",
        cascade="all, delete-orphan",
        order_by="TargetingRule.priority.asc()",
    )
    individual_overrides: Mapped[list["IndividualOverride"]] = relationship(
        "IndividualOverride",
        cascade="all, delete-orphan",
    )


class Segment(Base, TimestampMixin):
    __tablename__ = "segment"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_segment_project_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class TargetingRule(Base, TimestampMixin):
    __tablename__ = "targeting_rule"
    __table_args__ = (
        UniqueConstraint("flag_environment_setting_id", "priority", name="uq_rule_fes_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    flag_environment_setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flag_environment_setting.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("segment.id", ondelete="SET NULL"),
        nullable=True,
    )
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    distribution: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)


class IndividualOverride(Base, TimestampMixin):
    __tablename__ = "individual_override"
    __table_args__ = (
        UniqueConstraint(
            "flag_environment_setting_id", "context_key", name="uq_override_fes_context_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    flag_environment_setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flag_environment_setting.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_key: Mapped[str] = mapped_column(String(200), nullable=False)
    variation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variation.id", ondelete="CASCADE"),
        nullable=False,
    )
