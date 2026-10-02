"""
support/roles.py

Константы ролей и декораторы для проверки прав доступа.

Использование:
    from support.roles import role_required, ROLE_EDITOR

    @login_required
    @role_required(ROLE_EDITOR, ROLE_MANAGER, ROLE_ADMIN)
    def my_view(request):
        ...

Вспомогательные функции:
    get_user_role(user)  → строка с названием роли или None
    has_role(user, *roles) → bool
    can_edit(user)       → bool  (Администратор, Руководитель, Редактор)
    can_delete(user)     → bool  (Администратор, Руководитель)
    can_edit_schedule(user) → bool (Администратор, Руководитель)
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden

# ── Названия ролей (точно как в БД) ──────────────────────────────────────────
ROLE_ADMIN    = 'Администратор'
ROLE_MANAGER  = 'Руководитель'
ROLE_EDITOR   = 'Редактор'
ROLE_READER   = 'Читатель'
ROLE_EXTERNAL = 'Сторонний отдел'

# Роли у которых нет права на Django-admin (проверяется в middleware)
ROLES_NO_ADMIN = {ROLE_MANAGER, ROLE_EDITOR, ROLE_READER, ROLE_EXTERNAL}

# Роли с правом редактировать контент (создавать/изменять статьи)
ROLES_CAN_EDIT = {ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR}

# Роли с правом удалять контент
ROLES_CAN_DELETE = {ROLE_ADMIN, ROLE_MANAGER}

# Роли с правом редактировать/загружать график
ROLES_CAN_EDIT_SCHEDULE = {ROLE_ADMIN, ROLE_MANAGER}


def get_user_role(user):
    """Возвращает название роли пользователя или None."""
    if not user or not user.is_authenticated:
        return None
    try:
        role = user.profile.role
        return role.name if role else None
    except Exception:
        return None


def has_role(user, *roles):
    """Проверяет входит ли роль пользователя в переданный список."""
    return get_user_role(user) in roles


def can_edit(user):
    """Может создавать и редактировать статьи/категории."""
    return has_role(user, ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)


def can_delete(user):
    """Может удалять статьи и категории."""
    return has_role(user, ROLE_ADMIN, ROLE_MANAGER)


def can_edit_schedule(user):
    """Может редактировать и загружать график дежурств."""
    return has_role(user, ROLE_ADMIN, ROLE_MANAGER)


def role_required(*allowed_roles):
    """
    Декоратор — пускает только пользователей с указанными ролями.
    Если роль не подходит — возвращает 403.
    Если роли нет вообще — тоже 403 (нет роли = Читатель, но не редактор).
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role not in allowed_roles:
                return HttpResponseForbidden(
                    '<h2>403 — Недостаточно прав</h2>'
                    '<p>У вас нет доступа к этому действию.</p>'
                    '<a href="javascript:history.back()">← Назад</a>'
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator