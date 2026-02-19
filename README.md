# Sensor Dashboard

A full-stack demo app showcasing **Django** (UI) + **FastAPI** (API engine) + **HTMX** + **Tailwind CSS** + **TimescaleDB** + **PgBouncer** + **Redis**, all orchestrated with **Docker Compose**.

## Architecture

```
Browser ──▶ Django :8000 ──(httpx)──▶ FastAPI :8001 ──▶ PgBouncer ──▶ TimescaleDB
                                          │
                                          └──▶ Redis (cache)
```

| Service         | Role                      | Internal | Exposed |
|-----------------|---------------------------|----------|---------|
| **Django**      | Web UI (HTMX + Tailwind)  | 8000     | `:8000` |
| **FastAPI**     | REST API engine           | 8001     | `:8001` |
| **TimescaleDB** | Time-series database      | 5432     | —       |
| **PgBouncer**   | Connection pooler         | 6432     | —       |
| **Redis**       | Caching (password-protected) | 6379  | —       |

> Internal-only services are **not** exposed to the host.

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd sensor-dashboard
cp .env.example .env
# Edit .env — set strong passwords and a random SECRET_KEY

# 2. Build and start
docker compose up --build -d

# 3. Seed demo data (requires API key from .env)
curl -H "X-API-Key: <your-api-key>" -X POST http://localhost:8001/api/seed

# 4. Open the dashboard
open http://localhost:8000
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_USER` | Database user | ✅ |
| `POSTGRES_PASSWORD` | Database password | ✅ |
| `POSTGRES_DB` | Database name | ✅ |
| `REDIS_PASSWORD` | Redis authentication password | ✅ |
| `SECRET_KEY` | Django secret key | ✅ |
| `API_KEY` | API key for protected endpoints | ✅ |
| `DEBUG` | Django debug mode (`0` or `1`) | ❌ |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | ❌ |

## Stack Highlights

- **Django → FastAPI**: Django views call FastAPI via connection-pooled `httpx.Client`
- **HTMX**: Stats cards and sensor table auto-refresh every 5 seconds — zero JS frameworks
- **Tailwind CSS**: Dark-themed dashboard via CDN
- **TimescaleDB**: `sensor_readings` table is a hypertable, partitioned by `recorded_at`
- **PgBouncer**: Transaction-mode pooling between FastAPI and TimescaleDB
- **Redis**: Password-protected; FastAPI caches aggregated stats (30s TTL)

## Security

- 🔒 Internal services (DB, Redis, PgBouncer) are **not exposed** to the host network
- 🔑 Destructive endpoints require `X-API-Key` header
- 🛡️ Containers run as **non-root** `appuser`
- 🌐 CORS restricted to Django frontend origin
- ✅ Input validation on all API payloads
- 🔐 Redis requires password authentication

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | — | Health check |
| POST | `/api/readings` | — | Create a sensor reading |
| GET | `/api/readings` | — | List readings (`?sensor=&limit=`) |
| GET | `/api/stats` | — | Aggregated stats (cached 30s) |
| POST | `/api/seed` | 🔑 | Seed 100 random readings |

## Stopping

```bash
docker compose down        # Stop containers
docker compose down -v     # Stop and remove volumes
```

## License

MIT
