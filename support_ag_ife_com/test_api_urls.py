from django.contrib import admin
from django.urls import include, path

from monitoring.api import ingest_report

urlpatterns = [
    path("monitoring/", include("monitoring.urls")),
    path("api/monitoring/v1/reports/", ingest_report),
    path("admin/", admin.site.urls),
]
