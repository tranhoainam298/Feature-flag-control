"""FlagOps Demo Web Application.

FastAPI + Jinja2 web application demonstrating runtime feature flagging,
instant rollout toggling, config center values, and fail-safe resilience.
Powered by the FlagOps Python SDK in in_process mode with 5s polling.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from flagops import FlagOpsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_app")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

FLAGOPS_BASE_URL = os.getenv("FLAGOPS_BASE_URL", "http://localhost:8000")
FLAGOPS_API_KEY = os.getenv("FLAGOPS_API_KEY", "fo_srv_dev_secret_key_demo_12345678")
POLLING_INTERVAL = float(os.getenv("FLAGOPS_POLLING_INTERVAL", "5.0"))

# Initialize FlagOps Python SDK in in_process mode
sdk_client = FlagOpsClient(
    api_key=FLAGOPS_API_KEY,
    base_url=FLAGOPS_BASE_URL,
    mode="in_process",
    polling_interval=POLLING_INTERVAL,
    enable_streaming=True,
    timeout=2.0,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting FlagOps Demo App on port 3001 connecting to {FLAGOPS_BASE_URL}...")
    ready = sdk_client.wait_for_ready(timeout=4.0)
    if ready:
        logger.info("FlagOps SDK ruleset loaded successfully (in_process ready).")
    else:
        logger.warning("FlagOps SDK ruleset not yet loaded; starting in degraded/fail-safe mode.")
    yield
    logger.info("Shutting down FlagOps Demo App...")
    sdk_client.close()


app = FastAPI(title="FlagOps Demo Portal", lifespan=lifespan)

# Mount static files and templates
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _get_sdk_health() -> dict[str, Any]:
    """Retrieve internal health and caching status of the SDK client."""
    is_init = sdk_client._cache.is_initialized()
    ruleset = sdk_client._cache.get()
    last_updated = sdk_client._cache.last_updated_at()

    # Try quick ping to transport or verify cache status
    is_degraded = not is_init
    time_str = "Never"
    if last_updated > 0:
        time_str = time.strftime("%H:%M:%S UTC", time.gmtime(last_updated))

    return {
        "is_ready": is_init,
        "is_degraded": is_degraded,
        "status_label": "SDK Ready (In-Process)" if is_init else "SDK Degraded (Serving Cache)",
        "ruleset_version": ruleset.ruleset_version if ruleset else 0,
        "last_sync": time_str,
        "polling_interval": POLLING_INTERVAL,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the primary demonstration dashboard."""
    # 1. Evaluate checkout-v2 for target VN Premium user
    vn_context = {"userId": "user_vn_vip", "country": "VN", "plan": "premium"}
    checkout_eval_vn = sdk_client.get_evaluation("checkout-v2", context=vn_context, default=False)

    # 2. Evaluate checkout-v2 for standard US free user
    us_context = {"userId": "user_us_standard", "country": "US", "plan": "free"}
    checkout_eval_us = sdk_client.get_evaluation("checkout-v2", context=us_context, default=False)

    # 3. Fetch active configuration values from payment-service namespace
    payment_config = sdk_client.get_config("payment-service")
    payment_timeout_ms = payment_config.get("payment.timeout_ms", 3000)
    payment_gateway = payment_config.get("payment.gateway", "stripe")

    # 4. Fetch application namespace config
    app_config = sdk_client.get_config("application")
    maintenance_mode = app_config.get("app.maintenance_mode", "false")
    rate_limit = app_config.get("app.rate_limit_per_min", 100)

    sdk_health = _get_sdk_health()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "sdk_health": sdk_health,
            "checkout_eval_vn": checkout_eval_vn,
            "checkout_eval_us": checkout_eval_us,
            "payment_timeout_ms": payment_timeout_ms,
            "payment_gateway": payment_gateway,
            "maintenance_mode": maintenance_mode,
            "rate_limit": rate_limit,
        },
    )


class EvaluateRequest(BaseModel):
    flag_key: str = "checkout-v2"
    user_id: str = "demo_user_1"
    country: str = "VN"
    plan: str = "premium"


@app.post("/api/evaluate")
async def api_evaluate(req: EvaluateRequest):
    """Evaluate a flag with arbitrary context in real-time."""
    context = {
        "userId": req.user_id,
        "country": req.country,
        "plan": req.plan,
    }
    start = time.perf_counter()
    eval_res = sdk_client.get_evaluation(req.flag_key, context=context, default=None)
    latency_us = round((time.perf_counter() - start) * 1_000_000, 2)

    return {
        "flag_key": req.flag_key,
        "value": eval_res.value,
        "variant": eval_res.variant,
        "reason": eval_res.reason.value if hasattr(eval_res.reason, "value") else str(eval_res.reason),
        "context": context,
        "latency_us": latency_us,
    }


class SimulateRequest(BaseModel):
    flag_key: str = "new-homepage"
    sample_size: int = 1000


@app.post("/api/simulate-1000")
async def api_simulate_1000(req: SimulateRequest):
    """Execute in-process evaluation across 1,000 distinct users to verify distribution."""
    flag_key = req.flag_key
    sample_size = min(max(req.sample_size, 100), 5000)

    start = time.perf_counter()
    counts: dict[str, int] = {}

    for i in range(1, sample_size + 1):
        uid = f"user_{i}_{sample_size}"
        variant = sdk_client.get_variant(flag_key, context={"userId": uid}, default="default")
        counts[variant] = counts.get(variant, 0) + 1

    total_time_ms = round((time.perf_counter() - start) * 1000, 2)
    avg_eval_us = round((total_time_ms * 1000) / sample_size, 2)

    percentages = {
        v: round((cnt / sample_size) * 100, 1) for v, cnt in counts.items()
    }

    return {
        "flag_key": flag_key,
        "sample_size": sample_size,
        "counts": counts,
        "percentages": percentages,
        "total_time_ms": total_time_ms,
        "avg_eval_us": avg_eval_us,
    }


@app.get("/api/status")
async def api_status():
    """Lightweight endpoint for frontend live-polling."""
    sdk_health = _get_sdk_health()

    # Current state of checkout-v2 for VN Premium user
    vn_context = {"userId": "user_vn_vip", "country": "VN", "plan": "premium"}
    eval_vn = sdk_client.get_evaluation("checkout-v2", context=vn_context, default=False)

    payment_config = sdk_client.get_config("payment-service")
    timeout_ms = payment_config.get("payment.timeout_ms", 3000)

    return {
        **sdk_health,
        "checkout_v2_enabled": bool(eval_vn.value),
        "checkout_v2_variant": eval_vn.variant,
        "checkout_v2_reason": eval_vn.reason.value if hasattr(eval_vn.reason, "value") else str(eval_vn.reason),
        "payment_timeout_ms": timeout_ms,
    }
