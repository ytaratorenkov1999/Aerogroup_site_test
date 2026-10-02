from django.db import models


class CrewMember(models.Model):
    """
    Соответствие реального члена экипажа (по табельному номеру SAP)
    и его сгенерированных фейковых персональных данных.

    Ранее хранилось в SQLite (crew_akr.db, таблица russia_crew),
    перенесено в Postgres через Django ORM.
    """

    sap_number = models.BigIntegerField(
        primary_key=True,
        verbose_name="Табельный номер (SAP)",
    )
    first_name_ru = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Имя (RU)"
    )
    first_name_en = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Имя (EN)"
    )
    second_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Фамилия"
    )
    full_name = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Полное ФИО"
    )
    email = models.EmailField(
        max_length=255, blank=True, null=True, verbose_name="Email"
    )
    phone = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Телефон"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Член экипажа"
        verbose_name_plural = "Члены экипажа"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sap_number} — {self.full_name or 'без имени'}"