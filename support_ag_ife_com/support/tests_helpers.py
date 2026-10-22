# support/tests_helpers.py
#
# Вспомогательные миксины и фабрики, которые используются во ВСЕХ test-файлах.
# Этот файл НЕ является самостоятельным тест-файлом — он только импортируется.
#
# Положить в: support/tests_helpers.py

from django.contrib.auth.models import User
from support.models import Department, Role, EmployeeProfile
from support.roles import ROLE_CHOICES


# ─── Фабрики ────────────────────────────────────────────────────────────────

def make_role(code: str) -> Role:
    """Возвращает (или создаёт) роль с уровнем доступа code (ROLE_*)."""
    role, _ = Role.objects.get_or_create(code=code, defaults={'name': dict(ROLE_CHOICES)[code]})
    return role


def make_department(name: str = 'Отдел технической поддержки') -> Department:
    dept, _ = Department.objects.get_or_create(name=name)
    return dept


def make_user(
    username: str,
    role_name: str | None = None,
    department_name: str | None = None,
    password: str = 'testpass123',
    is_superuser: bool = False,
) -> User:
    """
    Создаёт пользователя с профилем.
    Если role_name передан — привязывает роль.
    """
    if is_superuser:
        user = User.objects.create_superuser(username, password=password)
    else:
        user = User.objects.create_user(username, password=password)

    role = make_role(role_name) if role_name else None
    dept = make_department(department_name) if department_name else None

    EmployeeProfile.objects.create(
        user=user,
        full_name=f'Тест {username}',
        email=f'{username}@test.com',
        role=role,
        department=dept,
    )
    return user


# ─── Миксин ─────────────────────────────────────────────────────────────────

class LoginMixin:
    """
    Добавляет метод self.login(user) для удобного входа в тест-клиент.
    Используй в TestCase вместе с обычным self.client.
    """

    def login(self, user: User) -> None:
        self.client.force_login(user)