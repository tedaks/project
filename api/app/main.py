import json
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from .database import async_session, engine
from .models import Base, SensorReading
from .schemas import SensorReadingCreate, SensorReadingOut, StatsOut
from .seed import seed_data

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
API_KEY = os.environ.get("API_KEY", "")
STATS_CACHE_TTL = 30  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    async with engine.begin() as conn:
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


app = FastAPI(
    title="Sensor API",
    description="FastAPI engine for the Sensor Dashboard demo",
    lifespan=lifespan,
)

# CORS — only allow the Django frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("CORS_ORIGIN", "http://localhost:8000"),
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _verify_api_key(x_api_key: str = Header(default="")):
    """Dependency to verify API key on destructive endpoints."""
    if not API_KEY:
        return  # No key configured — allow (dev mode)
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ---------- Health ----------
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------- Readings ----------
@app.post("/api/readings", response_model=SensorReadingOut, status_code=201)
async def create_reading(payload: SensorReadingCreate):
    async with async_session() as session:
        reading = SensorReading(
            sensor_name=payload.sensor_name,
            value=payload.value,
            recorded_at=payload.recorded_at,
        )
        session.add(reading)
        await session.commit()
        await session.refresh(reading)
        await app.state.redis.delete("stats_cache")
        return reading


@app.get("/api/readings", response_model=list[SensorReadingOut])
async def list_readings(
    sensor: str | None = Query(None, description="Filter by sensor name"),
    limit: int = Query(50, ge=1, le=500),
):
    async with async_session() as session:
        stmt = select(SensorReading).order_by(SensorReading.recorded_at.desc())
        if sensor:
            stmt = stmt.where(SensorReading.sensor_name == sensor)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()


# ---------- Stats ----------
@app.get("/api/stats", response_model=list[StatsOut])
async def get_stats():
    cached = await app.state.redis.get("stats_cache")
    if cached:
        return json.loads(cached)

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

    await app.state.redis.set(
        "stats_cache",
        json.dumps([s.model_dump(mode="json") for s in rows]),
        ex=STATS_CACHE_TTL,
    )
    return rows


# ---------- Seed (API-key protected) ----------
@app.post("/api/seed")
async def seed(x_api_key: str = Header(default="")):
    _verify_api_key(x_api_key)
    count = await seed_data()
    await app.state.redis.delete("stats_cache")
    return {"seeded": count}
