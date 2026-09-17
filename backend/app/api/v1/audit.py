"""Audit Log API router."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_project_access
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: UUID | None = None
    project_id: UUID | None = None
    environment_id: UUID | None = None
    actor_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def convert_ip(cls, v: Any) -> str | None:
        return str(v) if v is not None else None


@router.get("", response_model=list[AuditLogResponse], summary="List audit logs with filters")
async def list_audit_logs(
    project_id: UUID = Query(..., description="Project ID is required"),
    environment_id: UUID | None = Query(default=None),
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None, description="Cursor pagination (id < cursor)"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_project_access),
) -> list[AuditLog]:
    """Retrieve audit logs scoped strictly to the specified project."""
    stmt = select(AuditLog).where(AuditLog.project_id == project_id).order_by(AuditLog.id.desc())

    if environment_id:
        stmt = stmt.where(AuditLog.environment_id == environment_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if cursor:
        stmt = stmt.where(AuditLog.id < cursor)

    stmt = stmt.limit(limit)
    result = await db.scalars(stmt)
    return list(result.all())
