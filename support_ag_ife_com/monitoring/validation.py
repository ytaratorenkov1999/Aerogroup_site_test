import math
import re
from datetime import datetime
from typing import Any, NoReturn
from uuid import UUID

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware


class ReportValidationError(ValueError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__("invalid_report")


def fail(field: str) -> NoReturn:
    raise ReportValidationError(field)


def identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[-a-zA-Z0-9_]{1,100}", value
    ):
        fail(field)
    return value


def moment(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        fail(field)
    try:
        parsed = parse_datetime(value)
    except ValueError:
        fail(field)
    if parsed is None or not is_aware(parsed):
        fail(field)
    return parsed


def uuid_value(value: Any, field: str) -> UUID:
    if not isinstance(value, str):
        fail(field)
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        fail(field)


def positive_int(value: Any, field: str) -> int:
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        fail(field)
    return value


def validate_report(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        fail("report")
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        fail("schema_version")
    report_id = uuid_value(data.get("report_id"), "report_id")
    stream_id = uuid_value(data.get("stream_id"), "stream_id")
    site_id = identifier(data.get("site_id"), "site_id")
    agent_id = identifier(data.get("agent_id"), "agent_id")
    sequence = positive_int(data.get("sequence"), "sequence")
    started = moment(data.get("started_at"), "started_at")
    finished = moment(data.get("finished_at"), "finished_at")
    if finished < started:
        fail("finished_at")
    interval = data.get("interval_seconds")
    if (
        type(interval) not in (int, float) or not math.isfinite(interval)
        or interval <= 0
    ):
        fail("interval_seconds")
    moment(data.get("next_cycle_due_at"), "next_cycle_due_at")
    checks = data.get("checks")
    if not isinstance(checks, list) or len(checks) > 1000:
        fail("checks")
    count = 0
    check_ids: set[str] = set()
    forbidden = {"status", "problems", "diagnostics"}
    if version == 2 and forbidden.intersection(data):
        fail("removed_fields")
    for check in checks:
        if not isinstance(check, dict):
            fail("checks")
        if "name" in check and (
            not isinstance(check["name"], str) or len(check["name"]) > 512
        ):
            fail("checks.name")
        check_id = identifier(check.get("check_id"), "checks.check_id")
        if check_id in check_ids:
            fail("checks.check_id")
        check_ids.add(check_id)
        disabled_placeholder = (
            version == 2
            and check.get("type") == ""
            and check.get("enabled") is False
            and check.get("results") == []
            and check.get("error") is None
        )
        if check.get("type") not in (
            "network", "ping", "telnet", "memory", "content", "report",
        ) and not disabled_placeholder:
            fail("checks.type")
        check_started = moment(check.get("started_at"), "checks.started_at")
        check_finished = moment(check.get("finished_at"), "checks.finished_at")
        if check_finished < check_started:
            fail("checks.finished_at")
        if version == 2:
            if type(check.get("enabled")) is not bool:
                fail("checks.enabled")
            if forbidden.intersection(check):
                fail("checks.removed_fields")
        error = check.get("error")
        if error is not None and (not isinstance(error, str) or len(error) > 512):
            fail("checks.error")
        results = check.get("results")
        if version == 1 and results is None:
            if not isinstance(check.get("measurements"), dict):
                fail("checks.measurements")
            continue
        if not isinstance(results, list):
            fail("checks.results")
        count += len(results)
        if count > 20000:
            fail("checks.results")
        for result in results:
            if not isinstance(result, dict):
                fail("checks.results")
            if (
                not isinstance(result.get("target"), str)
                or len(result["target"]) > 4096
            ):
                fail("checks.results.target")
            if not isinstance(result.get("details"), dict):
                fail("checks.results.details")
            details = result["details"]
            if "name" in details and (
                not isinstance(details["name"], str) or len(details["name"]) > 512
            ):
                fail("checks.results.details.name")
            if version == 2:
                if forbidden.intersection(result):
                    fail("checks.results.removed_fields")
                result_error = result.get("error")
                if result_error is not None and not isinstance(result_error, str):
                    fail("checks.results.error")
                if "reachable" in result:
                    if (
                        result["reachable"] is not None
                        and type(result["reachable"]) is not bool
                    ):
                        fail("checks.results.reachable")
                elif "value" not in result:
                    fail("checks.results.value")
    return {
        "report_id": report_id, "stream_id": stream_id,
        "site_id": site_id, "agent_id": agent_id,
        "schema_version": version, "sequence": sequence,
        "started_at": started, "finished_at": finished,
    }
