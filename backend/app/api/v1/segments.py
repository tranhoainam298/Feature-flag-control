from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_project_role
from app.models.enums import MemberRole
from app.models.project import Project
from app.schemas.segment import SegmentCreate, SegmentResponse, SegmentUpdate
from app.services import targeting as targeting_service

router = APIRouter(prefix="/api/v1/projects/{project_id}/segments", tags=["segments"])


@router.get("", response_model=list[SegmentResponse])
async def list_segments(
    project_and_member: tuple[Project, Any] = Depends(require_project_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[SegmentResponse]:
    """List all segments in a project."""
    project, _ = project_and_member
    segments = await targeting_service.get_project_segments(db, project.id)
    return [SegmentResponse.model_validate(s) for s in segments]


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    data: SegmentCreate,
    project_and_member: tuple[Project, Any] = Depends(require_project_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    """Create a new segment in a project."""
    project, membership = project_and_member
    segment = await targeting_service.create_segment(
        db, project=project, data=data, user_id=membership.user_id
    )
    return SegmentResponse.model_validate(segment)


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: UUID,
    project_and_member: tuple[Project, Any] = Depends(require_project_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    """Get segment by ID."""
    project, _ = project_and_member
    segment = await targeting_service.get_segment(db, project.id, segment_id)
    return SegmentResponse.model_validate(segment)


@router.patch("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: UUID,
    data: SegmentUpdate,
    project_and_member: tuple[Project, Any] = Depends(require_project_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    """Update a segment."""
    project, membership = project_and_member
    segment = await targeting_service.update_segment(
        db, project=project, segment_id=segment_id, data=data, user_id=membership.user_id
    )
    return SegmentResponse.model_validate(segment)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: UUID,
    project_and_member: tuple[Project, Any] = Depends(require_project_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a segment."""
    project, membership = project_and_member
    await targeting_service.delete_segment(
        db, project=project, segment_id=segment_id, user_id=membership.user_id
    )
