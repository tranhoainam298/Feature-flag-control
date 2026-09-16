from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import FlagOpsError
from app.core.permissions import require_flag_role
from app.models.enums import MemberRole
from app.models.flag import Flag
from app.models.project import Environment
from app.schemas.targeting import (
    IndividualOverrideCreate,
    IndividualOverrideResponse,
    SimulateRequest,
    SimulateResponse,
    TargetingRuleResponse,
    TargetingRulesUpdate,
)
from app.services import targeting as targeting_service

router = APIRouter(
    prefix="/api/v1/flags/{flag_id}/environments/{env_id}",
    tags=["targeting"],
)


async def _get_env_in_flag_project(db: AsyncSession, flag: Flag, env_id: UUID) -> Environment:
    """Validate environment exists and belongs to same project as flag."""
    env = await db.scalar(
        select(Environment).where(
            Environment.id == env_id, Environment.project_id == flag.project_id
        )
    )
    if not env:
        raise FlagOpsError(
            code="ENVIRONMENT_NOT_FOUND",
            message="Environment not found in this project",
            status_code=404,
        )
    return env


@router.get("/rules", response_model=list[TargetingRuleResponse])
async def list_targeting_rules(
    env_id: UUID,
    flag_and_member: tuple[Flag, Any] = Depends(require_flag_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[TargetingRuleResponse]:
    """List all targeting rules for a flag in an environment."""
    flag, _ = flag_and_member
    await _get_env_in_flag_project(db, flag, env_id)
    rules = await targeting_service.get_targeting_rules(db, flag.id, env_id)
    return [TargetingRuleResponse.model_validate(r) for r in rules]


@router.put("/rules", response_model=list[TargetingRuleResponse])
async def put_targeting_rules_atomic(
    env_id: UUID,
    rules_data: TargetingRulesUpdate,
    flag_and_member: tuple[Flag, Any] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> list[TargetingRuleResponse]:
    """Atomically replace all targeting rules for a flag in an environment."""
    flag, membership = flag_and_member
    env = await _get_env_in_flag_project(db, flag, env_id)
    new_rules = await targeting_service.set_targeting_rules_atomic(
        db, flag=flag, env=env, rules_data=rules_data, user_id=membership.user_id
    )
    return [TargetingRuleResponse.model_validate(r) for r in new_rules]


@router.post(
    "/overrides",
    response_model=IndividualOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_override(
    env_id: UUID,
    data: IndividualOverrideCreate,
    flag_and_member: tuple[Flag, Any] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> IndividualOverrideResponse:
    """Create or update an individual override."""
    flag, membership = flag_and_member
    env = await _get_env_in_flag_project(db, flag, env_id)
    override = await targeting_service.create_individual_override(
        db, flag=flag, env=env, data=data, user_id=membership.user_id
    )
    return IndividualOverrideResponse.model_validate(override)


@router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_override(
    env_id: UUID,
    override_id: UUID,
    flag_and_member: tuple[Flag, Any] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an individual override."""
    flag, membership = flag_and_member
    env = await _get_env_in_flag_project(db, flag, env_id)
    await targeting_service.delete_individual_override(
        db, flag=flag, env=env, override_id=override_id, user_id=membership.user_id
    )


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_evaluation(
    env_id: UUID,
    req: SimulateRequest,
    flag_and_member: tuple[Flag, Any] = Depends(require_flag_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> SimulateResponse:
    """Simulate evaluation of a feature flag with trace."""
    flag, _ = flag_and_member
    env = await _get_env_in_flag_project(db, flag, env_id)
    return await targeting_service.simulate_flag_evaluation(
        db, flag=flag, env=env, context_raw=req.context
    )
