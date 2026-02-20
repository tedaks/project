import httpx
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

API = settings.FASTAPI_URL
API_KEY = getattr(settings, "API_KEY", "")

_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=200)

def create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, timeout=5.0, limits=_LIMITS)


async def dashboard(request):
    """Full-page dashboard view."""
    return render(request, "sensors/dashboard.html")


async def sensor_table(request):
    """HTMX partial: fetch readings from FastAPI and render table rows."""
    sensor = request.GET.get("sensor", "")
    params = {"limit": 30}
    if sensor:
        params["sensor"] = sensor

    async with create_client() as client:
        try:
            resp = await client.get("/api/readings", params=params)
            resp.raise_for_status()
            readings = resp.json()
        except httpx.HTTPError:
            readings = []

    return render(request, "sensors/partials/sensor_table.html", {"readings": readings, "sensor": sensor})


async def stats_cards(request):
    """HTMX partial: fetch stats from FastAPI and render summary cards."""
    async with create_client() as client:
        try:
            resp = await client.get("/api/stats")
            resp.raise_for_status()
            stats = resp.json()
        except httpx.HTTPError:
            stats = []

    return render(request, "sensors/partials/stats_cards.html", {"stats": stats})


@csrf_exempt
async def seed_data(request):
    """Trigger seed endpoint on FastAPI, then return 200 for HTMX or redirect."""
    async with create_client() as client:
        try:
            await client.post("/api/seed", headers={"X-API-Key": API_KEY}, timeout=10.0)
        except httpx.HTTPError:
            pass

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")


@csrf_exempt
async def clear_data(request):
    """Trigger delete endpoint on FastAPI to clear all data, then return 200 for HTMX or redirect."""
    async with create_client() as client:
        try:
            await client.delete("/api/readings", headers={"X-API-Key": API_KEY}, timeout=10.0)
        except httpx.HTTPError:
            pass

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")
