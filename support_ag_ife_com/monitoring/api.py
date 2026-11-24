import hashlib
import json
import logging
from functools import partial
from typing import Any

from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables

from .models import MonitoringAgent, MonitoringReport
from .notifications import dispatch_notifications, record_disk_alerts
from .storage import store_report
from .validation import ReportValidationError, validate_report

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 2 * 1024 * 1024


def reject_constant(value: str) -> None:
    raise ValueError("invalid_json")


def unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def response_error(
    code: str, status: int, field: str | None = None,
) -> JsonResponse:
    payload = {"accepted": False, "error": code}
    if field is not None:
        payload["field"] = field
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def acknowledgement(report_id: str, created: bool) -> JsonResponse:
    response = JsonResponse(
        {"accepted": True, "report_id": report_id},
        status=201 if created else 200,
    )
    response["Cache-Control"] = "no-store"
    return response


@sensitive_variables("authorization", "token", "body", "data")
@csrf_exempt
def ingest_report(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        response = response_error("method_not_allowed", 405)
        response["Allow"] = "POST"
        return response

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or len(authorization) > 263:
        return response_error("unauthorized", 401)
    token = authorization[7:]
    if not 32 <= len(token) <= 256 or any(c.isspace() for c in token):
        return response_error("unauthorized", 401)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        agent = MonitoringAgent.objects.filter(
            token_hash=digest, enabled=True
        ).first()
    except DatabaseError:
        log.error("Monitoring authentication storage unavailable")
        return response_error("storage_unavailable", 503)
    if agent is None:
        return response_error("unauthorized", 401)
    if request.content_type != "application/json":
        return response_error("unsupported_media_type", 415)

    length = request.META.get("CONTENT_LENGTH")
    try:
        if length and (int(length) < 0 or int(length) > MAX_BODY_BYTES):
            return response_error("payload_too_large", 413)
        body = request.read(MAX_BODY_BYTES + 1)
    except (OSError, ValueError):
        return response_error("invalid_request", 400)
    if len(body) > MAX_BODY_BYTES:
        return response_error("payload_too_large", 413)
    try:
        data = json.loads(
            body.decode("utf-8"),
            parse_constant=reject_constant, object_pairs_hook=unique_object,
        )
        fields = validate_report(data)
    except ReportValidationError as error:
        log.warning("Monitoring report rejected: field=%s", error.field)
        return response_error("invalid_report", 400, field=error.field)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        return response_error("invalid_report", 400)

    if fields["site_id"] != agent.site_id or fields["agent_id"] != agent.agent_id:
        return response_error("agent_identity_mismatch", 403)
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is not None and idempotency_key != data["report_id"]:
        return response_error("idempotency_key_mismatch", 400)
    sha256 = hashlib.sha256(body).hexdigest()
    report_id = str(fields["report_id"])
    try:
        with transaction.atomic():
            # Serialize ingest for one agent, including token revocation.
            locked = MonitoringAgent.objects.select_for_update().get(pk=agent.pk)
            if not locked.enabled or locked.token_hash != digest:
                return response_error("unauthorized", 401)
            existing = MonitoringReport.objects.filter(
                report_id=fields["report_id"]
            ).first()
            if existing is not None:
                if existing.agent_id != agent.pk or existing.sha256 != sha256:
                    return response_error("report_id_conflict", 409)
                store_report(agent.pk, fields["report_id"], body)
                MonitoringAgent.objects.filter(pk=agent.pk).update(
                    last_seen_at=timezone.now()
                )
                created = False
            else:
                if MonitoringReport.objects.filter(
                    agent=agent, stream_id=fields["stream_id"],
                    sequence=fields["sequence"],
                ).exists():
                    return response_error("sequence_conflict", 409)
                store_report(agent.pk, fields["report_id"], body)
                report = MonitoringReport.objects.create(
                    agent=agent, report_id=fields["report_id"],
                    stream_id=fields["stream_id"], sequence=fields["sequence"],
                    schema_version=fields["schema_version"],
                    started_at=fields["started_at"],
                    finished_at=fields["finished_at"],
                    sha256=sha256, size_bytes=len(body),
                )
                MonitoringAgent.objects.filter(pk=agent.pk).update(
                    last_seen_at=timezone.now()
                )
                record_disk_alerts(locked, report, data)
                created = True
            transaction.on_commit(
                partial(dispatch_notifications, agent.pk), robust=True,
            )
    except MonitoringAgent.DoesNotExist:
        return response_error("unauthorized", 401)
    except (OSError, DatabaseError):
        # Never log request bodies, authorization headers or token values.
        log.error("Monitoring report persistence failed: agent_pk=%s", agent.pk)
        return response_error("storage_unavailable", 503)
    return acknowledgement(data["report_id"], created)
