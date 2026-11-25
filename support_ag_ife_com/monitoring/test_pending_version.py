import ast
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .mail_templates import render_notification
from .models import MailTemplate
from .presentation import server_indicator


class ContentErrorTemplateTests(TestCase):
    def test_silence_and_error_templates_are_independent(self) -> None:
        template = MailTemplate.objects.get(category="content")
        template.problem_subject = "Тишина: {stream_name}"
        template.error_subject = "Ошибки: {stream_name}"
        template.error_body = "{error_count}: {error_files}"
        template.error_recovery_subject = "Ошибки устранены: {stream_name}"
        template.error_recovery_body = "{events}"
        template.full_clean()
        template.save()
        context = {
            "stream_name": "Профили", "error_count": 3,
            "error_files": "one.err", "events": "Каталог очищен",
        }
        self.assertEqual(
            render_notification("content", "problem", context)[0],
            "Тишина: Профили",
        )
        self.assertEqual(
            render_notification("content", "error", context),
            ("Ошибки: Профили", "3: one.err"),
        )
        self.assertEqual(
            render_notification("content", "error_recovery", context),
            ("Ошибки устранены: Профили", "Каталог очищен"),
        )
        self.assertEqual(
            MailTemplate.objects.get(category="content").problem_subject,
            "Тишина: {stream_name}",
        )

    def test_error_templates_have_same_validation(self) -> None:
        template = MailTemplate.objects.get(category="content")
        template.error_body = "{server_name.__class__}"
        with self.assertRaises(ValidationError):
            template.full_clean()
        with self.assertRaises(ValueError):
            render_notification("network", "error", {})

    def test_migration_preserves_custom_templates(self) -> None:
        template = MailTemplate.objects.get(category="content")
        template.problem_subject = "Моя тишина"
        template.error_subject = "Мои ошибки"
        template.save()
        migration = import_module("monitoring.migrations.0009_content_template_defaults")
        migration.populate_content_templates(
            apps, SimpleNamespace(connection=SimpleNamespace(alias="default")),
        )
        template.refresh_from_db()
        self.assertEqual(template.problem_subject, "Моя тишина")
        self.assertEqual(template.error_subject, "Мои ошибки")

    def test_content_admin_has_four_event_sections(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="content-template-admin", password="synthetic-password",
        )
        self.client.force_login(user)
        template = MailTemplate.objects.get(category="content")
        response = self.client.get(reverse(
            "admin:monitoring_mailtemplate_change", args=(template.pk,),
        ))
        for text in (
            "Данные не поступают", "Поступление данных восстановлено",
            "Обнаружены ошибки .err", "Ошибки .err устранены",
            'name="error_subject"', 'name="error_recovery_body"',
        ):
            self.assertContains(response, text)


class SidebarConfigurationTests(SimpleTestCase):
    def test_requested_groups_are_collapsible(self) -> None:
        settings_path = Path(__file__).parents[1] / "support_ag_ife_com/settings.py"
        tree = ast.parse(settings_path.read_text(encoding="utf-8-sig"))
        groups = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            fields = {
                key.value: value for key, value in zip(node.keys, node.values)
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if "title" not in fields or "items" not in fields:
                continue
            title = ast.literal_eval(fields["title"])
            groups[title] = ast.literal_eval(fields.get("collapsible", ast.Constant(False)))
        for title in (
            "Мониторинг", "Проверка знаний",
            "Сотрудники и регистрация пользователей",
        ):
            self.assertTrue(groups[title], title)

    def test_existing_errors_remain_red_without_new_errors_in_period(self) -> None:
        server = {
            "agent": {"enabled": True},
            "report": {"checks": [{
                "enabled": True, "type": "content", "results": [{
                    "details": {"err_count": 0, "err_total_count": 2},
                }],
            }]},
        }
        self.assertEqual(server_indicator(server, 90)["kind"], "bad")

    def test_new_agent_metrics_survive_api_validation_and_normalization(self) -> None:
        from .dashboard import normalize_check
        from .tests import payload
        from .validation import validate_report

        data = payload()
        check = data["checks"][0]
        check.update(check_id="DATA_CREWID", type="content")
        details = {
            "directory": "/synthetic",
            "last_normal_file": "normal.xml",
            "last_normal_time": "2026-11-25T10:00:00Z",
            "err_count": 0, "err_total_count": 2,
            "err_latest_files": [{
                "path": "old.err", "modified_at": "2026-11-24T10:00:00Z",
            }],
        }
        check["results"] = [{
            "target": "DIR", "value": 0, "error": None, "details": details,
        }]
        validate_report(data)
        self.assertEqual(normalize_check(check)["results"][0]["details"], details)
