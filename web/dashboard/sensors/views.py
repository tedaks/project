import httpx
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

API = settings.FASTAPI_URL
API_KEY = getattr(settings, "API_KEY", "")

# Reuse a single httpx client with connection pooling
_client = httpx.AsyncClient(base_url=API, timeout=5.0)


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
        readings = resp.json()
    except httpx.HTTPError:
        readings = []

    return render(request, "sensors/partials/sensor_table.html", {"readings": readings, "sensor": sensor})


async def stats_cards(request):
    """HTMX partial: fetch stats from FastAPI and render summary cards."""
    try:
        resp = await _client.get("/api/stats")
        resp.raise_for_status()
        stats = resp.json()
    except httpx.HTTPError:
        stats = []

    return render(request, "sensors/partials/stats_cards.html", {"stats": stats})


@csrf_exempt
async def seed_data(request):
    """Trigger seed endpoint on FastAPI, then return 200 for HTMX or redirect."""
    try:
        await _client.post("/api/seed", headers={"X-API-Key": API_KEY}, timeout=10.0)
    except httpx.HTTPError:
        pass

    if request.headers.get("HX-Request"):
        return HttpResponse(status=200)
    return redirect("dashboard")
