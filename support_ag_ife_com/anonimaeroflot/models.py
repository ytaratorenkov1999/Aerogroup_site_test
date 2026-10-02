from django.db import models


class CrewMember(models.Model):

    sap_number = models.BigIntegerField(
        primary_key=True,
        verbose_name="Табельный номер",
    )
    first_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Имя (с отчеством, RU)"
    )
    last_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Фамилия (RU)"
    )
    full_name = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Полное ФИО (RU)"
    )
    full_name_en = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Полное ФИО (EN, транслит)"
    )
    email = models.EmailField(
        max_length=255, blank=True, null=True, verbose_name="Email"
    )
    instructor_check = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ФИО инструкторской проверки"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Член экипажа"
        verbose_name_plural = "Члены экипажа"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sap_number} — {self.full_name or 'без имени'}"


class Passenger(models.Model):

    document_number = models.CharField(
        max_length=64,
        primary_key=True,
        verbose_name="Номер документа",
    )
    fake_document_number = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Фейковый номер документа"
    )
    first_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Имя"
    )
    middle_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Отчество"
    )
    last_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Фамилия"
    )
    birth_date = models.CharField(
        max_length=32, blank=True, null=True, verbose_name="Дата рождения"
    )
    expiry_date = models.CharField(
        max_length=32, blank=True, null=True, verbose_name="Дата истечения документа"
    )
    phone_number = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Телефон (PCTC)"
    )
    ctcm_phone_number = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Телефон (CTCM)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Пассажир"
        verbose_name_plural = "Пассажиры"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.document_number} — {self.last_name or 'без фамилии'}"
