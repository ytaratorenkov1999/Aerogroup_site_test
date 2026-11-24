import hashlib
from pathlib import Path

from django.core.exceptions import ValidationError
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
