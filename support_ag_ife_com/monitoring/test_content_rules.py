from importlib import import_module
from types import SimpleNamespace
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.test import TestCase
from django.urls import reverse

from .mail_templates import render_notification
from .models import ContentRule, MonitoringAgent, Server


class ContentRuleTests(TestCase):
    def setUp(self) -> None:
        server = Server.objects.create(name="Synthetic pollux", ip_address="192.0.2.12")
        self.agent = MonitoringAgent.objects.create(
            server=server, site_id="sdm-test", agent_id="pollux",
        )

    def make_rule(self, **overrides: Any) -> ContentRule:
        values = {
            "agent": self.agent, "name": "Профили",
            "check_id": "DATA_CREWID", "stream_id": "DIR",
            "silence_limit_minutes": 2880,
        }
        return ContentRule(**{**values, **overrides})

    def login_admin(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="content-rule-admin", password="synthetic-password",
        )
        self.client.force_login(user)

    def test_rule_accepts_minutes_and_custom_stream(self) -> None:
        rule = self.make_rule(stream_id="MAIN", silence_limit_minutes=180)
        rule.full_clean()
        rule.save()
        self.assertEqual(ContentRule.objects.get().silence_limit_minutes, 180)

    def test_zero_negative_and_non_integer_limits_are_invalid(self) -> None:
        form_type = modelform_factory(ContentRule, fields="__all__")
        for value in ("0", "-5", "1.5", "not-a-number"):
            with self.subTest(value=value):
                form = form_type(data={
                    "agent": self.agent.pk, "name": "Профили",
                    "check_id": "DATA_CREWID", "stream_id": "DIR",
                    "silence_limit_minutes": value, "enabled": "on",
                })
                self.assertFalse(form.is_valid())
                self.assertIn("silence_limit_minutes", form.errors)

    def test_duplicate_rule_for_same_agent_and_stream_is_rejected(self) -> None:
        self.make_rule().save()
        with self.assertRaises(ValidationError):
            self.make_rule(silence_limit_minutes=120).full_clean()

    def test_other_agent_can_use_its_own_threshold(self) -> None:
        self.make_rule().save()
        server = Server.objects.create(name="Synthetic kif", ip_address="192.0.2.13")
        agent = MonitoringAgent.objects.create(
            server=server, site_id="afl-test", agent_id="kif",
        )
        rule = self.make_rule(agent=agent, silence_limit_minutes=15)
        rule.full_clean()
        rule.save()
        self.assertEqual(ContentRule.objects.count(), 2)

    def test_admin_can_add_and_edit_rule(self) -> None:
        self.login_admin()
        values = {
            "agent": self.agent.pk, "name": "Экипаж",
            "check_id": "DATA_CREWLIST", "stream_id": "DIR",
            "silence_limit_minutes": "180", "enabled": "on",
        }
        url = reverse("admin:monitoring_contentrule_add")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, values).status_code, 302)
        rule = ContentRule.objects.get()
        values["silence_limit_minutes"] = "120"
        values.pop("enabled")
        url = reverse("admin:monitoring_contentrule_change", args=(rule.pk,))
        self.assertEqual(self.client.post(url, values).status_code, 302)
        rule.refresh_from_db()
        self.assertEqual(rule.silence_limit_minutes, 120)
        self.assertFalse(rule.enabled)

    def test_view_only_user_cannot_change_rule(self) -> None:
        rule = self.make_rule()
        rule.save()
        user = get_user_model().objects.create_user(
            username="rule-reader", is_staff=True,
        )
        user.user_permissions.add(Permission.objects.get(codename="view_contentrule"))
        self.client.force_login(user)
        url = reverse("admin:monitoring_contentrule_change", args=(rule.pk,))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_pollux_defaults_are_created_without_overwriting_changes(self) -> None:
        migration = import_module("monitoring.migrations.0007_pollux_content_rules")
        editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        migration.seed_pollux_rules(apps, editor)
        expected = {
            "DATA_CREWID": 2880, "DATA_CREWLIST": 180, "DATA_PAXPNL": 120,
            "DATA_PAXPRL": 120, "DATA_XML4OPS": 120,
        }
        self.assertEqual(
            dict(ContentRule.objects.filter(agent=self.agent).values_list(
                "check_id", "silence_limit_minutes",
            )),
            expected,
        )
        ContentRule.objects.filter(check_id="DATA_CREWID").update(
            silence_limit_minutes=3000,
        )
        migration.seed_pollux_rules(apps, editor)
        self.assertEqual(ContentRule.objects.count(), 5)
        self.assertEqual(
            ContentRule.objects.get(check_id="DATA_CREWID").silence_limit_minutes,
            3000,
        )

    def test_silence_limit_is_available_in_content_mail_template(self) -> None:
        from .models import MailTemplate

        template = MailTemplate.objects.get(category="content")
        template.problem_body = "{silence_minutes} / {silence_limit_minutes}"
        template.full_clean()
        template.save()
        _, body = render_notification("content", "problem", {
            "silence_minutes": 181, "silence_limit_minutes": 180,
        })
        self.assertEqual(body, "181 / 180")
