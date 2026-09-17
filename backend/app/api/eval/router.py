"""Evaluation API router — hot path for SDKs and clients."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import verify_api_key
from app.core.exceptions import FlagOpsError
from app.core.redis import get_redis_pool
from app.models.project import ApiKey, Environment
from app.schemas.eval import (
    EvaluateAllResponse,
    EvaluationRequest,
    EvaluationResponse,
    EventBatchRequest,
    EventBatchResponse,
)
from app.schemas.flag_health import FlagHealthListResponse
from app.services import config_service, ruleset_cache
from app.services import eval as eval_service
from app.services import flag_health as health_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval/v1", tags=["Evaluation"])

_active_sse_connections: int = 0


def get_active_sse_connections() -> int:
    """Return the number of currently active SSE subscriber connections."""
    return _active_sse_connections


async def enforce_rate_limit(api_key: ApiKey = Depends(verify_api_key)) -> ApiKey:
    """Rate limit dependency — 429 if over threshold, fail-open if Redis is down."""
    allowed, remaining = await ruleset_cache.check_rate_limit(api_key.id)
    if not allowed:
        raise FlagOpsError(
            code="RATE_LIMITED",
            message="Rate limit exceeded",
            status_code=429,
            details={"retry_after": 60, "remaining": 0},
        )
    return api_key


SSE_HEARTBEAT_INTERVAL_SECONDS = 25.0


async def _ruleset_event_stream(
    env_id: UUID,
    request: Request | None = None,
    heartbeat_interval: float = SSE_HEARTBEAT_INTERVAL_SECONDS,
    poll_interval: float | None = None,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Yield SSE frames from Redis Pub/Sub channel flagops:ruleset:{env_id} with heartbeats."""
    global _active_sse_connections
    _active_sse_connections += 1
    channel = f"flagops:ruleset:{env_id}"
    pool = get_redis_pool()
    pubsub = None

    try:
        if pool is not None and settings.REDIS_ENABLED:
            try:
                pubsub = pool.pubsub()
                await pubsub.subscribe(channel)
            except Exception as exc:
                logger.warning("Failed to subscribe to Redis channel %s: %s", channel, exc)

        # Initial heartbeat immediately upon connection once subscription is active
        yield ServerSentEvent(event="heartbeat", data="{}")

        if pubsub is None:
            logger.warning("Redis is disabled/unavailable; SSE running in fallback mode")
            while True:
                await asyncio.sleep(heartbeat_interval)
                yield ServerSentEvent(event="heartbeat", data="{}")
            return

        loop = asyncio.get_running_loop()
        last_heartbeat = loop.time()

        while True:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                now = loop.time()

                if msg and msg.get("type") == "message":
                    raw_data = msg.get("data")
                    try:
                        payload = json.loads(raw_data)
                    except Exception:
                        payload = {
                            "environmentId": str(env_id),
                            "rulesetVersion": 0,
                        }
                    yield ServerSentEvent(
                        event="ruleset_updated",
                        data=json.dumps(payload),
                    )
                    last_heartbeat = now
                elif now - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = now
                    yield ServerSentEvent(event="heartbeat", data="{}")

            except (asyncio.CancelledError, GeneratorExit):
                break
            except Exception as e:
                logger.warning("Error reading pubsub message in SSE stream: %s", e)
                await asyncio.sleep(1.0)

    finally:
        _active_sse_connections = max(0, _active_sse_connections - 1)
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception as e:
                logger.debug("Error closing pubsub subscriber: %s", e)
        logger.info(
            "SSE client disconnected for env %s. Active connections: %d",
            env_id,
            _active_sse_connections,
        )


@router.get("/ruleset")
async def get_ruleset(
    environment_id: UUID | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    api_key: ApiKey = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download environment ruleset for SDK evaluation with ETag / 304 Not Modified."""
    if environment_id is not None and environment_id != api_key.environment_id:
        raise FlagOpsError(
            code="FORBIDDEN",
            message="API key is not authorized for this environment",
            status_code=403,
        )

    # Fast check: use eager-loaded environment ruleset_version, falling back to db query
    env_ver = (
        api_key.environment.ruleset_version
        if getattr(api_key, "environment", None) is not None
        else await eval_service.get_environment_version(db, api_key.environment_id)
    )
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
async def stream_ruleset(
    request: Request,
    api_key: ApiKey = Depends(verify_api_key),
) -> EventSourceResponse:
    """Server-Sent Events stream notifying SDKs when the ruleset version changes."""
    return EventSourceResponse(
        _ruleset_event_stream(api_key.environment_id, request=request),
        ping=None,  # We emit explicit event: heartbeat every 25s
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream/connections", summary="Get number of active SSE connections")
async def stream_connections(
    api_key: ApiKey = Depends(verify_api_key),
) -> dict[str, int]:
    """Metric: Number of currently open SSE connections (requires valid API key)."""
    return {"active_connections": _active_sse_connections}


@router.post("/flags/{flag_key}/evaluate", response_model=EvaluationResponse)
async def evaluate_single_flag(
    flag_key: str,
    req: EvaluationRequest,
    api_key: ApiKey = Depends(enforce_rate_limit),
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
    api_key: ApiKey = Depends(enforce_rate_limit),
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
    api_key: ApiKey = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> EventBatchResponse:
    """Ingest evaluation events batch with hashed context keys."""
    count = await eval_service.record_events_batch(
        db=db,
        env_id=api_key.environment_id,
        events=req.events,
    )
    return EventBatchResponse(status="accepted", count=count)


@router.get("/config/{namespace}", summary="Fetch published configurations for namespace")
async def get_config(
    namespace: str,
    environment_id: UUID | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    api_key: ApiKey = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Fetch published configurations for SDK/Client with ETag / 304 Not Modified."""
    target_env_id = environment_id or api_key.environment_id
    if target_env_id != api_key.environment_id:
        raise FlagOpsError(
            code="FORBIDDEN",
            message="API key is not authorized for this environment",
            status_code=403,
        )

    version, configs = await config_service.get_client_config(
        db=db,
        env_id=api_key.environment_id,
        namespace_name=namespace,
        scope=api_key.scope,
    )

    etag_header = f'"{version}"'
    if if_none_match:
        client_ver = if_none_match.strip().strip('"')
        if client_ver == str(version):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag_header})

    payload = {
        "version": version,
        "namespace": namespace,
        "configs": configs,
    }
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_200_OK,
        headers={"ETag": etag_header},
    )


@router.get(
    "/flag-health",
    response_model=FlagHealthListResponse,
    summary="Get flag health data for project associated with API key (used by flag-scanner)",
)
async def get_eval_flag_health(
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> FlagHealthListResponse:
    """Fetch all flag health items in the project for flag-scanner CLI."""
    env = await db.get(Environment, api_key.environment_id)
    if not env:
        raise FlagOpsError(code="NOT_FOUND", message="Environment not found", status_code=404)
    return await health_svc.get_flag_health_list(db, env.project_id)
