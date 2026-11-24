import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import MonitoringAgentForm
from .models import MonitoringAgent, MonitoringReport, Server

URL = "/api/monitoring/v1/reports/"
TOKEN = "synthetic-test-token-for-agent-one-000001"


def payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "report_id": str(uuid4()),
        "stream_id": str(uuid4()),
        "sequence": 1,
        "site_id": "afl-test",
        "agent_id": "kif",
        "agent_version": "1.1.0",
        "started_at": "2026-11-18T13:40:24Z",
        "finished_at": "2026-11-18T13:40:32Z",
        "interval_seconds": 300,
        "next_cycle_due_at": "2026-11-18T13:45:24Z",
        "agent_errors": [],
        "delivery": {
            "pending_reports": 0, "payload_bytes": 0,
            "dropped_reports_total": 0, "storage_available": True,
        },
        "checks": [{
            "check_id": "REPORT", "type": "report",
            "description": "REPORT", "enabled": True,
            "started_at": "2026-11-18T13:40:31Z",
            "finished_at": "2026-11-18T13:40:32Z",
            "duration_ms": 1000, "error": None,
            "results": [{
                "target": "/var/pifet/queue/test/reports",
                "value": 0, "error": None, "details": {},
            }],
        }],
    }


class IngestTests(TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="monitoring-api-test-")
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MONITORING_REPORTS_ROOT=Path(self.temp.name))
        override.enable()
        self.addCleanup(override.disable)
        server = Server.objects.create(name="synthetic-kif", ip_address="192.0.2.13")
        self.agent = MonitoringAgent(
            server=server, site_id="afl-test", agent_id="kif", enabled=True,
        )
        self.agent.set_api_token(TOKEN)
        self.agent.save()
        self.client = Client(enforce_csrf_checks=True)

    def send(
        self, data: dict[str, Any] | bytes | None = None,
        token: str | None = TOKEN, **extra: Any,
    ) -> Any:
        value = payload() if data is None else data
        body = (
            value if isinstance(value, bytes)
            else json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        )
        headers = {}
        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        headers.update(extra)
        return self.client.post(
            URL, data=body, content_type="application/json", **headers,
        )

    def test_accepts_and_preserves_exact_json_bytes(self) -> None:
        body = json.dumps(payload(), ensure_ascii=False, indent=2).encode("utf-8")
        response = self.send(body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["accepted"], True)
        report = MonitoringReport.objects.get()
        self.assertEqual(response.json()["report_id"], str(report.report_id))
        self.assertEqual(report.storage_path.read_bytes(), body)
        self.assertEqual(report.size_bytes, len(body))
        self.agent.refresh_from_db()
        self.assertIsNotNone(self.agent.last_seen_at)

    def test_requires_authentication_without_redirect(self) -> None:
        response = self.send(token=None)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Location", response)
        self.assertFalse(MonitoringReport.objects.exists())
        self.assertEqual(list(Path(self.temp.name).rglob("*.json")), [])

    def test_rejects_wrong_token(self) -> None:
        self.assertEqual(self.send(token="x" * 32).status_code, 401)

    def test_rejects_disabled_agent(self) -> None:
        self.agent.enabled = False
        self.agent.save()
        self.assertEqual(self.send().status_code, 401)

    def test_token_is_not_stored_plaintext(self) -> None:
        self.agent.refresh_from_db()
        self.assertNotEqual(self.agent.token_hash, TOKEN)
        self.assertEqual(len(self.agent.token_hash), 64)

    def test_identity_is_bound_to_token(self) -> None:
        for key in ("site_id", "agent_id"):
            data = payload()
            data[key] = "another-agent"
            self.assertEqual(self.send(data).status_code, 403)
        self.assertFalse(MonitoringReport.objects.exists())

    def test_exact_retry_is_idempotent(self) -> None:
        data = payload()
        self.assertEqual(self.send(data).status_code, 201)
        self.assertEqual(self.send(data).status_code, 200)
        self.assertEqual(MonitoringReport.objects.count(), 1)
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.json"))), 1)

    def test_report_id_cannot_be_reused_with_different_content(self) -> None:
        data = payload()
        self.assertEqual(self.send(data).status_code, 201)
        modified = deepcopy(data)
        modified["checks"][0]["results"][0]["value"] = 100
        self.assertEqual(self.send(modified).status_code, 409)
        self.assertEqual(
            json.loads(MonitoringReport.objects.get().storage_path.read_bytes()),
            data,
        )

    def test_stream_sequence_conflict(self) -> None:
        data = payload()
        self.assertEqual(self.send(data).status_code, 201)
        data["report_id"] = str(uuid4())
        self.assertEqual(self.send(data).status_code, 409)
        self.assertEqual(MonitoringReport.objects.count(), 1)

    def test_idempotency_header_must_match_report(self) -> None:
        self.assertEqual(
            self.send(HTTP_IDEMPOTENCY_KEY=str(uuid4())).status_code, 400
        )
        data = payload()
        self.assertEqual(self.send(
            data, HTTP_IDEMPOTENCY_KEY=data["report_id"]
        ).status_code, 201)

    def test_unsupported_http_method(self) -> None:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_json_content_type_required(self) -> None:
        response = self.client.post(
            URL, data="{}", content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
        )
        self.assertEqual(response.status_code, 415)

    def test_body_limit(self) -> None:
        with patch("monitoring.api.MAX_BODY_BYTES", 64):
            self.assertEqual(self.send().status_code, 413)
        self.assertFalse(MonitoringReport.objects.exists())

    def test_rejects_invalid_json_and_duplicate_keys(self) -> None:
        for body in (
            b"not json", b'{"schema_version":2,"schema_version":1}',
            b'{"value":NaN}', b"\xff", b"[]",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.send(body).status_code, 400)

    def test_invalid_fields_do_not_create_receipt(self) -> None:
        for field, value in (
            ("schema_version", 3), ("schema_version", True),
            ("sequence", False), ("sequence", 0),
            ("report_id", "../../escape"),
            ("stream_id", "invalid"), ("site_id", "../site"),
            ("started_at", "2026-11-18T13:40:24"),
            ("finished_at", "2026-11-18T12:00:00Z"),
            ("interval_seconds", -1),
        ):
            with self.subTest(field=field):
                data = payload()
                data[field] = value
                self.assertEqual(self.send(data).status_code, 400)
        self.assertFalse(MonitoringReport.objects.exists())

    def test_v2_rejects_removed_status_fields(self) -> None:
        data = payload()
        data["checks"][0]["status"] = "ok"
        self.assertEqual(self.send(data).status_code, 400)

    def test_v2_accepts_network_error_and_disabled_targets(self) -> None:
        data = payload()
        check = data["checks"][0]
        check.update(check_id="NETWORK", type="network")
        check["results"] = [{
            "target": "NETWORK_MQ", "enabled": False,
            "reachable": None, "error": None,
            "details": {"group": "customer", "method": "telnet"},
        }]
        self.assertEqual(self.send(data).status_code, 201)

    def test_accepts_existing_v1_queue_reports(self) -> None:
        data = payload()
        data["schema_version"] = 1
        data["status"] = "ok"
        check = data["checks"][0]
        check.pop("enabled")
        check.update(status="ok", problems=[], diagnostics=[])
        self.assertEqual(self.send(data).status_code, 201)

    def test_accepts_early_v1_measurements(self) -> None:
        data = payload()
        data["schema_version"] = 1
        check = data["checks"][0]
        check["measurements"] = {"counts": {"/reports": 0}}
        check.pop("results")
        self.assertEqual(self.send(data).status_code, 201)

    def test_out_of_order_reports_are_archived(self) -> None:
        newer = payload()
        newer["sequence"] = 10
        self.assertEqual(self.send(newer).status_code, 201)
        older = payload()
        older["stream_id"] = newer["stream_id"]
        older["sequence"] = 9
        self.assertEqual(self.send(older).status_code, 201)
        self.assertEqual(MonitoringReport.objects.count(), 2)

    def test_file_failure_does_not_acknowledge_or_save_receipt(self) -> None:
        with patch("monitoring.api.store_report", side_effect=OSError("synthetic")):
            self.assertEqual(self.send().status_code, 503)
        self.assertFalse(MonitoringReport.objects.exists())
        self.agent.refresh_from_db()
        self.assertIsNone(self.agent.last_seen_at)

    def test_database_failure_is_retryable_with_same_report(self) -> None:
        data = payload()
        with patch(
            "monitoring.api.MonitoringReport.objects.create",
            side_effect=DatabaseError("synthetic"),
        ):
            self.assertEqual(self.send(data).status_code, 503)
        self.assertFalse(MonitoringReport.objects.exists())
        self.assertEqual(self.send(data).status_code, 201)

    def test_agent_form_does_not_require_rotation(self) -> None:
        form = MonitoringAgentForm(data={
            "server": self.agent.server_id,
            "site_id": self.agent.site_id, "agent_id": self.agent.agent_id,
            "enabled": True, "api_token": "",
        }, instance=self.agent)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_agent_form_requires_token_before_enabling(self) -> None:
        server = Server.objects.create(name="synthetic-pollux", ip_address="192.0.2.12")
        form = MonitoringAgentForm(data={
            "server": server.pk, "site_id": "sdm-test", "agent_id": "pollux",
            "enabled": True, "api_token": "",
        })
        self.assertFalse(form.is_valid())

    def test_download_requires_admin(self) -> None:
        self.send()
        report = MonitoringReport.objects.get()
        url = reverse(
            "admin:monitoring_monitoringreport_download", args=(report.report_id,)
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.create_superuser(
            username="synthetic-admin", password="synthetic-test-password"
        )
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content), report.storage_path.read_bytes()
        )

    def test_agent_form_rejects_reused_token(self) -> None:
        server = Server.objects.create(name="synthetic-other", ip_address="192.0.2.20")
        form = MonitoringAgentForm(data={
            "server": server.pk, "site_id": "sdm-test", "agent_id": "pollux",
            "enabled": True, "api_token": TOKEN,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("api_token", form.errors)

    def test_retry_restores_missing_file(self) -> None:
        data = payload()
        self.assertEqual(self.send(data).status_code, 201)
        report = MonitoringReport.objects.get()
        report.storage_path.unlink()
        self.assertEqual(self.send(data).status_code, 200)
        self.assertEqual(json.loads(report.storage_path.read_bytes()), data)
        self.assertEqual(MonitoringReport.objects.count(), 1)
    def test_token_widget_has_visible_unfold_styling(self) -> None:
        form = MonitoringAgentForm()
        html = str(form["api_token"])
        self.assertIn('type="password"', html)
        self.assertIn('name="api_token"', html)
        self.assertIn("border-base-200", html)
        self.assertIn("px-3", html)
        self.assertIn("w-full", html)
        self.assertIn('autocomplete="new-password"', html)
        bound = MonitoringAgentForm(data={"api_token": TOKEN})
        self.assertNotIn(TOKEN, str(bound["api_token"]))

    def test_agent_admin_page_renders_token_input(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="synthetic-form-admin", password="synthetic-test-password"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("admin:monitoring_monitoringagent_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="api_token"')
        self.assertContains(response, 'id="id_api_token"')
        self.assertContains(response, "Вставьте новый токен агента")

    def test_invalid_report_names_field_without_echoing_value(self) -> None:
        data = payload()
        data["checks"][0]["enabled"] = "synthetic-sensitive-value"
        response = self.send(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            "accepted": False, "error": "invalid_report",
            "field": "checks.enabled",
        })
        self.assertNotContains(
            response, "synthetic-sensitive-value", status_code=400
        )

    def test_invalid_schema_names_field(self) -> None:
        data = payload()
        data["schema_version"] = 99
        response = self.send(data)
        self.assertEqual(response.json()["field"], "schema_version")

    def test_missing_result_value_names_field(self) -> None:
        data = payload()
        data["checks"][0]["results"][0].pop("value")
        response = self.send(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "checks.results.value")

    def test_archives_queued_disabled_block_with_empty_type(self) -> None:
        data = payload()
        data["checks"][0].update(
            type="", enabled=False, results=[], error=None,
        )
        response = self.send(data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            json.loads(MonitoringReport.objects.get().storage_path.read_bytes()),
            data,
        )

    def test_empty_type_is_rejected_for_enabled_check(self) -> None:
        data = payload()
        data["checks"][0].update(type="", enabled=True, results=[])
        response = self.send(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "checks.type")

    def test_empty_type_placeholder_cannot_contain_data_or_error(self) -> None:
        for changes in (
            {"results": [{"target": "/reports", "value": 0, "details": {}}]},
            {"error": "check_timeout"},
        ):
            data = payload()
            data["checks"][0].update(
                type="", enabled=False, results=[], error=None,
            )
            data["checks"][0].update(changes)
            self.assertEqual(self.send(data).status_code, 400)

    def test_unknown_named_type_remains_invalid_when_disabled(self) -> None:
        data = payload()
        data["checks"][0].update(
            type="unsupported-type", enabled=False, results=[], error=None,
        )
        response = self.send(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "checks.type")
