import hashlib
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class Server(models.Model):
    name = models.CharField("Название сервера", max_length=150)
    ip_address = models.GenericIPAddressField(
        "IP-адрес", protocol="both", unique=True
    )
    created_at = models.DateTimeField("Дата добавления", auto_now_add=True)

    class Meta:
        verbose_name = "Сервер"
        verbose_name_plural = "Серверы"
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.name} ({self.ip_address})"


class MonitoringAgent(models.Model):
    server = models.OneToOneField(
        Server, on_delete=models.PROTECT,
        related_name="monitoring_agent", verbose_name="Сервер",
    )
    site_id = models.SlugField("ID площадки", max_length=100, unique=True)
    agent_id = models.SlugField("ID агента", max_length=100, unique=True)
    enabled = models.BooleanField("Приём разрешён", default=False)
    token_hash = models.CharField(
        max_length=64, unique=True, null=True, editable=False
    )
    last_seen_at = models.DateTimeField(
        "Последний приём", null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "Агент мониторинга"
        verbose_name_plural = "Агенты мониторинга"
        ordering = ("site_id",)

    def __str__(self) -> str:
        return f"{self.site_id} / {self.agent_id}"

    def set_api_token(self, value: str) -> None:
        if len(value) < 32 or len(value) > 256 or any(c.isspace() for c in value):
            raise ValidationError(
                "Токен должен содержать от 32 до 256 символов без пробелов."
            )
        self.token_hash = hashlib.sha256(value.encode("utf-8")).hexdigest()

    def clean(self) -> None:
        super().clean()
        if self.enabled and not self.token_hash:
            raise ValidationError(
                {"enabled": "Перед включением приёма задайте токен агента."}
            )


class MonitoringReport(models.Model):
    report_id = models.UUIDField("ID отчёта", primary_key=True, editable=False)
    agent = models.ForeignKey(
        MonitoringAgent, on_delete=models.PROTECT,
        related_name="reports", verbose_name="Агент",
    )
    schema_version = models.PositiveSmallIntegerField("Версия формата")
    stream_id = models.UUIDField("ID потока")
    sequence = models.PositiveBigIntegerField("Номер отчёта")
    started_at = models.DateTimeField("Начало проверки")
    finished_at = models.DateTimeField("Окончание проверки")
    received_at = models.DateTimeField("Получен сайтом", auto_now_add=True)
    sha256 = models.CharField("SHA-256", max_length=64, editable=False)
    size_bytes = models.PositiveIntegerField("Размер файла", editable=False)

    class Meta:
        verbose_name = "Отчёт мониторинга"
        verbose_name_plural = "Отчёты мониторинга"
        ordering = ("-received_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("agent", "stream_id", "sequence"),
                name="monitoring_report_stream_sequence_unique",
            ),
        ]

    def __str__(self) -> str:
        return str(self.report_id)

    @property
    def storage_path(self) -> Path:
        from .storage import report_path

        return report_path(self.agent_id, self.report_id)

class AlertRecipient(models.Model):
    email = models.EmailField("Email", unique=True)
    name = models.CharField("Имя / описание", max_length=150, blank=True)
    enabled = models.BooleanField("Получать уведомления", default=True)

    class Meta:
        verbose_name = "Получатель Alert уведомлений"
        verbose_name_plural = "Alert уведомления"
        ordering = ("email",)

    def __str__(self) -> str:
        return self.email


class DiskAlertState(models.Model):
    agent = models.ForeignKey(MonitoringAgent, on_delete=models.CASCADE)
    target_key = models.CharField(max_length=64)
    target = models.TextField()
    critical = models.BooleanField(default=False)
    percent = models.FloatField()
    checked_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("agent", "target_key"),
                name="monitoring_disk_alert_target_unique",
            ),
        ]


class AlertNotification(models.Model):
    agent = models.ForeignKey(MonitoringAgent, on_delete=models.CASCADE)
    report_id = models.UUIDField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("agent", "report_id"),
                name="monitoring_alert_report_unique",
            ),
        ]

class MailTemplate(models.Model):
    class Category(models.TextChoices):
        DISK = "disk", "Диск"
        CONTENT = "content", "Контент"
        NETWORK = "network", "Сетевая связность"

    category = models.CharField(
        "Раздел", max_length=16, choices=Category.choices, unique=True,
    )
    problem_subject = models.CharField(
        "Тема письма о проблеме", max_length=255,
    )
    problem_body = models.TextField(
        "Текст письма о проблеме", max_length=20000,
    )
    recovery_subject = models.CharField(
        "Тема письма о восстановлении", max_length=255,
    )
    recovery_body = models.TextField(
        "Текст письма о восстановлении", max_length=20000,
    )
    error_subject = models.CharField(
        "Тема письма об ошибках .err", max_length=255, blank=True, default="",
    )
    error_body = models.TextField(
        "Текст письма об ошибках .err", max_length=20000, blank=True, default="",
    )
    error_recovery_subject = models.CharField(
        "Тема письма об устранении ошибок", max_length=255, blank=True, default="",
    )
    error_recovery_body = models.TextField(
        "Текст письма об устранении ошибок", max_length=20000, blank=True, default="",
    )
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        verbose_name = "Шаблон письма"
        verbose_name_plural = "Шаблоны писем"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.get_category_display()

    def clean(self) -> None:
        from .mail_templates import validate_text

        super().clean()
        errors: dict[str, list[str]] = {}
        fields = [
            "problem_subject", "problem_body", "recovery_subject", "recovery_body",
        ]
        if self.category == self.Category.CONTENT:
            fields.extend((
                "error_subject", "error_body",
                "error_recovery_subject", "error_recovery_body",
            ))
        for field in fields:
            try:
                validate_text(
                    getattr(self, field), self.category,
                    subject=field.endswith("_subject"),
                )
            except ValidationError as error:
                errors[field] = error.messages
        if errors:
            raise ValidationError(errors)

class ContentRule(models.Model):
    agent = models.ForeignKey(
        MonitoringAgent, on_delete=models.PROTECT,
        related_name="content_rules", verbose_name="Агент / площадка",
    )
    name = models.CharField("Название потока", max_length=150)
    check_id = models.CharField(
        "ID проверки", max_length=100,
        validators=[RegexValidator(
            r"^[A-Za-z0-9_-]+$",
            "Допустимы латинские буквы, цифры, дефис и подчёркивание.",
        )],
        help_text="Идентификатор из JSON агента, например DATA_CREWID.",
    )
    stream_id = models.CharField(
        "ID потока", max_length=100, default="DIR",
        validators=[RegexValidator(
            r"^[A-Za-z0-9_-]+$",
            "Допустимы латинские буквы, цифры, дефис и подчёркивание.",
        )],
        help_text=(
            "Значение results[].target. Для настройки DATA_CREWID_DIR "
            "укажите DIR; для DATA_CREWID_DIR_MAIN — MAIN."
        ),
    )
    silence_limit_minutes = models.PositiveIntegerField(
        "Допустимая тишина, минут",
        validators=[MinValueValidator(1)],
        help_text="Например: 120 — 2 часа; 180 — 3 часа; 2880 — 48 часов.",
    )
    enabled = models.BooleanField("Контроль тишины", default=True)

    class Meta:
        verbose_name = "Правило контента"
        verbose_name_plural = "Правила контента"
        ordering = ("agent__site_id", "check_id", "stream_id")
        constraints = [
            models.UniqueConstraint(
                fields=("agent", "check_id", "stream_id"),
                name="monitoring_content_rule_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(silence_limit_minutes__gte=1),
                name="monitoring_content_silence_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.agent} — {self.name}"
