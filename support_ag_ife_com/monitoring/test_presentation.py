from copy import deepcopy
from typing import Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .presentation import server_indicator

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "OPTIONS": {"loaders": [
        ("django.template.loaders.locmem.Loader", {
            "base.html": (
                "<head>{% block extra_css %}{% endblock %}</head>"
                "{% block page_header %}<h1>Старый заголовок</h1>{% endblock %}"
                "{% block content %}{% endblock %}"
            ),
        }),
        "django.template.loaders.app_directories.Loader",
    ]},
}]


def sample_server() -> dict[str, Any]:
    return {
        "id": 1, "name": "Synthetic server", "ip_address": "192.0.2.1",
        "agent": {"enabled": True, "agent_id": "synthetic-agent"},
        "report": {
            "error": None, "checked_at": "2026-11-24T10:30:00Z",
            "checks": [
                {"type": "network", "enabled": True, "error": None, "results": [
                    {"reachable": True, "error": None, "details": {"group": "customer"}},
                ]},
                {"type": "memory", "enabled": True, "error": None, "results": [
                    {"value": 85, "error": None, "details": {}},
                ]},
                {"type": "content", "enabled": True, "error": None, "results": [
                    {"value": 0, "error": None, "details": {"err_count": 0}},
                ]},
            ],
        },
    }


class IndicatorTests(SimpleTestCase):
    def test_success_is_green_even_in_disk_warning_range(self) -> None:
        self.assertEqual(server_indicator(sample_server(), 90)["kind"], "ok")

    def test_network_disk_content_and_collection_failures_are_red(self) -> None:
        original = sample_server()
        for reason in ("network", "disk", "content", "check", "file"):
            with self.subTest(reason=reason):
                server = deepcopy(original)
                checks = server["report"]["checks"]
                if reason == "network":
                    checks[0]["results"][0]["reachable"] = False
                elif reason == "disk":
                    checks[1]["results"][0]["value"] = 90
                elif reason == "content":
                    checks[2]["results"][0]["details"]["err_count"] = 1
                elif reason == "check":
                    checks[0]["error"] = "check_timeout"
                else:
                    server["report"]["error"] = "file_missing"
                self.assertEqual(server_indicator(server, 90)["kind"], "bad")

    def test_no_report_and_incomplete_results_are_gray(self) -> None:
        server = sample_server()
        server["report"] = None
        self.assertEqual(server_indicator(server, 90)["kind"], "unknown")
        server = sample_server()
        server["report"]["checks"][0]["results"][0]["reachable"] = None
        self.assertEqual(server_indicator(server, 90)["kind"], "unknown")

    def test_disabled_failed_check_is_not_a_problem(self) -> None:
        server = sample_server()
        server["report"]["checks"][0].update(enabled=False, error="old_error")
        self.assertEqual(server_indicator(server, 90)["kind"], "ok")


@override_settings(TEMPLATES=TEMPLATES)
class InitialRenderTests(TestCase):
    def test_first_html_has_final_layout_and_bootstrap(self) -> None:
        user = get_user_model().objects.create_user(username="render-reader")
        self.client.force_login(user)
        server = sample_server()
        server["indicator"] = server_indicator(server, 90)
        data = {"servers": [server], "disk_limit": 90}
        with patch("monitoring.views.build_dashboard", return_value=data):
            response = self.client.get(reverse("monitoring:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertContains(response, "mon-server-details")
        self.assertContains(response, "mon-dot--ok")
        self.assertContains(response, "synthetic-agent")
        self.assertContains(response, "24.11.2026, 10:30:00 UTC")
        self.assertContains(response, 'id="monInitialData"')
        self.assertNotContains(response, "Загрузка")
        self.assertNotContains(response, "Старый заголовок")
        self.assertContains(response, "Мониторинг хостов")
        text = response.content.decode()
        self.assertLess(text.index("monitoring.css"), text.index("</head>"))
