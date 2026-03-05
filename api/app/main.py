import hmac
import logging
import os
from contextlib import asynccontextmanager

import orjson
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, select, text

from .database import async_session, engine
from .models import Base, SensorReading
from .schemas import SensorReadingCreate, SensorReadingOut, StatsOut
from .seed import seed_data

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
API_KEY = os.environ.get("API_KEY", "")
STATS_CACHE_TTL = 30  # seconds

# Rate limiter — keyed by remote IP
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    # Fail fast if required secrets are absent — surface the misconfiguration
    # immediately rather than letting it surface as a cryptic 5xx to callers.
    if not API_KEY:
        raise RuntimeError(
            "API_KEY environment variable is required but not set. "
            "Set it in your .env file or container environment."
        )

    async with engine.begin() as conn:
        # Prevent concurrent DDL race conditions across multiple Uvicorn workers
        await conn.execute(text("SELECT pg_advisory_xact_lock(1337)"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "SELECT create_hypertable('sensor_readings', 'recorded_at', "
                "if_not_exists => TRUE)"
            )
        )

    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    yield

    # --- Shutdown ---
    await app.state.redis.aclose()
    await engine.dispose()


_debug = os.environ.get("DEBUG", "0") == "1"

app = FastAPI(
    title="Sensor API",
    description="FastAPI engine for the Sensor Dashboard demo",
    lifespan=lifespan,
    # Disable interactive API docs in production to avoid exposing endpoint
    # schemas, parameter names, and a live test console to the network.
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

# Attach rate limiter state and its exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — only allow the Django frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("CORS_ORIGIN", "http://localhost:8000"),
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def _verify_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency to verify API key on protected endpoints.

    API_KEY is validated as non-empty at startup (lifespan), so by the time
    any request reaches here it is guaranteed to be set.
    Constant-time comparison prevents timing side-channel attacks.
    """
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")


# ---------- Global exception handler ----------
_logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler: log the full traceback server-side and return a
    structured JSON error to the client without leaking internal details."""
    _logger.exception("Unhandled error on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---------- Health ----------
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------- Readings ----------
@app.post(
    "/api/readings",
    response_model=SensorReadingOut,
    status_code=201,
    dependencies=[Depends(_verify_api_key)],
)
@limiter.limit("60/minute")
async def create_reading(request: Request, payload: SensorReadingCreate):
    async with async_session() as session:
        # Optimization: insert().returning() saves a SELECT round-trip
        stmt = (
            SensorReading.__table__.insert()
            .values(
                sensor_name=payload.sensor_name,
                value=payload.value,
                recorded_at=payload.recorded_at or func.now(),
            )
            .returning(SensorReading)
        )
        result = await session.execute(stmt)
        await session.commit()
        await app.state.redis.delete("stats_cache")
        return result.scalar_one()


@app.get("/api/readings")
@limiter.limit("120/minute")
async def list_readings(
    request: Request,
    sensor: str | None = Query(None, description="Filter by sensor name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    async with async_session() as session:
        count_stmt = select(func.count()).select_from(SensorReading)
        if sensor:
            count_stmt = count_stmt.where(SensorReading.sensor_name == sensor)

        stmt = select(SensorReading).order_by(SensorReading.recorded_at.desc())
        if sensor:
            stmt = stmt.where(SensorReading.sensor_name == sensor)
        stmt = stmt.limit(limit).offset(offset)

        total_result = await session.execute(count_stmt)
        result = await session.execute(stmt)

        total = total_result.scalar_one()
        rows = result.scalars().all()

    envelope = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [SensorReadingOut.model_validate(r).model_dump(mode="json") for r in rows],
    }
    return Response(content=orjson.dumps(envelope), media_type="application/json")


# ---------- Stats ----------
@app.get("/api/stats")
@limiter.limit("120/minute")
async def get_stats(request: Request):
    cached = await app.state.redis.get("stats_cache")
    if cached:
        # Optimization: return raw JSON directly, bypassing Pydantic validation
        return Response(content=cached, media_type="application/json")

    async with async_session() as session:
        stmt = (
            select(
                SensorReading.sensor_name,
                func.count().label("count"),
                func.avg(SensorReading.value).label("avg"),
                func.min(SensorReading.value).label("min"),
                func.max(SensorReading.value).label("max"),
            )
            .group_by(SensorReading.sensor_name)
            .order_by(SensorReading.sensor_name)
        )
        result = await session.execute(stmt)
        rows = [
            StatsOut(
                sensor_name=r.sensor_name,
                count=r.count,
                avg=round(float(r.avg), 2),
                min=round(float(r.min), 2),
                max=round(float(r.max), 2),
            )
            for r in result.all()
        ]

    # Serialize once → store in Redis → return directly (no double serialization)
    payload = orjson.dumps([s.model_dump(mode="json") for s in rows])
    await app.state.redis.set("stats_cache", payload, ex=STATS_CACHE_TTL)
    return Response(content=payload, media_type="application/json")


# ---------- Seed (API-key protected) ----------
@app.post("/api/seed", dependencies=[Depends(_verify_api_key)])
@limiter.limit("10/minute")
async def seed(request: Request):
    count = await seed_data()
    await app.state.redis.delete("stats_cache")
    return {"seeded": count}


# ---------- Clear (API-key protected) ----------
@app.delete("/api/readings", status_code=204, dependencies=[Depends(_verify_api_key)])
@limiter.limit("10/minute")
async def clear_readings(request: Request):
    """Truncates all sensor readings and clears the stats cache."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE sensor_readings RESTART IDENTITY"))
    await app.state.redis.delete("stats_cache")
    return Response(status_code=204)
