import hashlib
import logging
import math
import smtplib
from datetime import UTC, timedelta
from email.utils import formataddr, parseaddr
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import (
    AlertNotification, AlertRecipient, DiskAlertState,
    MonitoringAgent, MonitoringReport,
)
from .thresholds import disk_limit
from .mail_templates import render_notification

log = logging.getLogger(__name__)


def record_disk_alerts(
    agent: MonitoringAgent, report: MonitoringReport, data: dict[str, Any],
) -> None:
    """Called inside ingest's transaction while the agent row is locked."""
    from .dashboard import normalize_check

    now = timezone.now()
    interval = data.get("interval_seconds", 300)
    freshness = timedelta(seconds=max(600, interval * 2))
    if not now - freshness <= report.finished_at <= now + timedelta(minutes=5):
        return
    latest = MonitoringReport.objects.filter(agent=agent).order_by(
        "-finished_at", "-sequence", "-received_at",
    ).values_list("pk", flat=True).first()
    if latest != report.pk:
        return

    limit = disk_limit()
    changes: list[str] = []
    has_problem = False
    seen: set[str] = set()
    for raw in data["checks"]:
        if raw.get("type") != "memory":
            continue
        check = normalize_check(raw)
        if not check["enabled"]:
            continue
        for result in check["results"]:
            percent = result["value"]
            if (
                result["enabled"] is False or result["error"]
                or isinstance(percent, bool)
                or not isinstance(percent, (int, float))
                or not math.isfinite(percent) or not 0 <= percent <= 100
            ):
                continue
            target = result["target"]
            key = hashlib.sha256(
                f"{check['check_id']}\0{target}".encode("utf-8"),
            ).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            previous = DiskAlertState.objects.filter(
                agent=agent, target_key=key,
            ).first()
            if previous and report.finished_at < previous.checked_at:
                continue
            critical = percent >= limit
            if critical and (previous is None or not previous.critical):
                has_problem = True
                changes.append(
                    f"Раздел: {target} — {percent:g}% (лимит {limit:g}%).",
                )
            elif not critical and previous and previous.critical:
                changes.append(
                    f"Раздел: {target} — {percent:g}% (лимит {limit:g}%).",
                )
            DiskAlertState.objects.update_or_create(
                agent=agent, target_key=key,
                defaults={
                    "target": target, "critical": critical, "percent": percent,
                    "checked_at": report.finished_at,
                },
            )
    if changes:
        checked = report.finished_at.astimezone(UTC).strftime("%d.%m.%Y %H:%M:%S UTC")
        subject, body = render_notification(
            "disk", "problem" if has_problem else "recovery",
            {
                "server_name": agent.server.name,
                "server_ip": agent.server.ip_address,
                "site_id": agent.site_id, "agent_id": agent.agent_id,
                "checked_at": checked, "events": "\n".join(changes),
                "limit": f"{limit:g}",
            },
        )
        AlertNotification.objects.get_or_create(
            agent=agent, report_id=report.pk,
            defaults={"subject": subject, "body": body},
        )


def recipient_addresses() -> list[str]:
    candidates = AlertRecipient.objects.filter(
        enabled=True,
    ).values_list("email", flat=True)
    addresses: dict[str, str] = {}
    for candidate in candidates:
        address = str(candidate).strip()
        if not address:
            continue
        try:
            validate_email(address)
        except ValidationError:
            log.warning("Monitoring mail recipient ignored: invalid_email")
            continue
        addresses.setdefault(address.casefold(), address)
    return list(addresses.values())


def dispatch_notifications(agent_id: int) -> None:
    """Retry the durable outbox on new reports and idempotent agent retries."""
    try:
        with transaction.atomic():
            # One sender per agent, across all Gunicorn workers.
            MonitoringAgent.objects.select_for_update().get(pk=agent_id)
            pending = list(AlertNotification.objects.filter(
                agent_id=agent_id, sent_at__isnull=True,
            ).order_by("created_at", "pk")[:10])
            if not pending:
                return
            recipients = recipient_addresses()
            if not recipients:
                log.warning("Monitoring mail pending: no_recipients")
                return
            delivered = 0
            for item in pending:
                item.attempts += 1
                item.save(update_fields=["attempts"])
                try:
                    address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
                    validate_email(address)
                    sender = formataddr((
                        getattr(settings, "MAIL_FROM_NAME", "AG-Monitoring"),
                        address,
                    ))
                    message = EmailMessage(
                        subject=item.subject, body=item.body,
                        from_email=sender, bcc=recipients,
                        connection=get_connection(timeout=5),
                    )
                    if message.send(fail_silently=False) != 1:
                        raise smtplib.SMTPException("mail_not_sent")
                except (
                    OSError, smtplib.SMTPException, ValueError, ValidationError,
                ):
                    item.last_error = "smtp_error"
                    item.save(update_fields=["last_error"])
                    log.warning(
                        "Monitoring mail delivery failed: agent_pk=%s", agent_id,
                    )
                    return
                item.sent_at = timezone.now()
                item.last_error = ""
                item.save(update_fields=["sent_at", "last_error"])
                delivered += 1
            log.info(
                "Monitoring mail delivered: agent_pk=%s events=%s",
                agent_id, delivered,
            )
    except (DatabaseError, MonitoringAgent.DoesNotExist):
        log.error("Monitoring mail storage unavailable: agent_pk=%s", agent_id)
