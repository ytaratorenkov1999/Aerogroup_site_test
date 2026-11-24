import json
import tempfile
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .dashboard import build_dashboard
from .models import MonitoringAgent, MonitoringReport, Server
from .signals import remove_report_file
from .tests import TOKEN, payload

PAGE_TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "OPTIONS": {"loaders": [
        ("django.template.loaders.locmem.Loader", {
            "base.html": "{% block content %}{% endblock %}",
        }),
        "django.template.loaders.app_directories.Loader",
    ]},
}]


class DashboardTests(TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="monitoring-dashboard-")
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MONITORING_REPORTS_ROOT=Path(self.temp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.server = Server.objects.create(name="synthetic-kif", ip_address="192.0.2.13")
        self.agent = MonitoringAgent(
            server=self.server, site_id="afl-test", agent_id="kif", enabled=True
        )
        self.agent.set_api_token(TOKEN)
        self.agent.save()
        self.user = get_user_model().objects.create_user(
            username="synthetic-reader", password="synthetic-password"
        )

    def send(self, data: dict[str, Any] | None = None) -> MonitoringReport:
        data = payload() if data is None else data
        response = self.client.post(
            "/api/monitoring/v1/reports/", data=json.dumps(data),
            content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
        )
        self.assertEqual(response.status_code, 201)
        return MonitoringReport.objects.get(report_id=data["report_id"])

    def login_admin(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="synthetic-admin", password="synthetic-password"
        )
        self.client.force_login(user)

    def test_data_requires_login(self) -> None:
        response = self.client.get(reverse("monitoring:data"))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Location", response)

    def test_reader_sees_measurements_but_not_tokens(self) -> None:
        report = self.send()
        self.client.force_login(self.user)
        response = self.client.get(reverse("monitoring:data"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        server = response.json()["servers"][0]
        self.assertEqual(server["report"]["report_id"], str(report.pk))
        self.assertEqual(server["report"]["checks"][0]["results"][0]["value"], 0)
        self.assertNotContains(response, TOKEN)
        self.assertNotContains(response, self.agent.token_hash)

    def test_data_rejects_post(self) -> None:
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("monitoring:data")).status_code, 405)

    def test_late_old_report_does_not_replace_new_measurement(self) -> None:
        newer = payload()
        newer["sequence"] = 10
        self.send(newer)
        older = payload()
        older.update(
            stream_id=newer["stream_id"], sequence=9,
            started_at="2026-11-18T12:00:00Z", finished_at="2026-11-18T12:00:10Z",
        )
        self.send(older)
        self.assertEqual(
            build_dashboard()["servers"][0]["report"]["report_id"], newer["report_id"]
        )

    def test_missing_file_is_explicit(self) -> None:
        report = self.send()
        report.storage_path.unlink()
        snapshot = build_dashboard()["servers"][0]["report"]
        self.assertEqual(snapshot["error"], "file_missing")
        self.assertEqual(snapshot["checks"], [])

    def test_corrupt_file_is_explicit(self) -> None:
        report = self.send()
        report.storage_path.write_text("{}", encoding="utf-8")
        self.assertEqual(
            build_dashboard()["servers"][0]["report"]["error"], "file_invalid"
        )

    def test_server_without_agent_remains_visible(self) -> None:
        other = Server.objects.create(name="synthetic-new", ip_address="192.0.2.20")
        server = next(s for s in build_dashboard()["servers"] if s["id"] == other.pk)
        self.assertIsNone(server["agent"])
        self.assertIsNone(server["report"])

    def test_agent_without_reports_remains_visible(self) -> None:
        server = build_dashboard()["servers"][0]
        self.assertEqual(server["agent"]["agent_id"], "kif")
        self.assertIsNone(server["report"])

    def test_network_disks_and_content_are_visible(self) -> None:
        data = payload()
        check = data["checks"][0]
        data["checks"].extend([
            {**check, "check_id": "NETWORK", "type": "network", "results": [{
                "target": "192.0.2.1:443", "reachable": False, "error": "refused",
                "details": {"group": "platform", "method": "telnet"},
            }]},
            {**check, "check_id": "DISK", "type": "memory", "results": [{
                "target": "/", "value": 90, "error": None,
                "details": {"used_gb": 9, "size_gb": 10, "avail_gb": 1},
            }]},
            {**check, "check_id": "DATA_FILES", "type": "content", "results": [{
                "target": "DIR", "value": 0, "error": None,
                "details": {
                    "directory": "/content", "last_file": "old.xml",
                    "last_time": "2026-11-18T12:00:00Z", "err_count": 1,
                    "err_files": ["one.err"],
                },
            }]},
        ])
        self.send(data)
        checks = build_dashboard()["servers"][0]["report"]["checks"]
        self.assertEqual(len(checks), 4)
        self.assertIs(checks[1]["results"][0]["reachable"], False)
        self.assertEqual(checks[2]["results"][0]["value"], 90)
        self.assertEqual(checks[3]["results"][0]["details"]["err_count"], 1)

    def test_early_v1_measurements_are_visible(self) -> None:
        data = payload()
        data["schema_version"] = 1
        check = data["checks"][0]
        check["measurements"] = {"counts": {"/reports": 4}}
        check.pop("results")
        self.send(data)
        result = build_dashboard()["servers"][0]["report"]["checks"][0]["results"][0]
        self.assertEqual(result["value"], 4)

    @override_settings(TEMPLATES=PAGE_TEMPLATES)
    def test_page_renders_real_endpoint_and_four_tabs(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("monitoring:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-url="/monitoring/data/"')
        for tab in ("network", "disks", "reports", "content"):
            self.assertContains(response, f'data-tab="{tab}"')
        self.assertNotContains(response, "Демонстрационный режим")

    def test_admin_deletes_report_and_file(self) -> None:
        report = self.send()
        path = report.storage_path
        self.login_admin()
        url = reverse("admin:monitoring_monitoringreport_delete", args=(report.pk,))
        self.assertEqual(self.client.get(url).status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MonitoringReport.objects.exists())
        self.assertFalse(path.exists())

    def test_bulk_delete_removes_only_selected_files(self) -> None:
        first = self.send()
        data = payload()
        data["sequence"] = 2
        second = self.send(data)
        self.login_admin()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:monitoring_monitoringreport_changelist"),
                {"action": "delete_selected", "_selected_action": [str(first.pk)],
                 "post": "yes"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(first.storage_path.exists())
        self.assertTrue(second.storage_path.exists())

    def test_rollback_keeps_file(self) -> None:
        report = self.send()
        path = report.storage_path
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    report.delete()
                    raise RuntimeError("synthetic rollback")
            except RuntimeError:
                pass
        self.assertTrue(path.exists())
        self.assertEqual(MonitoringReport.objects.count(), 1)

    def test_missing_file_does_not_block_deletion(self) -> None:
        report = self.send()
        report.storage_path.unlink()
        self.login_admin()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:monitoring_monitoringreport_delete", args=(report.pk,)),
                {"post": "yes"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MonitoringReport.objects.exists())

    def test_view_only_staff_cannot_delete(self) -> None:
        report = self.send()
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_monitoringreport")
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("admin:monitoring_monitoringreport_delete", args=(report.pk,)),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(report.storage_path.exists())

    def test_existing_receipt_is_not_removed_by_old_cleanup(self) -> None:
        report = self.send()
        remove_report_file(self.agent.pk, report.pk, report.storage_path, "default")
        self.assertTrue(report.storage_path.exists())

    def test_deleted_latest_report_falls_back_to_previous(self) -> None:
        first = self.send()
        data = payload()
        data.update(sequence=2, started_at="2026-11-18T13:45:24Z",
                    finished_at="2026-11-18T13:45:32Z")
        second = self.send(data)
        self.assertEqual(
            build_dashboard()["servers"][0]["report"]["report_id"], str(second.pk)
        )
        with self.captureOnCommitCallbacks(execute=True):
            second.delete()
        self.assertEqual(
            build_dashboard()["servers"][0]["report"]["report_id"], str(first.pk)
        )

    def test_deleted_history_returns_no_report(self) -> None:
        self.send()
        with self.captureOnCommitCallbacks(execute=True):
            MonitoringReport.objects.all().delete()
        self.assertIsNone(build_dashboard()["servers"][0]["report"])
