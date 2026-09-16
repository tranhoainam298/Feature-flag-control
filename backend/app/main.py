import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.eval import router as eval_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.auth import router as auth_router
from app.api.v1.environments import router as envs_router
from app.api.v1.flags import router as flags_router
from app.api.v1.organizations import router as orgs_router
from app.api.v1.projects import router as projects_router
from app.api.v1.segments import router as segments_router
from app.api.v1.targeting import router as targeting_router
from app.core.config import settings
from app.core.database import check_db_health
from app.core.exceptions import register_exception_handlers
from app.core.redis import check_redis_health

app = FastAPI(
    title="FlagOps API",
    description="Feature Flag & Application Configuration Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID Middleware
@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Register exception handlers for error envelope
register_exception_handlers(app)

# Register API routers
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(projects_router)
app.include_router(envs_router)
app.include_router(api_keys_router)
app.include_router(flags_router)
app.include_router(segments_router)
app.include_router(targeting_router)
app.include_router(eval_router)


@app.get("/health", summary="Basic health check", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", summary="Database health check", tags=["Health"])
async def health_db_check() -> JSONResponse:
    try:
        await check_db_health()
        return JSONResponse(status_code=200, content={"status": "ok", "database": "connected"})
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": str(exc),
            },
        )


@app.get("/health/redis", summary="Redis health check", tags=["Health"])
async def health_redis_check() -> JSONResponse:
    try:
        await check_redis_health()
        return JSONResponse(status_code=200, content={"status": "ok", "redis": "connected"})
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "redis": "disconnected",
                "detail": str(exc),
            },
        )
