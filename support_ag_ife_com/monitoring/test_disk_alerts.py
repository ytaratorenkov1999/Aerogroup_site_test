import json
import smtplib
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    AlertNotification, AlertRecipient, DiskAlertState, MonitoringAgent, Server,
)
from .notifications import dispatch_notifications, recipient_addresses
from .tests import TOKEN, payload
from .thresholds import disk_limit


@override_settings(
    LIMIT_DISK=90,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="monitoring@example.test",
    MAIL_FROM_NAME="AG-Monitoring",
)
class DiskAlertTests(TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="monitoring-alerts-")
        self.addCleanup(temp.cleanup)
        override = override_settings(MONITORING_REPORTS_ROOT=Path(temp.name))
        override.enable()
        self.addCleanup(override.disable)
        server = Server.objects.create(name="Synthetic server", ip_address="192.0.2.13")
        self.agent = MonitoringAgent(
            server=server, site_id="afl-test", agent_id="kif", enabled=True,
        )
        self.agent.set_api_token(TOKEN)
        self.agent.save()
        self.recipient = AlertRecipient.objects.create(email="one@example.test")
        self.sequence = 0
        self.now = timezone.now()
        mail.get_connection()
        mail.outbox.clear()

    def report(self, percent: Any, age: int = 0) -> dict[str, Any]:
        self.sequence += 1
        data = payload()
        finished = self.now + timedelta(seconds=age)
        data.update({
            "sequence": self.sequence,
            "started_at": (finished - timedelta(seconds=2)).isoformat(),
            "finished_at": finished.isoformat(),
        })
        data["checks"] = [{
            "check_id": "DISK", "type": "memory", "enabled": True,
            "started_at": data["started_at"], "finished_at": data["finished_at"],
            "error": None, "results": [{
                "target": "/", "value": percent, "error": None, "details": {},
            }],
        }]
        return data

    def send(self, data: dict[str, Any]) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/monitoring/v1/reports/",
                data=json.dumps(data), content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
            )
        self.assertIn(response.status_code, (200, 201))

    def test_boundary_crossing_and_recovery_notify_once(self) -> None:
        self.send(self.report(85))
        self.assertEqual(len(mail.outbox), 0)
        self.send(self.report(90, 1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Раздел: / — 90% (лимит 90%).", mail.outbox[0].body)
        self.send(self.report(95, 2))
        self.assertEqual(len(mail.outbox), 1)
        self.send(self.report(89, 3))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Раздел: / — 89% (лимит 90%).", mail.outbox[1].body)
        self.assertIn("восстановление", mail.outbox[1].subject)
        self.send(self.report(80, 4))
        self.assertEqual(len(mail.outbox), 2)

    def test_first_critical_report_and_duplicate(self) -> None:
        data = self.report(91)
        self.send(data)
        self.send(data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(AlertNotification.objects.count(), 1)
        self.assertIsNotNone(AlertNotification.objects.get().sent_at)

    def test_only_enabled_admin_recipients_receive_mail(self) -> None:
        self.recipient.delete()
        AlertRecipient.objects.create(email="admin@example.test")
        AlertRecipient.objects.create(email="disabled@example.test", enabled=False)
        self.send(self.report(90))
        self.assertEqual(mail.outbox[0].bcc, ["admin@example.test"])
        self.assertEqual(mail.outbox[0].from_email, "AG-Monitoring <monitoring@example.test>")
        self.assertEqual(mail.outbox[0].to, [])

    def test_admin_recipients_are_deduplicated(self) -> None:
        AlertRecipient.objects.create(email="ONE@example.test")
        AlertRecipient.objects.create(email="two@example.test")
        addresses = recipient_addresses()
        self.assertEqual(len(addresses), 2)
        self.assertEqual(
            {address.casefold() for address in addresses},
            {"one@example.test", "two@example.test"},
        )

    def test_disabling_all_admin_recipients_stops_delivery(self) -> None:
        self.recipient.delete()
        recipient = AlertRecipient.objects.create(
            email="disabled@example.test", enabled=False,
        )
        self.send(self.report(90))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(AlertNotification.objects.get().sent_at)
        recipient.enabled = True
        recipient.save()
        dispatch_notifications(self.agent.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_failure_remains_pending_and_retries_on_duplicate(self) -> None:
        data = self.report(90)
        with patch(
            "monitoring.notifications.EmailMessage.send",
            side_effect=smtplib.SMTPException("synthetic_failure"),
        ):
            self.send(data)
        event = AlertNotification.objects.get()
        self.assertIsNone(event.sent_at)
        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.last_error, "smtp_error")
        self.send(data)
        event.refresh_from_db()
        self.assertIsNotNone(event.sent_at)
        self.assertEqual(event.attempts, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_missing_recipients_retains_notification(self) -> None:
        self.recipient.delete()
        with override_settings(ALLERT_MAIL_REICERVERS="ignored@example.test"):
            self.send(self.report(90))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(AlertNotification.objects.get().sent_at)

    def test_old_backlog_does_not_send_alert(self) -> None:
        self.send(self.report(99, -3600))
        self.assertEqual(AlertNotification.objects.count(), 0)
        self.assertEqual(DiskAlertState.objects.count(), 0)

    def test_out_of_order_report_does_not_recover_critical_disk(self) -> None:
        self.send(self.report(95, 60))
        self.send(self.report(20))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(DiskAlertState.objects.get().critical)

    def test_disabled_and_failed_measurements_do_not_recover(self) -> None:
        self.send(self.report(95))
        for index, variant in enumerate(("disabled", "failed", "invalid"), 1):
            data = self.report(20, index)
            check = data["checks"][0]
            if variant == "disabled":
                check["enabled"] = False
            elif variant == "failed":
                check["results"][0]["error"] = "read_error"
            else:
                check["results"][0]["value"] = True
            self.send(data)
        self.assertTrue(DiskAlertState.objects.get().critical)
        self.assertEqual(len(mail.outbox), 1)

    def test_multiple_disks_are_batched_in_one_notification(self) -> None:
        data = self.report(90)
        data["checks"][0]["results"].append({
            "target": "/var", "value": 99, "error": None, "details": {},
        })
        self.send(data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/var", mail.outbox[0].body)
        self.assertIn("UTC", mail.outbox[0].body)

    def test_configured_limit_is_used(self) -> None:
        with override_settings(LIMIT_DISK=75):
            self.send(self.report(75))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("лимит 75%", mail.outbox[0].body)

    def test_threshold_configuration_validation(self) -> None:
        for value in (0, -1, 101, float("nan"), float("inf"), "invalid"):
            with self.subTest(value=value), override_settings(LIMIT_DISK=value):
                with self.assertRaises(ImproperlyConfigured):
                    disk_limit()

    def test_recipient_admin_page(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="alert-admin", password="synthetic-password",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("admin:monitoring_alertrecipient_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
