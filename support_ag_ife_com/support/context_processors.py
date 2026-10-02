"""
support/context_processors.py

Передаёт в шаблоны:
  - menu        — сайдбар с учётом роли
  - user_menu   — меню профиля
  - user_photo  — фото текущего пользователя
  - user_role   — название роли текущего пользователя
  - can_edit    — bool: может редактировать контент
  - can_delete  — bool: может удалять контент
  - can_edit_schedule — bool: может редактировать график
"""

from .models import EmployeeProfile
from .roles import (
    get_user_role, can_edit, can_delete, can_edit_schedule,
    ROLE_EXTERNAL,
)

# Полный сайдбар — все пункты
_FULL_MENU = [
    {'title': 'Главная страница',    'url_name': 'home',           'icons': 'support/images/home.svg'},
    {'title': 'Статистика обращений','url_name': 'stats_hd',       'icons': 'support/images/statistic.svg'},
    {'title': 'База знаний Аэрофлот','url_name': 'aeroflot:index', 'icons': 'support/images/bd.svg'},
    {'title': 'База знаний Россия',  'url_name': 'russia:index',   'icons': 'support/images/bd.svg'},
    {'title': 'График дежурств',     'url_name': 'schedule',       'icons': 'support/images/daily.svg'},
    {'title': 'Проверка знаний',     'url_name': 'knowledge_check:knowledge', 'icons': 'support/images/check_knowledge.svg'},
    {'title': 'Обезличивание Аэрофлот', 'url_name': 'anonimaeroflot:anonimaeroflot','icons': 'support/images/shpion.svg'},
    {'title': 'Обезличивание Россия', 'url_name': 'anonimrussia:anonimrussia','icons': 'support/images/shpion.svg'},
]

# Сайдбар для стороннего отдела
_EXTERNAL_MENU = [
    {'title': 'Главная страница',    'url_name': 'home',           'icons': 'support/images/home.svg'},
    {'title': 'Обезличивание Аэрофлот', 'url_name': 'anonimaeroflot:anonimaeroflot','icons': 'support/images/shpion.svg'},
    {'title': 'Обезличивание Россия', 'url_name': 'anonimrussia:anonimrussia','icons': 'support/images/shpion.svg'},
]


def get_menu(request):
    """Возвращает пункты сайдбара в зависимости от роли."""
    if not request.user.is_authenticated:
        return {'menu': []}

    role = get_user_role(request.user)

    if role == ROLE_EXTERNAL:
        menu = _EXTERNAL_MENU
    else:
        menu = _FULL_MENU

    return {'menu': menu}


def get_svg_user(request):
    """Возвращает user_menu, user_photo, user_role и флаги прав."""
    svg_menu = [
        {'title': 'Профиль', 'url_name': 'profile', 'icons': 'support/images/profile.svg'},
        {'title': 'Выйти',   'url_name': 'logout',  'icons': 'support/images/logout.svg'},
    ]

    photo    = None
    role     = None

    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            photo   = profile.photo.url if profile.photo else None
            role    = profile.role.name if profile.role else None
        except EmployeeProfile.DoesNotExist:
            pass

    return {
        'user_menu':         svg_menu,
        'user_photo':        photo,
        'user_role':         role,
        'can_edit':          can_edit(request.user),
        'can_delete':        can_delete(request.user),
        'can_edit_schedule': can_edit_schedule(request.user),
    }