from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .mail_templates import render_notification
from .models import MailTemplate
from . import test_disk_alerts


class MailTemplateTests(TestCase):
    def test_three_categories_are_ready(self) -> None:
        self.assertEqual(
            set(MailTemplate.objects.values_list("category", flat=True)),
            {"disk", "content", "network"},
        )

    def test_invalid_placeholders_cannot_be_saved_in_admin(self) -> None:
        template = MailTemplate.objects.get(category="disk")
        for value in (
            "{unknown}", "{server_name.__class__}", "{server_name[0]}",
            "{server_name!r}", "{server_name:10000}", "{", "",
        ):
            with self.subTest(value=value):
                template.problem_body = value
                with self.assertRaises(ValidationError):
                    template.full_clean()

    def test_subject_rejects_line_breaks(self) -> None:
        template = MailTemplate.objects.get(category="disk")
        template.problem_subject = "Subject\nBcc: synthetic@example.test"
        with self.assertRaises(ValidationError):
            template.full_clean()

    def test_substitution_does_not_evaluate_context(self) -> None:
        template = MailTemplate.objects.get(category="disk")
        template.problem_subject = "{server_name}"
        template.problem_body = "Сервер: {server_name}; {{скобки}}"
        template.save()
        subject, body = render_notification(
            "disk", "problem", {"server_name": "{events}"},
        )
        self.assertEqual(subject, "{events}")
        self.assertEqual(body, "Сервер: {events}; {скобки}")

    def test_invalid_stored_template_uses_safe_default(self) -> None:
        MailTemplate.objects.filter(category="disk").update(
            problem_body="{unknown}",
        )
        subject, body = render_notification(
            "disk", "problem", {"server_name": "Synthetic", "events": "90%"},
        )
        self.assertIn("дисков", subject)
        self.assertIn("90%", body)
        self.assertNotIn("{unknown}", body)

    def test_content_and_network_templates_render_independently(self) -> None:
        for category, extra in (
            ("content", {"directory": "/synthetic", "error_count": 2}),
            ("network", {"target": "192.0.2.1", "port": 443}),
        ):
            template = MailTemplate.objects.get(category=category)
            template.problem_body = " | ".join("{" + key + "}" for key in extra)
            template.full_clean()
            template.save()
            _, body = render_notification(category, "problem", extra)
            self.assertEqual(body, " | ".join(str(value) for value in extra.values()))

    def test_admin_has_sections_and_variable_help(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="template-admin", password="synthetic-password",
        )
        self.client.force_login(user)
        template = MailTemplate.objects.get(category="disk")
        response = self.client.get(reverse(
            "admin:monitoring_mailtemplate_change", args=(template.pk,),
        ))
        self.assertEqual(response.status_code, 200)
        for text in ("Проблема", "Восстановление", "{server_name}", "{limit}"):
            self.assertContains(response, text)
        response = self.client.get(reverse("admin:monitoring_mailtemplate_changelist"))
        for text in ("Диск", "Контент", "Сетевая связность"):
            self.assertContains(response, text)


@override_settings(
    LIMIT_DISK=90,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="monitoring@example.test",
    MAIL_FROM_NAME="AG-Monitoring",
)
class DiskTemplateIntegrationTests(TestCase):
    setUp = test_disk_alerts.DiskAlertTests.setUp
    report = test_disk_alerts.DiskAlertTests.report
    send = test_disk_alerts.DiskAlertTests.send

    def test_disk_problem_and_recovery_use_edited_templates(self) -> None:
        template = MailTemplate.objects.get(category="disk")
        template.problem_subject = "Диск: {server_name}"
        template.problem_body = "{events}\nПорог: {limit}"
        template.recovery_subject = "Восстановлено: {site_id}"
        template.recovery_body = "Готово: {events}"
        template.full_clean()
        template.save()
        self.send(self.report(90))
        self.assertEqual(mail.outbox[0].subject, "Диск: Synthetic server")
        self.assertIn("Порог: 90", mail.outbox[0].body)
        self.send(self.report(80, 1))
        self.assertEqual(mail.outbox[1].subject, "Восстановлено: afl-test")
        self.assertTrue(mail.outbox[1].body.startswith("Готово: "))

    def test_pending_events_keep_their_individual_subjects(self) -> None:
        self.recipient.enabled = False
        self.recipient.save()
        self.send(self.report(90))
        self.send(self.report(80, 1))
        self.recipient.enabled = True
        self.recipient.save()
        self.send(self.report(80, 2))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("состояние дисков", mail.outbox[0].subject)
        self.assertIn("восстановление", mail.outbox[1].subject)
