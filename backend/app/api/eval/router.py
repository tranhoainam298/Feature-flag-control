"""Evaluation API router — hot path for SDKs and clients."""

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
from app.core.deps import verify_api_key
from app.core.exceptions import FlagOpsError
from app.models.project import ApiKey
from app.schemas.eval import (
    EvaluateAllResponse,
    EvaluationRequest,
    EvaluationResponse,
    EventBatchRequest,
    EventBatchResponse,
)
from app.services import eval as eval_service

router = APIRouter(prefix="/eval/v1", tags=["Evaluation"])

SSE_POLL_INTERVAL_SECONDS = 2.0
SSE_HEARTBEAT_INTERVAL_SECONDS = 25.0


async def _ruleset_event_stream(
    env_id: UUID,
    poll_interval: float = SSE_POLL_INTERVAL_SECONDS,
    heartbeat_interval: float = SSE_HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames whenever the environment ruleset_version changes."""
    last_version = -1
    loop = asyncio.get_running_loop()
    last_heartbeat = loop.time()
    while True:
        async with async_session_factory() as session:
            version = await eval_service.get_environment_version(session, env_id)
        now = loop.time()
        if version != last_version:
            last_version = version
            data = json.dumps({"environmentId": str(env_id), "rulesetVersion": version})
            yield f"event: ruleset_updated\ndata: {data}\n\n"
            last_heartbeat = now
        elif now - last_heartbeat >= heartbeat_interval:
            last_heartbeat = now
            yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(poll_interval)


@router.get("/ruleset")
async def get_ruleset(
    environment_id: UUID | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download environment ruleset for SDK evaluation with ETag / 304 Not Modified."""
    if environment_id is not None and environment_id != api_key.environment_id:
        raise FlagOpsError(
            code="FORBIDDEN",
            message="API key is not authorized for this environment",
            status_code=403,
        )

    # Fast check: only read ruleset_version
    env_ver = await eval_service.get_environment_version(db, api_key.environment_id)
    etag_header = f'"{env_ver}"'

    if if_none_match:
        client_ver = if_none_match.strip().strip('"')
        if client_ver == str(env_ver):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag_header})

    # Version changed or first fetch: build ruleset
    payload = await eval_service.get_ruleset_payload(db, api_key.environment, api_key.scope)
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_200_OK,
        headers={"ETag": etag_header},
    )


@router.get("/stream", summary="Stream ruleset updates via SSE")
async def stream_ruleset(api_key: ApiKey = Depends(verify_api_key)) -> StreamingResponse:
    """Server-Sent Events stream notifying SDKs when the ruleset version changes."""
    return StreamingResponse(
        _ruleset_event_stream(api_key.environment_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/flags/{flag_key}/evaluate", response_model=EvaluationResponse)
async def evaluate_single_flag(
    flag_key: str,
    req: EvaluationRequest,
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """Evaluate a single feature flag."""
    return await eval_service.evaluate_flag(
        db=db,
        env=api_key.environment,
        flag_key=flag_key,
        raw_context=req.context,
        scope=api_key.scope,
    )


@router.post("/flags/evaluate-all", response_model=EvaluateAllResponse)
async def evaluate_all(
    req: EvaluationRequest,
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> EvaluateAllResponse:
    """Evaluate all feature flags in the environment."""
    return await eval_service.evaluate_all_flags(
        db=db,
        env=api_key.environment,
        raw_context=req.context,
        scope=api_key.scope,
    )


@router.post("/events", response_model=EventBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_events(
    req: EventBatchRequest,
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> EventBatchResponse:
    """Ingest evaluation events batch with hashed context keys."""
    count = await eval_service.record_events_batch(
        db=db,
        env_id=api_key.environment_id,
        events=req.events,
    )
    return EventBatchResponse(status="accepted", count=count)
