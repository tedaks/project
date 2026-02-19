from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("partials/sensor-table/", views.sensor_table, name="sensor_table"),
    path("partials/stats-cards/", views.stats_cards, name="stats_cards"),
    path("seed/", views.seed_data, name="seed_data"),
]
