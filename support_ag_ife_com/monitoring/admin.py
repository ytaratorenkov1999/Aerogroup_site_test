from django.contrib import admin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.urls import URLPattern, URLResolver, path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .forms import MonitoringAgentForm
from .models import MonitoringAgent, MonitoringReport, Server


@admin.register(Server)
class ServerAdmin(ModelAdmin):
    list_display = ("id", "name", "ip_address", "created_at")
    search_fields = ("name", "ip_address")
    readonly_fields = ("created_at",)
    fields = ("name", "ip_address")
    ordering = ("id",)


@admin.register(MonitoringAgent)
class MonitoringAgentAdmin(ModelAdmin):
    form = MonitoringAgentForm
    list_display = ("server", "site_id", "agent_id", "enabled", "last_seen_at")
    search_fields = ("site_id", "agent_id", "server__name")
    list_filter = ("enabled",)
    readonly_fields = ("last_seen_at",)
    fields = ("server", "site_id", "agent_id", "enabled", "api_token", "last_seen_at")


@admin.register(MonitoringReport)
class MonitoringReportAdmin(ModelAdmin):
    list_display = (
        "report_id", "agent", "sequence", "schema_version", "finished_at",
        "received_at",
    )
    list_filter = ("agent", "schema_version")
    search_fields = ("report_id", "agent__site_id", "agent__agent_id")
    readonly_fields = (
        "report_id", "agent", "schema_version", "stream_id", "sequence",
        "started_at", "finished_at", "received_at", "size_bytes", "sha256",
        "download_link",
    )
    fields = readonly_fields

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: MonitoringReport | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: MonitoringReport | None = None,
    ) -> bool:
        return super().has_delete_permission(request, obj)

    def get_urls(self) -> list[URLPattern | URLResolver]:
        return [
            path(
                "<uuid:report_id>/download/",
                self.admin_site.admin_view(self.download),
                name="monitoring_monitoringreport_download",
            ),
        ] + super().get_urls()

    @admin.display(description="Файл JSON")
    def download_link(self, obj: MonitoringReport) -> str:
        url = reverse(
            "admin:monitoring_monitoringreport_download", args=(obj.report_id,)
        )
        return format_html('<a href="{}">Скачать JSON</a>', url)

    def download(
        self, request: HttpRequest, report_id: str,
    ) -> HttpResponse:
        if not self.has_view_permission(request):
            raise Http404
        try:
            report = MonitoringReport.objects.get(report_id=report_id)
            stream = report.storage_path.open("rb")
        except (MonitoringReport.DoesNotExist, OSError):
            raise Http404 from None
        response = FileResponse(
            stream, as_attachment=True,
            filename=f"{report.report_id}.json", content_type="application/json",
        )
        response["Cache-Control"] = "no-store"
        return response
