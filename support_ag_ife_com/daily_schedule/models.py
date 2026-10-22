from django.db import models
from support.models import EmployeeProfile


class DailyTable(models.Model):
    STATUS_CHOICES = [
        ('working', 'ЯП — Рабочий день'),
        ('working_holiday', 'РВ — Работа в выходной'),
        ('vacation', 'В — Выходной/отпуск'),
    ]

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name='daily_entries',
        verbose_name='Сотрудник'
    )
    date = models.DateField(verbose_name='Дата')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name='Статус'
    )

    class Meta:
        verbose_name = 'Запись табеля'
        verbose_name_plural = 'Записи табеля'
        unique_together = ('employee', 'date')
        ordering = ['date', 'employee']

    def __str__(self):
        return f"{self.employee} — {self.date} — {self.get_status_display()}"