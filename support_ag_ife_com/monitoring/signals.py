import logging
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID

from django.db import DatabaseError, transaction
from django.db.models.signals import post_delete

from .models import MonitoringAgent, MonitoringReport

log = logging.getLogger(__name__)


def remove_report_file(
    agent_pk: int, report_id: UUID, path: Path, using: str,
) -> None:
    try:
        with transaction.atomic(using=using):
            # Ingest locks the same agent: do not remove a re-delivered report.
            MonitoringAgent.objects.using(using).select_for_update().filter(
                pk=agent_pk
            ).first()
            if MonitoringReport.objects.using(using).filter(
                report_id=report_id
            ).exists():
                return
            path.unlink(missing_ok=True)
    except (OSError, DatabaseError):
        log.error("Report file cleanup failed: report_id=%s", report_id)


def report_deleted(
    sender: type[MonitoringReport], instance: MonitoringReport,
    using: str, **kwargs: Any,
) -> None:
    transaction.on_commit(
        partial(
            remove_report_file, instance.agent_id, instance.report_id,
            instance.storage_path, using,
        ),
        using=using,
    )


def connect_report_cleanup() -> None:
    post_delete.connect(
        report_deleted, sender=MonitoringReport,
        dispatch_uid="monitoring.report_file_cleanup",
    )
