from datetime import UTC

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime

from .dashboard import build_dashboard
from .demo import build_demo_dashboard
from datetime import UTC

from django.utils.dateparse import parse_datetime


@login_required(login_url="login")
def index(request: HttpRequest) -> HttpResponse:
    demo = request.GET.get("demo") == "1"
    dashboard = build_demo_dashboard() if demo else build_dashboard()
    for server in dashboard["servers"]:
        checked = (server.get("report") or {}).get("checked_at")
        parsed = parse_datetime(checked) if checked else None
        server["checked_at_display"] = (
            parsed.astimezone(UTC).strftime("%d.%m.%Y, %H:%M:%S UTC")
            if parsed else "-"
        )
    response = render(request, "monitoring/monitoring.html", {
        "title": "Мониторинг хостов",
        "servers": dashboard["servers"],
        "initial_dashboard": dashboard,
        "demo": demo,
    })
    response["Cache-Control"] = "no-store"
    return response


def data(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if request.method != "GET":
        response = JsonResponse({"error": "method_not_allowed"}, status=405)
        response["Allow"] = "GET"
        return response
    dashboard = (
        build_demo_dashboard()
        if request.GET.get("demo") == "1"
        else build_dashboard()
    )
    response = JsonResponse(dashboard)
    response["Cache-Control"] = "no-store"
    return response
