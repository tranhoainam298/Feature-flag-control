import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ApiKeyScope


class Project(Base, TimestampMixin):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    default_stale_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


class Environment(Base, TimestampMixin):
    __tablename__ = "environment"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_environment_project_key"),)

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
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    is_production: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ruleset_version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_key"

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
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    scope: Mapped[ApiKeyScope] = mapped_column(
        Enum(ApiKeyScope, name="api_key_scope", create_type=True),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    environment: Mapped["Environment"] = relationship("Environment")
