from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html, mark_safe
from unfold.admin import ModelAdmin, StackedInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

# Русификация заголовков Django admin (оформление — django-unfold, см. settings.UNFOLD)
admin.site.site_header  = 'Панель администратора'
admin.site.site_title   = 'Aerogroup'
admin.site.index_title  = 'Управление системой'
from .models import Employee, EmployeeProfile, Department, Role
from .roles import ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR, ROLE_READER, ROLE_EXTERNAL


# ══════════════════════════════════════════════════════════════
#  Отделы
# ══════════════════════════════════════════════════════════════

@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
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

# Цвета для каждого уровня доступа
ROLE_COLORS = {
    ROLE_ADMIN:    ('#1a1a2e', '#fff'),
    ROLE_MANAGER:  ('#1251a3', '#fff'),
    ROLE_EDITOR:   ('#0f6e56', '#fff'),
    ROLE_READER:   ('#5f5e5a', '#fff'),
    ROLE_EXTERNAL: ('#854f0b', '#fff'),
}


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display  = ('colored_name', 'access_level', 'employee_count')
    list_filter   = ('code',)
    search_fields = ('name',)
    ordering      = ('name',)
    fields        = ('name', 'code')

    def access_level(self, obj):
        if not obj.code:
            return mark_safe('<span style="color:#e24b4a;font-weight:600">не задан — прав нет</span>')
        return obj.get_code_display()
    access_level.short_description = 'Уровень доступа'
    access_level.admin_order_field = 'code'

    def colored_name(self, obj):
        bg, fg = ROLE_COLORS.get(obj.code, ('#888', '#fff'))
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
#  Сотрудники: учётная запись + профиль на одной странице
# ══════════════════════════════════════════════════════════════

# Учётные записи показываем через proxy Employee в разделе «Сотрудники»,
# группы не используются — права выдаются через роли
admin.site.unregister(User)
admin.site.unregister(Group)


def _avatar_and_name(profile, username):
    if profile and profile.photo:
        img = format_html(
            '<img src="{}" style="width:32px;height:32px;border-radius:50%;'
            'object-fit:cover;vertical-align:middle;margin-right:8px">',
            profile.photo.url
        )
    else:
        initials = ((profile and profile.full_name) or username)[:1].upper()
        img = format_html(
            '<span style="display:inline-flex;align-items:center;justify-content:center;'
            'width:32px;height:32px;border-radius:50%;background:#03a0dc;color:#fff;'
            'font-size:13px;font-weight:600;vertical-align:middle;margin-right:8px">{}</span>',
            initials
        )
    return format_html('{}{}', img, (profile and profile.full_name) or '—')


def _role_badge(role):
    if not role:
        return mark_safe('<span style="color:#aaa;font-size:12px">— не задана —</span>')
    bg, fg = ROLE_COLORS.get(role.code, ('#888', '#fff'))
    return format_html(
        '<span style="background:{};color:{};padding:2px 9px;'
        'border-radius:10px;font-size:12px;font-weight:500">{}</span>',
        bg, fg, role.name
    )


class EmployeeProfileInline(StackedInline):
    """Профиль заполняется сразу при создании пользователя.
    Отдел и роль можно завести прямо отсюда — кнопкой «+» у поля."""
    model               = EmployeeProfile
    fk_name             = 'user'
    min_num             = 1
    max_num             = 1
    extra               = 0
    can_delete          = False
    verbose_name        = 'Профиль сотрудника'
    verbose_name_plural = 'Профиль сотрудника'
    readonly_fields     = ('avatar_preview',)
    fieldsets = (
        ('Роль и отдел', {
            'fields': ('role', 'department', 'position'),
        }),
        ('Личные данные', {
            'fields': ('full_name', 'email', 'phone', 'birthday'),
        }),
        ('Фото', {
            'fields': ('photo', 'avatar_preview'),
        }),
    )

    def avatar_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;'
                'border-radius:50%;object-fit:cover">',
                obj.photo.url
            )
        return '— нет фото —'
    avatar_preview.short_description = 'Предпросмотр фото'


@admin.register(Employee)
class EmployeeAdmin(BaseUserAdmin, ModelAdmin):
    form                 = UserChangeForm
    add_form             = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    inlines        = [EmployeeProfileInline]
    list_display   = (
        'avatar_and_name', 'user_login', 'role_badge',
        'department_name', 'position', 'is_active',
    )
    list_filter    = ('profile__role', 'profile__department', 'is_active', 'is_superuser')
    search_fields  = ('username', 'profile__full_name', 'profile__email', 'profile__position')
    ordering       = ('profile__full_name', 'username')

    # ФИО и почта хранятся в профиле — поля User first_name/last_name/email не показываем
    fieldsets = (
        ('Учётная запись', {
            'fields': ('username', 'password', 'is_active'),
        }),
        ('Доступ к панели администратора', {
            'fields': ('is_staff', 'is_superuser', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Даты', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'profile', 'profile__role', 'profile__department'
        )

    @staticmethod
    def _profile(obj):
        return getattr(obj, 'profile', None)

    def avatar_and_name(self, obj):
        return _avatar_and_name(self._profile(obj), obj.username)
    avatar_and_name.short_description = 'Сотрудник'
    avatar_and_name.admin_order_field = 'profile__full_name'

    def user_login(self, obj):
        return format_html(
            '<span style="font-family:monospace;color:#555">@{}</span>',
            obj.username
        )
    user_login.short_description = 'Логин'
    user_login.admin_order_field = 'username'

    def role_badge(self, obj):
        profile = self._profile(obj)
        return _role_badge(profile.role if profile else None)
    role_badge.short_description = 'Роль'

    def department_name(self, obj):
        profile = self._profile(obj)
        if profile and profile.department:
            return profile.department.name
        return mark_safe('<span style="color:#aaa">—</span>')
    department_name.short_description = 'Отдел'

    def position(self, obj):
        profile = self._profile(obj)
        return (profile and profile.position) or ''
    position.short_description = 'Должность'
