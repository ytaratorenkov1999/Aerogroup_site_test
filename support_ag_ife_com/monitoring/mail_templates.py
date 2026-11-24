import logging
from string import Formatter
from typing import Any

from django.core.exceptions import ValidationError

log = logging.getLogger(__name__)

COMMON_FIELDS = {
    "server_name": "название сервера",
    "server_ip": "IP-адрес сервера",
    "site_id": "идентификатор площадки",
    "agent_id": "идентификатор агента",
    "checked_at": "дата проверки в UTC",
    "events": "список обнаруженных изменений",
}
CATEGORY_FIELDS = {
    "disk": {"limit": "порог заполнения диска, %"},
    "content": {
        "stream_name": "название потока", "directory": "каталог",
        "last_time": "дата последнего файла в UTC",
        "silence_minutes": "длительность тишины в минутах",
        "error_count": "количество файлов с ошибками",
    },
    "network": {
        "stream_name": "название потока", "target": "адрес подключения",
        "port": "порт", "error": "описание ошибки",
    },
}
BODY = (
    "Сервер: {server_name}\n"
    "Площадка: {site_id}\n"
    "Дата проверки: {checked_at}\n\n{events}"
)
DEFAULT_TEMPLATES = {
    "disk": {
        "problem_subject": "AG-Monitoring: состояние дисков",
        "problem_body": BODY,
        "recovery_subject": "AG-Monitoring: диски — восстановление",
        "recovery_body": BODY,
    },
    "content": {
        "problem_subject": "AG-Monitoring: проблема с контентом",
        "problem_body": BODY,
        "recovery_subject": "AG-Monitoring: контент — восстановление",
        "recovery_body": BODY,
    },
    "network": {
        "problem_subject": "AG-Monitoring: сетевая связность нарушена",
        "problem_body": BODY,
        "recovery_subject": "AG-Monitoring: сетевая связность восстановлена",
        "recovery_body": BODY,
    },
}


def available_fields(category: str) -> dict[str, str]:
    return {**COMMON_FIELDS, **CATEGORY_FIELDS.get(category, {})}


def validate_text(value: str, category: str, subject: bool = False) -> None:
    if subject and ("\n" in value or "\r" in value):
        raise ValidationError("Тема письма должна занимать одну строку.")
    if not value.strip():
        raise ValidationError("Шаблон не должен быть пустым.")
    if len(value) > (255 if subject else 20000):
        raise ValidationError("Шаблон превышает допустимую длину.")
    allowed = available_fields(category)
    try:
        for _, field, spec, conversion in Formatter().parse(value):
            if field is None:
                continue
            if field not in allowed or spec or conversion:
                raise ValidationError(
                    "Неизвестная переменная или недопустимый формат. "
                    "Используйте переменные из списка ниже.",
                )
    except ValueError:
        raise ValidationError("Проверьте парность фигурных скобок в шаблоне.") from None


def render_notification(
    category: str, event: str, context: dict[str, Any],
) -> tuple[str, str]:
    """Render only allowlisted string substitutions; no template execution."""
    from .models import MailTemplate

    if category not in DEFAULT_TEMPLATES or event not in {"problem", "recovery"}:
        raise ValueError("Unknown notification template category or event")
    defaults = DEFAULT_TEMPLATES[category]
    template = MailTemplate.objects.filter(category=category).first()
    subject_key, body_key = f"{event}_subject", f"{event}_body"
    subject = getattr(template, subject_key) if template else defaults[subject_key]
    body = getattr(template, body_key) if template else defaults[body_key]
    try:
        validate_text(subject, category, subject=True)
        validate_text(body, category)
    except ValidationError:
        log.warning("Monitoring mail template invalid: category=%s event=%s", category, event)
        subject, body = defaults[subject_key], defaults[body_key]
    values = {
        key: str(context[key]) if context.get(key) is not None else "-"
        for key in available_fields(category)
    }
    rendered_subject = subject.format_map(values)
    rendered_subject = rendered_subject.replace("\r", " ").replace("\n", " ")[:255]
    return rendered_subject, body.format_map(values)
