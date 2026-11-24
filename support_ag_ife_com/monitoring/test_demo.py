from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .demo import build_demo_dashboard
from .test_dashboard import PAGE_TEMPLATES


class DemoDashboardTests(TestCase):
    def test_demo_uses_no_database_queries(self) -> None:
        with self.assertNumQueries(0):
            dashboard = build_demo_dashboard()
        self.assertTrue(dashboard["demo"])
        self.assertEqual(len(dashboard["servers"]), 4)
        for server in dashboard["servers"]:
            self.assertIn("+00:00", server["report"]["checked_at"])
            self.assertEqual(
                {check["type"] for check in server["report"]["checks"]},
                {"network", "memory", "report", "content"},
            )

    def test_demo_requires_authentication(self) -> None:
        response = self.client.get(reverse("monitoring:data"), {"demo": "1"})
        self.assertEqual(response.status_code, 401)

    @override_settings(TEMPLATES=PAGE_TEMPLATES)
    def test_demo_page_and_data_are_isolated(self) -> None:
        user = get_user_model().objects.create_user(username="demo-reader")
        self.client.force_login(user)
        with patch("monitoring.views.build_dashboard") as real_dashboard:
            page = self.client.get(reverse("monitoring:index"), {"demo": "1"})
            self.assertContains(page, '/monitoring/data/?demo=1')
            self.assertContains(page, "Тестовые данные")
            self.assertNotContains(page, "monUpdated")
            self.assertNotContains(page, "monModalMeta")
            response = self.client.get(reverse("monitoring:data"), {"demo": "1"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertTrue(response.json()["demo"])
            real_dashboard.assert_not_called()

    def test_real_mode_keeps_real_data_source(self) -> None:
        user = get_user_model().objects.create_user(username="real-reader")
        self.client.force_login(user)
        with patch("monitoring.views.build_dashboard", return_value={"servers": []}) as real:
            response = self.client.get(reverse("monitoring:data"))
            self.assertEqual(response.json(), {"servers": []})
            real.assert_called_once_with()
