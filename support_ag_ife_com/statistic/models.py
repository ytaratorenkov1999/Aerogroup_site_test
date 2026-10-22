from decouple import config
from django.db import models
from typing import TYPE_CHECKING


class HelpdeskStatistic(models.Model):
    """Основная таблица со статистикой за период"""
    period = models.CharField(max_length=7)                   # "2026-05"
    created_at = models.DateTimeField(auto_now_add=True)

    total_ticket = models.IntegerField()
    request_count_afl = models.IntegerField()
    request_count_akr = models.IntegerField()
    count_service_ife = models.IntegerField()
    count_service_rportal = models.IntegerField()
    redirect_second_line = models.FloatField()                # процент

    redirect_second_line_count = models.IntegerField(null=True, blank=True)
    avg_time_first_answer = models.FloatField(null=True)

    if TYPE_CHECKING:
        from django.db.models import QuerySet

    admins: 'QuerySet[HelpdeskAdminStat]'
    categories_afl: 'QuerySet[HelpdeskCategoryAfl]'
    categories_akr: 'QuerySet[HelpdeskCategoryAkr]'
    tickets: 'QuerySet[HelpdeskTicket]'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Статистика HelpDesk'
        verbose_name_plural = 'Статистика HelpDesk'

    def __str__(self):
        return f"Статистика за {self.period} ({self.created_at:%d.%m.%Y %H:%M})"


class HelpdeskAdminStat(models.Model):
    statistic = models.ForeignKey(HelpdeskStatistic, on_delete=models.CASCADE, related_name='admins')
    name = models.CharField(max_length=150)
    count = models.IntegerField()

    class Meta:
        ordering = ['-count']
        verbose_name = 'Статистика по сотруднику'
        verbose_name_plural = 'Статистика по сотрудникам'

    def __str__(self):
        return f"{self.name}: {self.count}"


class HelpdeskCategoryAfl(models.Model):
    statistic = models.ForeignKey(HelpdeskStatistic, on_delete=models.CASCADE, related_name='categories_afl')
    category = models.CharField(max_length=255)
    count = models.IntegerField()
    ticket_ids = models.JSONField(default=list)  # [20499, 20500, ...]

    class Meta:
        ordering = ['-count']
        verbose_name = 'Категория AFL'
        verbose_name_plural = 'Категории AFL'

    def __str__(self):
        return f"{self.category}: {self.count}"


class HelpdeskCategoryAkr(models.Model):
    statistic = models.ForeignKey(HelpdeskStatistic, on_delete=models.CASCADE, related_name='categories_akr')
    category = models.CharField(max_length=255)
    count = models.IntegerField()
    ticket_ids = models.JSONField(default=list)  # [20499, 20500, ...]

    class Meta:
        ordering = ['-count']
        verbose_name = 'Категория AKR'
        verbose_name_plural = 'Категории AKR'

    def __str__(self):
        return f"{self.category}: {self.count}"


class HelpdeskTicketQuerySet(models.QuerySet):
    def afl(self):
        return self.filter(airline=HelpdeskTicket.AFL)

    def akr(self):
        return self.filter(airline=HelpdeskTicket.AKR)

    def crew_tablet(self):
        return self.filter(
            models.Q(airline=HelpdeskTicket.AFL, service_name=config('SERVICE_NAME_AFL'))
            | models.Q(airline=HelpdeskTicket.AKR, service_name=config('SERVICE_NAME_AKR'))
        )

    def media_services(self):
        return self.filter(
            models.Q(airline=HelpdeskTicket.AFL, service_name=config('SERVICE_NAME_IFE_AFL'))
            | models.Q(airline=HelpdeskTicket.AKR, service_name=config('SERVICE_NAME_MEDIA_AKR'))
        )

    def second_line(self):
        return self.crew_tablet().filter(group=config('SECOND_LINE'))

    def handled_by_admins(self, admins):
        return self.crew_tablet().filter(executor__in=admins)


class HelpdeskTicket(models.Model):
    AFL = 'afl'
    AKR = 'akr'
    AIRLINE_CHOICES = [
        (AFL, 'ПАО "Аэрофлот"'),
        (AKR, 'АК "Россия"'),
    ]
    TICKET_URL_ENV = {
        AFL: ('HELPDESK_AFL_TICKET_URL', 'https://helpdesk-su.ag-ife.com/request/'),
        AKR: ('HELPDESK_AKR_TICKET_URL', 'https://helpdesk-fv.ag-ife.com/request/'),
    }

    statistic = models.ForeignKey(HelpdeskStatistic, on_delete=models.CASCADE, related_name='tickets')
    airline = models.CharField(max_length=3, choices=AIRLINE_CHOICES)
    ticket_id = models.PositiveIntegerField(null=True)
    service_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=255, blank=True)
    group = models.CharField(max_length=255, blank=True)         # gfullname
    executor = models.CharField(max_length=255, blank=True)      # mfullname
    created_at = models.DateTimeField(null=True)                 # Date
    first_answer_at = models.DateTimeField(null=True)            # fStartTime
    first_answer_minutes = models.FloatField(null=True)

    objects = HelpdeskTicketQuerySet.as_manager()

    class Meta:
        ordering = ['created_at', 'ticket_id']
        indexes = [models.Index(fields=['statistic', 'airline'])]
        verbose_name = 'Заявка HelpDesk'
        verbose_name_plural = 'Заявки HelpDesk'

    def __str__(self):
        return f"#{self.ticket_id} ({self.get_airline_display()})"

    @classmethod
    def base_url(cls, airline):
        env_name, default = cls.TICKET_URL_ENV[airline]
        return config(env_name, default=default)

    @property
    def url(self):
        if self.ticket_id is None:
            return ''
        return f"{self.base_url(self.airline)}{self.ticket_id}"