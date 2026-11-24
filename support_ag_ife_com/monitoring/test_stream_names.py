from typing import Any

from django.test import SimpleTestCase

from .dashboard import normalize_check
from .tests import payload
from .validation import ReportValidationError, validate_report


class StreamNameTests(SimpleTestCase):
    def test_name_survives_report_validation_and_dashboard(self) -> None:
        data = payload()
        check = data["checks"][0]
        check.update({"check_id": "NETWORK", "type": "network", "name": "Сеть"})
        check["results"] = [{
            "target": "192.0.2.1:1518", "reachable": True, "error": None,
            "details": {
                "check_id": "NETWORK_CUSTOM_QUEUE",
                "name": "Пользовательская очередь заказчика",
                "group": "customer", "port": 1518,
            },
        }]
        validate_report(data)
        normalized = normalize_check(check)
        self.assertEqual(normalized["name"], "Сеть")
        self.assertEqual(
            normalized["results"][0]["details"]["name"],
            "Пользовательская очередь заказчика",
        )

    def test_old_reports_without_name_remain_valid(self) -> None:
        data = payload()
        validate_report(data)
        check = normalize_check(data["checks"][0])
        self.assertIsNone(check["name"])
        self.assertNotIn("name", check["results"][0]["details"])

    def test_invalid_names_are_rejected_with_safe_field(self) -> None:
        for value in (None, 42, [], {}, "x" * 513):
            for location in ("check", "details"):
                with self.subTest(value=type(value).__name__, location=location):
                    data: dict[str, Any] = payload()
                    check = data["checks"][0]
                    if location == "check":
                        check["name"] = value
                        expected = "checks.name"
                    else:
                        check["results"][0]["details"]["name"] = value
                        expected = "checks.results.details.name"
                    with self.assertRaises(ReportValidationError) as caught:
                        validate_report(data)
                    self.assertEqual(caught.exception.field, expected)
