"""
support/middleware.py

Middleware для блокировки Django-admin для всех кроме Администратора.
Подключить в settings.py в MIDDLEWARE после AuthenticationMiddleware:

    'support.middleware.AdminAccessMiddleware',
"""

from django.http import HttpResponseForbidden
from django.utils import translation
from .roles import get_user_role, ROLE_ADMIN


class AdminAccessMiddleware:
    """
    Блокирует доступ к /admin/ для всех кроме роли 'Администратор'.
    Суперпользователи (is_superuser) пропускаются без проверки роли.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            user = request.user
            if user.is_authenticated:
                # Суперпользователь всегда проходит
                if user.is_superuser:
                    return self.get_response(request)
                # Остальные — только если роль Администратор
                role = get_user_role(user)
                if role != ROLE_ADMIN:
                    return HttpResponseForbidden(
                        '<h2>403 — Доступ запрещён</h2>'
                        '<p>Раздел администрирования доступен только администраторам.</p>'
                        '<a href="/">← На главную</a>'
                    )
        return self.get_response(request)


class AdminRussianLocaleMiddleware:
    """
    Включает русский язык только для /admin/ — остальной сайт работает
    с LANGUAGE_CODE из settings без изменений.
    override() возвращает прежний язык после ответа, чтобы он не «залип»
    в потоке воркера для следующих запросов.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            with translation.override('ru'):
                return self.get_response(request)
        return self.get_response(request)
