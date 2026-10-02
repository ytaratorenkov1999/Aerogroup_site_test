from django.contrib import admin
from django.utils.html import format_html, mark_safe
from .models import DailyTable


STATUS_COLORS = {
    'working':         ('#eaf3de', '#3b6d11', 'ЯП — Рабочий день'),
    'working_holiday': ('#faeeda', '#ba7517', 'РВ — Работа в выходной'),
    'vacation':        ('#e6f1fb', '#185fa5', 'В — Выходной/отпуск'),
}


@admin.register(DailyTable)
class DailyTableAdmin(admin.ModelAdmin):
    list_display   = ('employee_name', 'date', 'status_badge', 'department')
    list_filter    = ('status', 'date', 'employee__department')
    search_fields  = ('employee__full_name',)
    ordering       = ('-date', 'employee__full_name')
    date_hierarchy = 'date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'employee', 'employee__department'
        )

    def employee_name(self, obj):
        return obj.employee.full_name
    employee_name.short_description = 'Сотрудник'
    employee_name.admin_order_field = 'employee__full_name'

    def department(self, obj):
        dept = obj.employee.department
        return dept.name if dept else mark_safe('<span style="color:#aaa">—</span>')
    department.short_description = 'Отдел'

    def status_badge(self, obj):
        bg, fg, label = STATUS_COLORS.get(obj.status, ('#f0f0f0', '#555', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:10px;font-size:12px;font-weight:500">{}</span>',
            bg, fg, label
        )
    status_badge.short_description = 'Статус'
    status_badge.admin_order_field = 'status'