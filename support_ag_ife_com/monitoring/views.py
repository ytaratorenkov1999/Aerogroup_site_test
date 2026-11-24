from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .dashboard import build_dashboard
from .demo import build_demo_dashboard
from .models import Server


@login_required(login_url="login")
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "monitoring/monitoring.html", {
        "title": "Мониторинг площадок",
        "servers": [] if request.GET.get("demo") == "1" else Server.objects.all(),
        "demo": request.GET.get("demo") == "1",
    })


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
