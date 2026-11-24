import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from django.db.models import OuterRef, Subquery
from django.utils import timezone as django_timezone

from .thresholds import disk_limit
from .api import MAX_BODY_BYTES
from .models import MonitoringAgent, MonitoringReport, Server

log = logging.getLogger(__name__)


def iso_time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def legacy_results(check: dict[str, Any]) -> list[dict[str, Any]]:
    measurements = check.get("measurements", {})
    check_type = check.get("type")
    results = []
    if check_type in ("ping", "telnet"):
        for target in measurements.get("targets", []):
            name = (
                target["host"] if "host" in target
                else f"{target.get('ip')}:{target.get('port')}"
            )
            results.append({
                "target": name, "reachable": target.get("reachable"),
                "error": target.get("error"), "details": target,
            })
    elif check_type == "report":
        for directory, count in measurements.get("counts", {}).items():
            results.append({
                "target": directory, "value": count, "details": {},
            })
    elif check_type == "memory":
        for disk in measurements.get("disks", []):
            results.append({
                "target": disk["mount"], "value": disk["percent"],
                "details": disk,
            })
        if not results:
            for target, percent in measurements.get("usage", {}).items():
                results.append({
                    "target": target, "value": percent, "details": {},
                })
    elif check_type == "content":
        for stream, data in measurements.get("streams", {}).items():
            details = dict(data)
            if "last_time" not in details and data.get("last") is not None:
                details["last_time"] = datetime.fromtimestamp(
                    float(data["last"]), timezone.utc
                ).isoformat()
            results.append({
                "target": stream, "value": data.get("count", data.get("recent", 0)),
                "details": details,
            })
    return results


def normalize_check(check: dict[str, Any]) -> dict[str, Any]:
    enabled = check.get("enabled", check.get("status") != "disabled")
    results = []
    source = check.get("results")
    if source is None:
        source = legacy_results(check)
    for item in source:
        details = item.get("details") or {}
        error = item.get("error") or details.get("error")
        if item.get("status") == "error" and not error:
            error = "collection_error"
        result = {
            "target": item.get("target", ""),
            "value": item.get("value"),
            "error": error,
            "enabled": item.get("enabled", enabled),
            "details": {
                key: details[key]
                for key in (
                    "check_id", "name", "group", "method", "host", "ip", "port",
                    "started_at", "finished_at", "output", "device",
                    "size_gb", "used_gb", "avail_gb", "directory", "last_file",
                    "last_time", "err_count", "err_files",
                )
                if key in details
            },
        }
        if "reachable" in item:
            result["reachable"] = item["reachable"]
        elif check.get("type") in ("network", "ping", "telnet"):
            result["reachable"] = (
                item.get("value") if type(item.get("value")) is bool else None
            )
        results.append(result)
    return {
        "check_id": check.get("check_id"),
        "name": check.get("name"),
        "type": check.get("type"),
        "enabled": enabled,
        "started_at": check.get("started_at"),
        "finished_at": check.get("finished_at"),
        "duration_ms": check.get("duration_ms"),
        "error": check.get("error"),
        "results": results,
    }


def read_snapshot(report: MonitoringReport) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "report_id": str(report.report_id),
        "schema_version": report.schema_version,
        "stream_id": str(report.stream_id),
        "sequence": report.sequence,
        "checked_at": iso_time(report.finished_at),
        "received_at": iso_time(report.received_at),
        "interval_minutes": None,
        "checks": [],
        "error": None,
    }
    try:
        with report.storage_path.open("rb") as stream:
            body = stream.read(MAX_BODY_BYTES + 1)
        if (
            len(body) != report.size_bytes
            or hashlib.sha256(body).hexdigest() != report.sha256
        ):
            snapshot["error"] = "file_invalid"
            return snapshot
        data = json.loads(body)
        snapshot["checks"] = [
            normalize_check(check) for check in data["checks"]
        ]
        snapshot["interval_minutes"] = data["interval_seconds"] / 60
    except FileNotFoundError:
        snapshot["error"] = "file_missing"
    except PermissionError:
        snapshot["error"] = "file_unreadable"
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        snapshot["error"] = "file_invalid"
    if snapshot["error"]:
        log.warning(
            "Monitoring snapshot unavailable: report_id=%s error=%s",
            report.report_id, snapshot["error"],
        )
    return snapshot


def build_dashboard() -> dict[str, Any]:
    latest = MonitoringReport.objects.filter(
        agent_id=OuterRef("pk")
    ).order_by("-finished_at", "-sequence", "-received_at")
    agents = list(MonitoringAgent.objects.annotate(
        latest_report_pk=Subquery(latest.values("report_id")[:1])
    ))
    reports = {
        report.pk: report for report in MonitoringReport.objects.filter(
            report_id__in=[
                agent.latest_report_pk for agent in agents
                if agent.latest_report_pk is not None
            ]
        )
    }
    by_server = {agent.server_id: agent for agent in agents}
    servers = []
    for server in Server.objects.all():
        agent = by_server.get(server.pk)
        report = reports.get(agent.latest_report_pk) if agent else None
        servers.append({
            "id": server.pk,
            "name": server.name,
            "ip_address": server.ip_address,
            "agent": {
                "site_id": agent.site_id,
                "agent_id": agent.agent_id,
                "enabled": agent.enabled,
                "last_seen_at": iso_time(agent.last_seen_at),
            } if agent else None,
            "report": read_snapshot(report) if report else None,
        })
    return {
        "generated_at": iso_time(django_timezone.now()),
        "disk_limit": disk_limit(),
        "servers": servers,
    }
