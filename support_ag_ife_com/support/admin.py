from django.contrib import admin
from django.utils.html import format_html, mark_safe

# Русификация заголовков Django admin
admin.site.site_header  = 'Панель администратора'
admin.site.site_title   = 'Aerogroup'
admin.site.index_title  = 'Управление системой'
from .models import EmployeeProfile, Department, Role


# ══════════════════════════════════════════════════════════════
#  Отделы
# ══════════════════════════════════════════════════════════════

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'employee_count')
    search_fields = ('name',)
    ordering      = ('name',)

    def employee_count(self, obj):
        count = obj.employeeprofile_set.count()
        return format_html('<b>{}</b> сотр.', count)
    employee_count.short_description = 'Сотрудников'


# ══════════════════════════════════════════════════════════════
#  Роли
# ══════════════════════════════════════════════════════════════

# Цвета для каждой роли
ROLE_COLORS = {
    'Администратор':   ('#1a1a2e', '#fff'),
    'Руководитель':    ('#1251a3', '#fff'),
    'Редактор':        ('#0f6e56', '#fff'),
    'Читатель':        ('#5f5e5a', '#fff'),
    'Сторонний отдел': ('#854f0b', '#fff'),
}


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ('colored_name', 'employee_count')
    search_fields = ('name',)
    ordering      = ('name',)

    def colored_name(self, obj):
        bg, fg = ROLE_COLORS.get(obj.name, ('#888', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:500">{}</span>',
            bg, fg, obj.name
        )
    colored_name.short_description = 'Роль'

    def employee_count(self, obj):
        count = obj.employeeprofile_set.count()
        return format_html('<b>{}</b> сотр.', count)
    employee_count.short_description = 'Сотрудников'


# ══════════════════════════════════════════════════════════════
#  Профили сотрудников
# ══════════════════════════════════════════════════════════════

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display   = (
        'avatar_and_name', 'user_login', 'role_badge',
        'department', 'position', 'email', 'phone',
    )
    list_filter    = ('department', 'role')
    search_fields  = ('full_name', 'user__username', 'email', 'position')
    ordering       = ('full_name',)
    readonly_fields = ('avatar_preview',)

    fieldsets = (
        ('Учётная запись', {
            'fields': ('user', 'role', 'department'),
        }),
        ('Личные данные', {
            'fields': ('full_name', 'email', 'phone', 'birthday', 'position'),
        }),
        ('Фото', {
            'fields': ('photo', 'avatar_preview'),
            'classes': ('collapse',),
        }),
    )

    def avatar_and_name(self, obj):
        if obj.photo:
            img = format_html(
                '<img src="{}" style="width:32px;height:32px;border-radius:50%;'
                'object-fit:cover;vertical-align:middle;margin-right:8px">',
                obj.photo.url
            )
        else:
            initials = (obj.full_name or obj.user.username)[:1].upper()
            img = format_html(
                '<span style="display:inline-flex;align-items:center;justify-content:center;'
                'width:32px;height:32px;border-radius:50%;background:#03a0dc;color:#fff;'
                'font-size:13px;font-weight:600;vertical-align:middle;margin-right:8px">{}</span>',
                initials
            )
        return format_html('{}{}', img, obj.full_name or '—')
    avatar_and_name.short_description = 'Сотрудник'

    def user_login(self, obj):
        return format_html(
            '<span style="font-family:monospace;color:#555">@{}</span>',
            obj.user.username
        )
    user_login.short_description = 'Логин'

    def role_badge(self, obj):
        if not obj.role:
            return mark_safe('<span style="color:#aaa;font-size:12px">— не задана —</span>')
        bg, fg = ROLE_COLORS.get(obj.role.name, ('#888', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:10px;font-size:12px;font-weight:500">{}</span>',
            bg, fg, obj.role.name
        )
    role_badge.short_description = 'Роль'

    def avatar_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;'
                'border-radius:50%;object-fit:cover">',
                obj.photo.url
            )
        return '— нет фото —'
    avatar_preview.short_description = 'Предпросмотр фото'