# support/tests.py
#
# Тесты для приложения support:
#   - Ролевая логика (roles.py)
#   - Middleware блокировки /admin/
#   - Авторизация / выход
#   - Вьюхи: главная, профиль
#   - Контекстные процессоры
#
# Положить в: support/tests.py  (заменить пустой файл)

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from support.models import Department, Role, EmployeeProfile
from support.roles import (
    get_user_role, has_role, can_edit, can_delete, can_edit_schedule,
    ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR, ROLE_READER, ROLE_EXTERNAL,
)
from .tests_helpers import make_user, make_role, make_department, LoginMixin


# ════════════════════════════════════════════════════════════════════════════
# 1. Ролевая логика (roles.py)
# ════════════════════════════════════════════════════════════════════════════

class GetUserRoleTests(TestCase):

    def test_returns_role_name_for_user_with_role(self):
        user = make_user('u1', role_name=ROLE_EDITOR)
        self.assertEqual(get_user_role(user), ROLE_EDITOR)

    def test_returns_none_for_user_without_role(self):
        user = make_user('u2')          # профиль есть, роль — None
        self.assertIsNone(get_user_role(user))

    def test_returns_none_for_unauthenticated(self):
        # AnonymousUser не имеет is_authenticated=True
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(get_user_role(AnonymousUser()))

    def test_returns_none_for_none(self):
        self.assertIsNone(get_user_role(None))

    def test_returns_none_when_profile_missing(self):
        # Пользователь без профиля вообще
        user = User.objects.create_user('noprofile', password='x')
        self.assertIsNone(get_user_role(user))


class HasRoleTests(TestCase):

    def test_true_when_role_in_list(self):
        user = make_user('u3', role_name=ROLE_MANAGER)
        self.assertTrue(has_role(user, ROLE_ADMIN, ROLE_MANAGER))

    def test_false_when_role_not_in_list(self):
        user = make_user('u4', role_name=ROLE_READER)
        self.assertFalse(has_role(user, ROLE_ADMIN, ROLE_MANAGER))


class CanEditTests(TestCase):

    def test_admin_can_edit(self):
        self.assertTrue(can_edit(make_user('e1', ROLE_ADMIN)))

    def test_manager_can_edit(self):
        self.assertTrue(can_edit(make_user('e2', ROLE_MANAGER)))

    def test_editor_can_edit(self):
        self.assertTrue(can_edit(make_user('e3', ROLE_EDITOR)))

    def test_reader_cannot_edit(self):
        self.assertFalse(can_edit(make_user('e4', ROLE_READER)))

    def test_external_cannot_edit(self):
        self.assertFalse(can_edit(make_user('e5', ROLE_EXTERNAL)))

    def test_no_role_cannot_edit(self):
        self.assertFalse(can_edit(make_user('e6')))


class CanDeleteTests(TestCase):

    def test_admin_can_delete(self):
        self.assertTrue(can_delete(make_user('d1', ROLE_ADMIN)))

    def test_manager_can_delete(self):
        self.assertTrue(can_delete(make_user('d2', ROLE_MANAGER)))

    def test_editor_cannot_delete(self):
        self.assertFalse(can_delete(make_user('d3', ROLE_EDITOR)))

    def test_reader_cannot_delete(self):
        self.assertFalse(can_delete(make_user('d4', ROLE_READER)))


class CanEditScheduleTests(TestCase):

    def test_admin_can_edit_schedule(self):
        self.assertTrue(can_edit_schedule(make_user('s1', ROLE_ADMIN)))

    def test_manager_can_edit_schedule(self):
        self.assertTrue(can_edit_schedule(make_user('s2', ROLE_MANAGER)))

    def test_editor_cannot_edit_schedule(self):
        self.assertFalse(can_edit_schedule(make_user('s3', ROLE_EDITOR)))


# ════════════════════════════════════════════════════════════════════════════
# 2. AdminAccessMiddleware
# ════════════════════════════════════════════════════════════════════════════

class AdminAccessMiddlewareTests(LoginMixin, TestCase):

    def test_superuser_can_access_admin(self):
        user = make_user('su', is_superuser=True)
        self.login(user)
        response = self.client.get('/admin/')
        # Суперпользователь проходит в /admin/ (200 или редирект на login внутри admin)
        self.assertNotEqual(response.status_code, 403)

    def test_admin_role_can_access_admin(self):
        user = make_user('adm', ROLE_ADMIN)
        # Нужен is_staff=True чтобы Django admin пустил внутрь
        user.is_staff = True
        user.save()
        self.login(user)
        response = self.client.get('/admin/')
        self.assertNotEqual(response.status_code, 403)

    def test_reader_blocked_from_admin(self):
        user = make_user('rdr', ROLE_READER)
        self.login(user)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 403)

    def test_editor_blocked_from_admin(self):
        user = make_user('edt', ROLE_EDITOR)
        self.login(user)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 403)

    def test_manager_blocked_from_admin(self):
        user = make_user('mgr', ROLE_MANAGER)
        self.login(user)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 403)

    def test_external_blocked_from_admin(self):
        user = make_user('ext', ROLE_EXTERNAL)
        self.login(user)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 403)

    def test_anonymous_gets_admin_login(self):
        """Анонимный попадает на страницу входа Django-admin, не 403."""
        response = self.client.get('/admin/')
        # Django перенаправляет на /admin/login/ — не 403
        self.assertNotEqual(response.status_code, 403)


# ════════════════════════════════════════════════════════════════════════════
# 3. Авторизация (auth.py)
# ════════════════════════════════════════════════════════════════════════════

