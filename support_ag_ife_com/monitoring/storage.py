import os
import tempfile
from pathlib import Path
from uuid import UUID

from django.conf import settings


def report_path(agent_pk: int, report_id: UUID) -> Path:
    root = Path(getattr(
        settings, "MONITORING_REPORTS_ROOT",
        Path(settings.BASE_DIR) / "monitoring_reports",
    ))
    return root / str(agent_pk) / f"{report_id}.json"


def store_report(agent_pk: int, report_id: UUID, body: bytes) -> Path:
    path = report_path(agent_pk, report_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".report-", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    return path
