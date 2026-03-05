import asyncio
import logging
import re

import httpx
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)

API = settings.FASTAPI_URL
API_KEY = getattr(settings, "API_KEY", "")

_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=200)

# Allowed sensor name pattern — alphanumeric, hyphen, underscore, max 100 chars.
_SENSOR_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _get_client() -> httpx.AsyncClient:
    """Return (or lazily create) an AsyncClient bound to the current event loop.

    Creating the client per-loop instead of at module scope prevents the
    'Event loop is closed' errors that occur when Gunicorn forks multiple
    UvicornWorker processes — each fork gets a fresh event loop, so the
    parent's asyncio handles would be stale if shared.
    """
    loop = asyncio.get_event_loop()
    client: httpx.AsyncClient | None = getattr(loop, "_httpx_client", None)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            base_url=API,
            timeout=5.0,
            limits=_LIMITS,
        )
        loop._httpx_client = client  # type: ignore[attr-defined]
    return client


def _is_mutation_allowed(request) -> bool:
    """Return True only if mutations are enabled AND the request comes from an
    allowed IP address.  The allowlist is configured via the MUTATION_ALLOWED_IPS
    environment variable (comma-separated, defaults to loopback only).
    """
    if not getattr(settings, "ENABLE_MUTATIONS", False):
        return False
    allowed_ips = set(
        ip.strip()
        for ip in getattr(settings, "MUTATION_ALLOWED_IPS", "127.0.0.1").split(",")
        if ip.strip()
    )
    remote_ip = request.META.get("REMOTE_ADDR", "")
    return remote_ip in allowed_ips


async def dashboard(request):
    """Full-page dashboard view."""
    return render(
        request,
        "sensors/dashboard.html",
        {"enable_mutations": getattr(settings, "ENABLE_MUTATIONS", False)},
    )


async def sensor_table(request):
    """HTMX partial: fetch readings from FastAPI and render table rows."""
    raw_sensor = request.GET.get("sensor", "")
    # Validate sensor name: only alphanumeric/hyphen/underscore, max 100 chars.
    sensor = raw_sensor if _SENSOR_RE.match(raw_sensor) else ""

    params = {"limit": 30}
    if sensor:
        params["sensor"] = sensor

    client = _get_client()
    try:
        resp = await client.get("/api/readings", params=params)
        resp.raise_for_status()
        envelope = resp.json()
        readings = envelope.get("data", [])
    except httpx.HTTPStatusError as exc:
        logger.error("FastAPI returned %s for /api/readings: %s", exc.response.status_code, exc)
        return render(request, "sensors/partials/sensor_table.html", {
            "readings": [],
            "sensor": sensor,
            "error": f"API error ({exc.response.status_code}). Please try again.",
        })
    except httpx.HTTPError as exc:
        logger.exception("Network error fetching /api/readings: %s", exc)
        return render(request, "sensors/partials/sensor_table.html", {
            "readings": [],
            "sensor": sensor,
            "error": "Could not reach the data service. Please try again shortly.",
        })

    return render(request, "sensors/partials/sensor_table.html", {
        "readings": readings,
        "sensor": sensor,
    })


async def stats_cards(request):
    """HTMX partial: fetch stats from FastAPI and render summary cards."""
    client = _get_client()
    try:
        resp = await client.get("/api/stats")
        resp.raise_for_status()
        stats = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("FastAPI returned %s for /api/stats: %s", exc.response.status_code, exc)
        return render(request, "sensors/partials/stats_cards.html", {
            "stats": [],
            "error": f"API error ({exc.response.status_code}).",
        })
    except httpx.HTTPError as exc:
        logger.exception("Network error fetching /api/stats: %s", exc)
        return render(request, "sensors/partials/stats_cards.html", {
            "stats": [],
            "error": "Could not reach the data service.",
        })

    return render(request, "sensors/partials/stats_cards.html", {"stats": stats})


async def seed_data(request):
    """Trigger seed endpoint on FastAPI (append mode), then refresh or redirect."""
    if request.method != "POST":
        return HttpResponse(status=405)
    if not _is_mutation_allowed(request):
        return HttpResponse("Seed endpoint is disabled or not allowed from your IP.", status=403)

    client = _get_client()
    try:
        resp = await client.post(
            "/api/seed",
            headers={"X-API-Key": API_KEY},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Seed API returned %s: %s", exc.response.status_code, exc)
        return HttpResponse(
            f"Seed failed (API error {exc.response.status_code})", status=502
        )
    except httpx.HTTPError as exc:
        logger.exception("Network error calling /api/seed: %s", exc)
        return HttpResponse("Seed failed — data service unreachable", status=502)

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")


async def clear_data(request):
    """Trigger delete endpoint on FastAPI to clear all data, then refresh or redirect."""
    if request.method != "POST":
        return HttpResponse(status=405)
    if not _is_mutation_allowed(request):
        return HttpResponse("Clear endpoint is disabled or not allowed from your IP.", status=403)

    client = _get_client()
    try:
        resp = await client.delete(
            "/api/readings",
            headers={"X-API-Key": API_KEY},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Clear API returned %s: %s", exc.response.status_code, exc)
        return HttpResponse(
            f"Clear failed (API error {exc.response.status_code})", status=502
        )
    except httpx.HTTPError as exc:
        logger.exception("Network error calling DELETE /api/readings: %s", exc)
        return HttpResponse("Clear failed — data service unreachable", status=502)

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")
