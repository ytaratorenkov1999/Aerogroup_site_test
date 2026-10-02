"""
project_finance/models.py

Учёт выполненной работы по микросайтам: проекты, прайс-лист проекта и задачи.
Сумма задачи = цена × количество; задача «не в стоимости» (is_free) даёт 0 ₽,
но остаётся в списке.
"""
from decimal import Decimal

from django.db import models
from django.db.models import Max


class MicrositeProject(models.Model):
    STATUS_ACTIVE   = 'active'
    STATUS_CLOSED   = 'closed'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_ACTIVE,   'Активный'),
        (STATUS_CLOSED,   'Закрыт'),
        (STATUS_ARCHIVED, 'В архиве'),
    ]

    name        = models.CharField(max_length=120, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, verbose_name='Статус')
    order       = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Проект (микросайты)'
        verbose_name_plural = 'Проекты (микросайты)'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self._state.adding and not self.order:
            self.order = (MicrositeProject.objects.aggregate(m=Max('order'))['m'] or 0) + 1
        super().save(*args, **kwargs)


class PriceItem(models.Model):
    """Позиция прайс-листа проекта. Цена копируется в задачу при её создании."""
    project       = models.ForeignKey(MicrositeProject, on_delete=models.CASCADE, related_name='price_items', verbose_name='Проект')
    name          = models.CharField(max_length=160, verbose_name='Услуга')
    price         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Цена, ₽')
    is_negotiable = models.BooleanField(default=False, verbose_name='По договорённости')
    order         = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Позиция прайса'
        verbose_name_plural = 'Прайс-лист'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_negotiable:
            self.price = None
        if self._state.adding and not self.order:
            self.order = (PriceItem.objects.filter(project=self.project).aggregate(m=Max('order'))['m'] or 0) + 1
        super().save(*args, **kwargs)


class Task(models.Model):
    project      = models.ForeignKey(MicrositeProject, on_delete=models.CASCADE, related_name='tasks', verbose_name='Проект')
    number       = models.PositiveIntegerField(verbose_name='№')
    title        = models.CharField(max_length=200, verbose_name='Название')
    description  = models.TextField(blank=True, verbose_name='Описание')
    price_item   = models.ForeignKey(PriceItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Услуга из прайса')
    service_name = models.CharField(max_length=160, blank=True, verbose_name='Услуга (на момент создания)')
    price        = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Цена за единицу, ₽')
    quantity     = models.PositiveIntegerField(default=1, verbose_name='Количество')
    time_spent   = models.CharField(max_length=60, blank=True, verbose_name='Затраченное время')
    date         = models.DateField(verbose_name='Дата')
    is_free      = models.BooleanField(default=False, verbose_name='Не включать в стоимость')
    is_paid      = models.BooleanField(default=False, verbose_name='Оплачено')
    paid_at      = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['project', 'number'], name='pf_task_unique_number'),
        ]

    def __str__(self):
        return f'№{self.number} {self.title}'

    @property
    def full_amount(self):
        """Цена × количество, без учёта «не в стоимости»."""
        return (self.price or Decimal('0')) * self.quantity

    @property
    def amount(self):
        """Сумма к оплате: 0 для задач «не в стоимости»."""
        return Decimal('0') if self.is_free else self.full_amount

    @property
    def service_label(self):
        return self.price_item.name if self.price_item else (self.service_name or '—')

    def save(self, *args, **kwargs):
        if self._state.adding and not self.number:
            self.number = (Task.objects.filter(project=self.project).aggregate(m=Max('number'))['m'] or 0) + 1
        super().save(*args, **kwargs)


def totals(tasks):
    """Итоги по набору задач: всего / оплачено / не оплачено."""
    total = paid = Decimal('0')
    for task in tasks:
        total += task.amount
        if task.is_paid:
            paid += task.amount
    return {'total': total, 'paid': paid, 'due': total - paid}
