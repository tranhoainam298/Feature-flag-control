from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import FlagOpsError
from app.core.permissions import require_flag_role
from app.models.enums import ChangeRequestStatus, MemberRole
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
from app.services.change_request import change_request_service

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
):
    """Atomically replace all targeting rules for a flag in an environment."""
    flag, membership = flag_and_member
    env = await _get_env_in_flag_project(db, flag, env_id)

    # Rule: is_production = True -> DO NOT apply directly, create PENDING ChangeRequest
    if env.is_production:
        cr = await change_request_service.create_change_request(
            db=db,
            env_id=env.id,
            user_id=membership.user_id,
            title=f"Update targeting rules for {flag.key}",
            description="Auto-generated change request for production environment",
            payload={
                "type": "targeting_rules",
                "flag_id": str(flag.id),
                "flag_key": flag.key,
                "rules": [r.model_dump(mode="json") for r in rules_data.rules],
            },
            status=ChangeRequestStatus.PENDING,
        )
        existing_rules = await targeting_service.get_targeting_rules(db, flag.id, env_id)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "change_request_id": str(cr.id),
                "change_request_status": cr.status.value,
                "message": "Change request created in PENDING status for production environment",
                "rules": [
                    TargetingRuleResponse.model_validate(r).model_dump(mode="json")
                    for r in existing_rules
                ],
            },
            headers={"X-Change-Request-Id": str(cr.id)},
        )

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
