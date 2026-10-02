from django.contrib import admin
from django.utils.html import format_html
from .models import HelpdeskStatistic, HelpdeskAdminStat, HelpdeskCategoryAfl, HelpdeskCategoryAkr

class HelpdeskAdminStatInline(admin.TabularInline):
    model           = HelpdeskAdminStat
    extra           = 0
    readonly_fields = ('name', 'count')
    fields          = ('name', 'count')
    can_delete      = False
    verbose_name_plural = 'По сотрудникам'

    def has_add_permission(self, request, obj=None):
        return False

class HelpdeskCategoryAflInline(admin.TabularInline):
    model           = HelpdeskCategoryAfl
    extra           = 0
    readonly_fields = ('category', 'count')
    fields          = ('category', 'count')
    can_delete      = False
    verbose_name_plural = 'Категории Аэрофлот'

    def has_add_permission(self, request, obj=None):
        return False


class HelpdeskCategoryAkrInline(admin.TabularInline):
    model           = HelpdeskCategoryAkr
    extra           = 0
    readonly_fields = ('category', 'count')
    fields          = ('category', 'count')
    can_delete      = False
    verbose_name_plural = 'Категории Россия'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(HelpdeskStatistic)
class HelpdeskStatisticAdmin(admin.ModelAdmin):
    list_display   = (
        'period', 'total_badge', 'afl_count', 'akr_count',
        'redirect_pct', 'created_at',
    )
    list_filter    = ('period',)
    search_fields  = ('period',)
    readonly_fields = (
        'period', 'created_at', 'total_ticket',
        'request_count_afl', 'request_count_akr',
        'count_service_ife', 'count_service_rportal',
        'redirect_second_line', 'redirect_second_line_count', 'avg_time_first_answer',
    )
    ordering       = ('-created_at',)
    inlines        = [
        HelpdeskAdminStatInline,
        HelpdeskCategoryAflInline,
        HelpdeskCategoryAkrInline,
    ]

    fieldsets = (
        ('Период', {
            'fields': ('period', 'created_at'),
        }),
        ('Обращения', {
            'fields': (
                'total_ticket',
                'request_count_afl', 'request_count_akr',
                'count_service_ife', 'count_service_rportal',
            ),
        }),
        ('Показатели', {
            'fields': ('redirect_second_line', 'redirect_second_line_count', 'avg_time_first_answer'),
        }),
    )

    def total_badge(self, obj):
        return format_html(
            '<span style="font-size:15px;font-weight:700;color:#03a0dc">{}</span>',
            obj.total_ticket
        )
    total_badge.short_description = 'Всего'
    total_badge.admin_order_field = 'total_ticket'

    def afl_count(self, obj):
        return format_html('<b>{}</b>', obj.request_count_afl)
    afl_count.short_description = 'AFL'

    def akr_count(self, obj):
        return format_html('<b>{}</b>', obj.request_count_akr)
    akr_count.short_description = 'AKR'

    def redirect_pct(self, obj):
        pct = float(obj.redirect_second_line)
        color = '#e24b4a' if pct > 20 else '#27ae60'
        return format_html(
            '<span style="color:{};font-weight:600">{}% ({})</span>',
            color, f'{pct:.1f}',
            obj.redirect_second_line_count if obj.redirect_second_line_count is not None else '—'
        )
    redirect_pct.short_description = '2-я линия'
    redirect_pct.admin_order_field = 'redirect_second_line'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False