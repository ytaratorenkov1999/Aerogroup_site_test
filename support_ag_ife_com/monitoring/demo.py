"""Synthetic dashboard snapshots; no database or filesystem access."""

from datetime import UTC, datetime, timedelta
from typing import Any

from .thresholds import disk_limit


def build_demo_dashboard() -> dict[str, Any]:
    now = datetime.now(UTC)
    checked = (now - timedelta(minutes=1)).isoformat()
    last_file_time = (now - timedelta(minutes=7)).isoformat()

    def result(
        target: str, value: int | float | None,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "target": target, "value": value, "enabled": True,
            "error": error, "details": details or {},
        }

    def check(
        check_id: str, kind: str, results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "check_id": check_id, "type": kind, "enabled": True,
            "started_at": checked, "finished_at": checked,
            "duration_ms": 120, "error": None, "results": results,
        }

    servers: list[dict[str, Any]] = []
    for index, machine in enumerate(("calculon", "castor", "pollux", "kif"), 1):
        network = []
        stream_names = {
            "NETWORK_PLATFORM": "Серверы площадки",
            "NETWORK_CREW": "Экипаж",
            "NETWORK_PAX": "Пассажиры",
            "NETWORK_MQ_TEST": "MQ TEST",
            "NETWORK_MAIL": "Почта",
        }
        for stream, group, address, port, reachable in (
            ("NETWORK_PLATFORM", "platform", f"192.0.2.{index}", None, True),
            ("NETWORK_CREW", "customer", "198.51.100.20", 443, True),
            ("NETWORK_PAX", "customer", "198.51.100.21", 443, index != 3),
            ("NETWORK_MQ_TEST", "customer", "198.51.100.22", 1518, index != 4),
            ("NETWORK_MAIL", "customer", "198.51.100.23", 25, True),
        ):
            details: dict[str, Any] = {
                "check_id": stream, "name": stream_names[stream],
                "group": group, "ip": address,
                "method": "telnet" if port else "ping",
                "finished_at": checked,
            }
            if port:
                details["port"] = port
            else:
                details["output"] = "3 packets transmitted, 3 received, 0% packet loss"
            item = result(
                f"{address}:{port}" if port else address, int(reachable),
                details, None if reachable else "connection_timeout",
            )
            item["reachable"] = reachable
            network.append(item)
        checks = [
            check("NETWORK", "network", network),
            check("DISK", "memory", [
                result("/", (max(0, disk_limit() - 8), max(0, disk_limit() - 5), disk_limit(), max(disk_limit(), 99.5))[index - 1], {"device": "/dev/vda1"}),
                result("/var/pifet", 31.5 + index, {"device": "/dev/vdb1"}),
            ]),
            check("REPORT", "report", [
                result("/var/pifet/queue/reports", index * 3),
                result("/var/pifet/queue/shopReport", 0),
                result("/var/pifet/queue/miles", 2),
                result("/var/pifet/queue/feedback", 0),
            ]),
            check("DATA_CREWLIST", "content", [
                result("crewlist", 12, {
                    "directory": "/var/pifet/data/crewlist",
                    "last_file": "crewlist_demo.xml", "last_time": last_file_time,
                    "err_count": 1 if index == 3 else 0,
                    "err_files": ["crewlist_demo.err"] if index == 3 else [],
                }),
            ]),
            check("DATA_PAX", "content", [
                result("pax", None if index == 4 else 0, {
                    "directory": "/var/pifet/data/pax",
                    "last_file": None, "last_time": None,
                    "err_count": None if index == 4 else 0, "err_files": [],
                }),
            ]),
        ]
        servers.append({
            "id": index, "name": f"Демо — {machine}",
            "ip_address": f"192.0.2.{index}",
            "agent": {
                "site_id": f"demo-{machine}", "agent_id": machine,
                "enabled": True, "last_seen_at": now.isoformat(),
            },
            "report": {
                "report_id": f"demo-{index}", "schema_version": 2,
                "sequence": 1, "checked_at": checked,
                "received_at": now.isoformat(), "interval_minutes": 5,
                "error": None, "checks": checks,
            },
        })
    return {
        "generated_at": now.isoformat(), "demo": True,
        "disk_limit": disk_limit(), "servers": servers,
    }
