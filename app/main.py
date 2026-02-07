"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.jobs.scheduler import register_jobs, scheduler
from app.routers import (
    auth,
    balance,
    chamber,
    communities,
    declarations,
    elections,
    leaderboard,
    ledger,
    members,
    notifications,
    sunset,
)
from app.utils.errors import AppError, InvalidInputError

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop scheduler with app lifecycle."""
    if settings.enable_scheduler:
        register_jobs()
        scheduler.start()
        logger.info("Scheduler started")
    yield
    if settings.enable_scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.app_name,
    description="Bureau of Declared Joy - Backend API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """Add per-request processing time and optionally log slow requests."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

    threshold_ms = settings.slow_request_log_threshold_ms
    if threshold_ms > 0 and elapsed_ms >= threshold_ms:
        logger.warning(
            "Slow request %s %s %.1fms",
            request.method,
            request.url.path,
            elapsed_ms,
        )

    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Convert domain exceptions into structured API responses."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Normalize FastAPI validation responses."""
    detail = exc.errors()
    message = detail[0].get("msg", "Invalid request") if detail else "Invalid request"
    api_error = InvalidInputError(message)
    return JSONResponse(status_code=api_error.status_code, content=api_error.to_dict())


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch unexpected errors without leaking internals."""
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
    )


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(communities.router, prefix="/communities", tags=["communities"])
app.include_router(chamber.router, prefix="/communities/{community_id}/chamber", tags=["chamber"])
app.include_router(
    declarations.router,
    prefix="/communities/{community_id}/gazette",
    tags=["gazette"],
)
app.include_router(ledger.router, prefix="/communities/{community_id}/ledger", tags=["ledger"])
app.include_router(members.router, prefix="/communities/{community_id}/members", tags=["members"])
app.include_router(
    leaderboard.router,
    prefix="/communities/{community_id}",
    tags=["leaderboard"],
)
app.include_router(
    elections.router,
    prefix="/communities/{community_id}/elections",
    tags=["elections"],
)
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(sunset.router, prefix="/communities/{community_id}/sunset", tags=["sunset"])
app.include_router(balance.router, prefix="/communities/{community_id}/balance", tags=["balance"])


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for deploys and uptime probes."""
    return {"status": "ok", "version": settings.app_version}