class AuthViewTests(TestCase):

    def setUp(self):
        self.user = make_user('loginuser', ROLE_READER, password='pass1234')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_successful_login_redirects_to_home(self):
        response = self.client.post(reverse('login'), {
            'login': 'loginuser',
            'password': 'pass1234',
        })
        self.assertRedirects(response, reverse('home'))

    def test_wrong_password_shows_error(self):
        response = self.client.post(reverse('login'), {
            'login': 'loginuser',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Неверный логин или пароль')

    def test_wrong_username_shows_error(self):
        response = self.client.post(reverse('login'), {
            'login': 'noexist',
            'password': 'pass1234',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Неверный логин или пароль')

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_logout_clears_session(self):
        self.client.force_login(self.user)
        self.client.get(reverse('logout'))
        # После выхода главная должна редиректить на логин
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '/login/?next=/')

    def test_session_expires_on_close_without_remember(self):
        """
        Без 'remember' вьюха вызывает session.set_expiry(0).
        Django test client хранит сессию в памяти, поэтому get_expiry_age()
        возвращает дефолтное значение (SESSION_COOKIE_AGE = 1209600),
        а не 0. Проверяем поведение через expire_date == None / get_expire_at_browser_close().
        """
        self.client.post(reverse('login'), {
            'login': 'loginuser',
            'password': 'pass1234',
        })
        # После set_expiry(0) флаг get_expire_at_browser_close() должен быть True
        self.assertTrue(self.client.session.get_expire_at_browser_close())


# ════════════════════════════════════════════════════════════════════════════
# 4. Основные вьюхи (views.py)
# ════════════════════════════════════════════════════════════════════════════

class IndexViewTests(LoginMixin, TestCase):

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '/login/?next=/')

    def test_logged_in_user_sees_home(self):
        user = make_user('homeusr', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)


class ProfileViewTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('profuser', ROLE_READER)
        self.login(self.user)

    def test_profile_page_loads(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)

    def test_profile_update_full_name(self):
        response = self.client.post(reverse('profile'), {
            'full_name': 'Иванов Иван',
            'email':     'ivan@test.com',
            'phone':     '',
            'position':  '',
        })
        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Иванов Иван')

    def test_profile_update_email(self):
        self.client.post(reverse('profile'), {
            'full_name': 'Тест profuser',
            'email':     'newemail@test.com',
            'phone':     '',
            'position':  '',
        })
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.email, 'newemail@test.com')

    def test_anonymous_redirected_from_profile(self):
        self.client.logout()
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, '/login/?next=/profile/')

    def test_profile_created_if_missing(self):
        """Если у юзера нет профиля — GET создаёт его автоматически."""
        user = User.objects.create_user('noprof2', password='pass')
        self.client.force_login(user)
        self.client.get(reverse('profile'))
        self.assertTrue(EmployeeProfile.objects.filter(user=user).exists())


# ════════════════════════════════════════════════════════════════════════════
# 5. Контекстные процессоры (context_processors.py)
# ════════════════════════════════════════════════════════════════════════════

class ContextProcessorTests(LoginMixin, TestCase):

    def test_full_menu_for_regular_user(self):
        user = make_user('ctx1', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('home'))
        menu = response.context.get('menu', [])
        url_names = [item['url_name'] for item in menu]
        self.assertIn('home', url_names)
        self.assertIn('stats_hd', url_names)

    def test_restricted_menu_for_external(self):
        user = make_user('ctx2', ROLE_EXTERNAL)
        self.login(user)
        response = self.client.get(reverse('home'))
        menu = response.context.get('menu', [])
        url_names = [item['url_name'] for item in menu]
        # Сторонний видит только главную
        self.assertIn('home', url_names)
        self.assertNotIn('stats_hd', url_names)

    def test_can_edit_in_context_for_editor(self):
        user = make_user('ctx3', ROLE_EDITOR)
        self.login(user)
        response = self.client.get(reverse('home'))
        self.assertTrue(response.context.get('can_edit'))

    def test_can_edit_false_for_reader(self):
        user = make_user('ctx4', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('home'))
        self.assertFalse(response.context.get('can_edit'))

    def test_can_delete_in_context_for_manager(self):
        user = make_user('ctx5', ROLE_MANAGER)
        self.login(user)
        response = self.client.get(reverse('home'))
        self.assertTrue(response.context.get('can_delete'))

    def test_empty_menu_for_anonymous(self):
        response = self.client.get(reverse('home'), follow=False)
        # Редирект — анонимный не получит контекст
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 6. Модели support
# ════════════════════════════════════════════════════════════════════════════

class EmployeeProfileModelTests(TestCase):

    def test_str_returns_full_name(self):
        user = make_user('strtest', ROLE_READER)
        profile = user.profile
        profile.full_name = 'Петров Пётр'
        profile.save()
        self.assertEqual(str(profile), 'Петров Пётр')

    def test_str_fallback_to_username(self):
        user = make_user('fallbackusr', ROLE_READER)
        profile = user.profile
        profile.full_name = ''
        profile.save()
        self.assertEqual(str(profile), 'fallbackusr')

    def test_get_photo_returns_default_when_no_photo(self):
        user = make_user('nophoto', ROLE_READER)
        self.assertIn('avatar_man', user.profile.get_photo())

    def test_department_fk(self):
        dept = make_department('Бухгалтерия')
        user = make_user('deptuser', ROLE_READER, department_name='Бухгалтерия')
        self.assertEqual(user.profile.department, dept)