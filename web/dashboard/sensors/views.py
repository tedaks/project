import logging

import httpx
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)

API = settings.FASTAPI_URL
API_KEY = getattr(settings, "API_KEY", "")

# Persistent async client — reuses TCP connections across requests for keep-alive efficiency.
# This client lives for the process lifetime; Django does not have a shutdown hook for
# module-level resources, but the OS cleans up on container stop.
_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=200)
_client = httpx.AsyncClient(base_url=API, timeout=5.0, limits=_LIMITS)


async def dashboard(request):
    """Full-page dashboard view."""
    return render(request, "sensors/dashboard.html")


async def sensor_table(request):
    """HTMX partial: fetch readings from FastAPI and render table rows."""
    sensor = request.GET.get("sensor", "")
    params = {"limit": 30}
    if sensor:
        params["sensor"] = sensor

    try:
        resp = await _client.get("/api/readings", params=params)
        resp.raise_for_status()
        envelope = resp.json()
        readings = envelope.get("data", [])
    except httpx.HTTPStatusError as exc:
        logger.error("FastAPI returned %s for /api/readings: %s", exc.response.status_code, exc)
        readings = []
        return render(request, "sensors/partials/sensor_table.html", {
            "readings": readings,
            "sensor": sensor,
            "error": f"API error ({exc.response.status_code}). Please try again.",
        })
    except httpx.HTTPError as exc:
        logger.exception("Network error fetching /api/readings: %s", exc)
        readings = []
        return render(request, "sensors/partials/sensor_table.html", {
            "readings": readings,
            "sensor": sensor,
            "error": "Could not reach the data service. Please try again shortly.",
        })

    return render(request, "sensors/partials/sensor_table.html", {
        "readings": readings,
        "sensor": sensor,
    })


async def stats_cards(request):
    """HTMX partial: fetch stats from FastAPI and render summary cards."""
    try:
        resp = await _client.get("/api/stats")
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

    try:
        await _client.post(
            "/api/seed",
            headers={"X-API-Key": API_KEY},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.exception("Error calling /api/seed: %s", exc)

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")


async def clear_data(request):
    """Trigger delete endpoint on FastAPI to clear all data, then refresh or redirect."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        await _client.delete(
            "/api/readings",
            headers={"X-API-Key": API_KEY},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.exception("Error calling DELETE /api/readings: %s", exc)

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")
