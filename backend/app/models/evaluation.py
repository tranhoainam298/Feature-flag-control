import uuid
from datetime import datetime

from sqlalchemy import BigInteger, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EvaluationEvent(Base):
    __tablename__ = "evaluation_event"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_evaluation_event"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    environment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    flag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    variation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    context_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
