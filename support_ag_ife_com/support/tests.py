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

import os
import tempfile

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User

from aeroflot.models import BdAeroflotCategory
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

# ════════════════════════════════════════════════════════════════════════════
# 7. Админка: раздел «Сотрудники и регистрация пользователей»
# ════════════════════════════════════════════════════════════════════════════

class EmployeeAdminTests(LoginMixin, TestCase):

    def setUp(self):
        self.login(make_user('su_emp', is_superuser=True))

    def _profile_formset(self, **fields):
        data = {
            'profile-TOTAL_FORMS': '1', 'profile-INITIAL_FORMS': '0',
            'profile-MIN_NUM_FORMS': '1', 'profile-MAX_NUM_FORMS': '1',
        }
        data.update({f'profile-0-{k}': v for k, v in fields.items()})
        return data

    def test_index_shows_employees_section_only(self):
        content = self.client.get('/admin/').content.decode()
        self.assertIn('Сотрудники и регистрация пользователей', content)
        self.assertIn(reverse('admin:support_employee_changelist'), content)
        self.assertNotIn('/admin/auth/', content)
        self.assertNotIn('/admin/daily_schedule/', content)

    def test_create_user_with_profile_role_and_department_in_one_step(self):
        role = make_role(ROLE_EDITOR)
        dept = make_department('Отдел технической поддержки')
        data = {
            'username': 'new_employee',
            'usable_password': 'true',
            'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        }
        data.update(self._profile_formset(
            full_name='Иванов Иван', email='ivanov@example.com',
            role=role.id, department=dept.id, position='Инженер',
        ))
        response = self.client.post(reverse('admin:support_employee_add'), data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='new_employee')
        self.assertTrue(user.check_password('Str0ng-pass-123'))
        self.assertEqual(user.profile.full_name, 'Иванов Иван')
        self.assertEqual(user.profile.role, role)
        self.assertEqual(user.profile.department, dept)

    def test_profile_is_required(self):
        data = {
            'username': 'no_profile',
            'usable_password': 'true',
            'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        }
        data.update(self._profile_formset())
        response = self.client.post(reverse('admin:support_employee_add'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='no_profile').exists())

    def test_changelist_and_change_page_open(self):
        user = make_user('emp_view', ROLE_READER)
        self.assertEqual(
            self.client.get(reverse('admin:support_employee_changelist')).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse('admin:support_employee_change', args=[user.id])).status_code, 200
        )


class AdminLocaleTests(LoginMixin, TestCase):
    """Админка (django-unfold) на русском, остальной сайт — без изменений."""

    def test_admin_login_page_in_russian(self):
        content = self.client.get('/admin/login/').content.decode()
        self.assertIn('Добро пожаловать в', content)
        self.assertIn('Войти', content)

    def test_language_not_leaking_after_admin_request(self):
        from django.conf import settings
        from django.utils import translation
        self.client.get('/admin/login/')
        self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)

    def test_admin_login_without_next_redirects_to_admin_index(self):
        make_user('su_login', is_superuser=True, password='testpass123')
        response = self.client.post('/admin/login/', {'username': 'su_login', 'password': 'testpass123'})
        self.assertRedirects(response, reverse('admin:index'), fetch_redirect_response=False)


class RoleAccessLevelTests(TestCase):
    """Права зависят от уровня доступа (Role.code), а не от названия роли."""

    def test_renamed_role_keeps_permissions(self):
        user = make_user('renamed', ROLE_EDITOR)
        role = user.profile.role
        role.name = 'Контент-менеджер'
        role.save()
        user.refresh_from_db()
        self.assertEqual(get_user_role(user), ROLE_EDITOR)
        self.assertTrue(can_edit(user))

    def test_role_without_access_level_has_no_rights(self):
        role = Role.objects.create(name='Администратор')  # название без уровня доступа
        user = make_user('nocode')
        user.profile.role = role
        user.profile.save()
        self.assertIsNone(get_user_role(user))
        self.assertFalse(can_edit(user))

    def test_role_required_view_uses_access_level(self):
        user = make_user('renamed_mgr', ROLE_MANAGER)
        user.profile.role.name = 'Начальник смены'
        user.profile.role.save()
        self.client.force_login(user)
        cat = BdAeroflotCategory.objects.create(name='К')
        response = self.client.post(reverse('aeroflot:category_delete', args=[cat.id]))
        self.assertEqual(response.status_code, 302)


@override_settings(MEDIA_X_ACCEL=True)
class ProtectedMediaTests(LoginMixin, TestCase):
    """/media/ — только для вошедших; файл отдаёт nginx через X-Accel-Redirect."""

    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self._override = override_settings(MEDIA_ROOT=self._media.name)
        self._override.enable()
        os.makedirs(os.path.join(self._media.name, 'docs'))
        with open(os.path.join(self._media.name, 'docs', 'файл 1.pdf'), 'wb') as f:
            f.write(b'%PDF-1.4 test')

    def tearDown(self):
        self._override.disable()
        self._media.cleanup()

    def test_anonymous_redirected_to_login(self):
        response = self.client.get('/media/docs/файл 1.pdf')
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_logged_in_gets_x_accel_redirect(self):
        self.login(make_user('media_user', ROLE_READER))
        response = self.client.get('/media/docs/файл 1.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Accel-Redirect'], '/protected-media/docs/%D1%84%D0%B0%D0%B9%D0%BB%201.pdf')

    def test_missing_file_404(self):
        self.login(make_user('media_user2', ROLE_READER))
        self.assertEqual(self.client.get('/media/docs/nope.pdf').status_code, 404)

    def test_path_traversal_404(self):
        self.login(make_user('media_user3', ROLE_READER))
        self.assertEqual(self.client.get('/media/../manage.py').status_code, 404)
        self.assertEqual(self.client.get('/media/%2e%2e/manage.py').status_code, 404)

    @override_settings(MEDIA_X_ACCEL=False)
    def test_without_nginx_django_serves_file(self):
        self.login(make_user('media_user4', ROLE_READER))
        response = self.client.get('/media/docs/файл 1.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test')


# ════════════════════════════════════════════════════════════════════════════
# Ссылки на созвоны (MeetingLink) — главная страница берёт их из админки
# ════════════════════════════════════════════════════════════════════════════

from datetime import date, timedelta
import json

from django.core.management import call_command
from django.utils import timezone

from aeroflot.models import BdAeroflotArticle, ArticleAcknowledgement
from support.activity import (
    log_activity, build_activity_calendar, activity_stats, plural_ru,
)
from support.models import MeetingLink, UserActivity
from support.views import _next_birthday


class MeetingLinkTests(LoginMixin, TestCase):

    def setUp(self):
        MeetingLink.objects.all().delete()
        self.login(make_user('meet_user', ROLE_READER))

    def test_home_shows_active_links_only(self):
        MeetingLink.objects.create(title='Планёрка', url='https://telemost.yandex.ru/j/111', schedule='Пн–Пт, 10:00')
        MeetingLink.objects.create(title='Скрытая', url='https://zoom.us/j/222', is_active=False)
        content = self.client.get(reverse('home')).content.decode()
        self.assertIn('Планёрка', content)
        self.assertIn('https://telemost.yandex.ru/j/111', content)
        self.assertIn('Пн–Пт, 10:00', content)
        self.assertNotIn('https://zoom.us/j/222', content)

    def test_links_ordered(self):
        MeetingLink.objects.create(title='Вторая', url='https://a.ru/2', order=2)
        MeetingLink.objects.create(title='Первая', url='https://a.ru/1', order=1)
        content = self.client.get(reverse('home')).content.decode()
        self.assertLess(content.index('Первая'), content.index('Вторая'))

    def test_empty_state(self):
        content = self.client.get(reverse('home')).content.decode()
        self.assertIn('Ссылки на созвоны пока не добавлены', content)

    def test_platform_detected_by_url(self):
        self.assertEqual(MeetingLink(url='https://telemost.yandex.ru/j/1').platform, 'Яндекс Телемост')
        self.assertEqual(MeetingLink(url='https://us02web.zoom.us/j/1').platform, 'Zoom')
        self.assertEqual(MeetingLink(url='https://example.com/room').platform, 'Видеозвонок')

    def test_admin_link_shown_only_to_admin(self):
        manage_url = reverse('admin:support_meetinglink_changelist')
        self.assertNotIn(manage_url, self.client.get(reverse('home')).content.decode())
        self.login(make_user('meet_admin', ROLE_ADMIN))
        self.assertIn(manage_url, self.client.get(reverse('home')).content.decode())


class MeetingLinkMigrationTests(TestCase):

    def test_existing_links_moved_from_template(self):
        """Миграция переносит ссылки, которые раньше были зашиты в шаблон."""
        urls = set(MeetingLink.objects.values_list('url', flat=True))
        self.assertIn('https://telemost.yandex.ru/j/02129986235123', urls)
        self.assertIn('https://telemost.yandex.ru/j/43380988188792', urls)


class MeetingLinkAdminTests(LoginMixin, TestCase):

    def setUp(self):
        self.login(make_user('su_meet', is_superuser=True))

    def test_add_link_in_admin(self):
        response = self.client.post(reverse('admin:support_meetinglink_add'), {
            'title': 'Новый созвон', 'description': '', 'url': 'https://telemost.yandex.ru/j/999',
            'schedule': '', 'order': 5, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MeetingLink.objects.filter(url='https://telemost.yandex.ru/j/999').exists())

    def test_admin_pages_open(self):
        self.assertEqual(self.client.get(reverse('admin:support_meetinglink_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:support_useractivity_changelist')).status_code, 200)


# ════════════════════════════════════════════════════════════════════════════
# История активности
# ════════════════════════════════════════════════════════════════════════════

class LogActivityTests(TestCase):

    def setUp(self):
        self.user = make_user('act_user', ROLE_EDITOR)

    def test_creates_record(self):
        log_activity(self.user, UserActivity.ARTICLE_EDITED, 'Статья', 'БЗ Аэрофлот', '/a/')
        a = UserActivity.objects.get(user=self.user)
        self.assertEqual((a.action, a.target, a.section, a.url),
                         (UserActivity.ARTICLE_EDITED, 'Статья', 'БЗ Аэрофлот', '/a/'))

    def test_dedupe_window(self):
        for _ in range(3):
            log_activity(self.user, UserActivity.SCHEDULE_EDITED, '10.2026', dedupe_minutes=30)
        log_activity(self.user, UserActivity.SCHEDULE_EDITED, '11.2026', dedupe_minutes=30)
        self.assertEqual(UserActivity.objects.filter(user=self.user).count(), 2)

    def test_anonymous_ignored(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(log_activity(AnonymousUser(), UserActivity.PROFILE_UPDATED))
        self.assertFalse(UserActivity.objects.exists())

    def test_plural(self):
        self.assertEqual([plural_ru(n, ('день', 'дня', 'дней')) for n in (1, 2, 5, 11, 21, 22)],
                         ['день', 'дня', 'дней', 'дней', 'день', 'дня'])


class ActivityCalendarTests(TestCase):

    def setUp(self):
        self.user = make_user('cal_user', ROLE_EDITOR)
        self.today = timezone.localdate()

    def _add(self, days_ago, count=1):
        when = timezone.now() - timedelta(days=days_ago)
        for _ in range(count):
            UserActivity.objects.create(user=self.user, action=UserActivity.ARTICLE_EDITED, created_at=when)

    def test_grid_shape_and_levels(self):
        self._add(0, 2)
        self._add(3, 12)
        cal = build_activity_calendar(self.user, today=self.today)
        self.assertEqual(len(cal['weeks']), 53)
        self.assertTrue(all(len(w) == 7 for w in cal['weeks']))
        days = {d['date']: d for w in cal['weeks'] for d in w if d}
        self.assertEqual(max(days), self.today)
        self.assertEqual(days[self.today]['count'], 2)
        self.assertEqual(days[self.today]['level'], 1)
        self.assertEqual(days[self.today - timedelta(days=3)]['level'], 4)
        self.assertEqual(days[self.today - timedelta(days=1)]['level'], 0)
        # Будущие дни текущей недели — пустые
        self.assertEqual(sum(d is None for d in cal['weeks'][-1]), 6 - self.today.weekday())

    def test_month_labels_on_first_day(self):
        cal = build_activity_calendar(self.user, today=date(2026, 10, 22))
        labels = [m['label'] for m in cal['months']]
        self.assertEqual(labels[-1], 'Окт')
        self.assertIn('Янв', labels)

    def test_stats_streak(self):
        self._add(0)
        self._add(1, 3)
        self._add(2)
        self._add(10)
        stats = activity_stats(self.user, today=self.today)
        self.assertEqual(stats['streak'], 3)
        self.assertEqual(stats['month_total'], 6)
        self.assertEqual(stats['year_total'], 6)

    def test_streak_counts_from_yesterday_if_today_empty(self):
        self._add(1)
        self._add(2)
        self.assertEqual(activity_stats(self.user, today=self.today)['streak'], 2)


class ProfileActivityTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('pa_user', ROLE_EDITOR)
        self.login(self.user)

    def _post(self, **overrides):
        data = {'full_name': 'Тест pa_user', 'email': 'pa_user@test.com', 'phone': '', 'position': ''}
        data.update(overrides)
        return self.client.post(reverse('profile'), data)

    def test_profile_shows_activity(self):
        log_activity(self.user, UserActivity.ARTICLE_CREATED, 'Моя статья', 'БЗ Аэрофлот', '/x/')
        content = self.client.get(reverse('profile')).content.decode()
        self.assertIn('Последние действия', content)
        self.assertIn('Моя статья', content)
        self.assertIn('heatmap__cell lvl-1', content)

    def test_profile_change_logged(self):
        self._post(phone='+7 900 000-00-00')
        self.assertTrue(UserActivity.objects.filter(user=self.user, action=UserActivity.PROFILE_UPDATED).exists())

    def test_unchanged_profile_not_logged(self):
        self._post()
        self.assertFalse(UserActivity.objects.filter(user=self.user).exists())


class EmployeeProfileViewTests(LoginMixin, TestCase):

    def setUp(self):
        self.viewer = make_user('viewer', ROLE_READER)
        self.colleague = make_user('colleague', ROLE_EDITOR)
        log_activity(self.colleague, UserActivity.QUIZ_COMPLETED, 'Основы', 'Проверка знаний')
        self.login(self.viewer)

    def test_view_colleague_activity(self):
        response = self.client.get(reverse('employee_profile', args=['colleague']))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Тест colleague', content)
        self.assertIn('Основы', content)
        # Контакты коллеги не показываем
        self.assertNotIn('colleague@test.com', content)

    def test_own_username_redirects_to_profile(self):
        response = self.client.get(reverse('employee_profile', args=['viewer']))
        self.assertRedirects(response, reverse('profile'))

    def test_unknown_user_404(self):
        self.assertEqual(self.client.get(reverse('employee_profile', args=['nobody'])).status_code, 404)

    def test_external_role_cannot_view(self):
        self.login(make_user('ext_viewer', ROLE_EXTERNAL))
        self.assertEqual(self.client.get(reverse('employee_profile', args=['colleague'])).status_code, 404)


class HomeTeamWidgetsTests(LoginMixin, TestCase):

    def setUp(self):
        self.colleague = make_user('feed_author', ROLE_EDITOR)
        log_activity(self.colleague, UserActivity.ARTICLE_CREATED, 'Новая инструкция', 'БЗ Россия', '/r/')

    def test_team_feed_on_home(self):
        self.login(make_user('feed_reader', ROLE_READER))
        content = self.client.get(reverse('home')).content.decode()
        self.assertIn('Активность команды', content)
        self.assertIn('Новая инструкция', content)
        self.assertIn(reverse('employee_profile', args=['feed_author']), content)

    def test_external_role_sees_only_meetings(self):
        self.login(make_user('feed_ext', ROLE_EXTERNAL))
        content = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('Активность команды', content)
        self.assertNotIn('Новая инструкция', content)

    def test_upcoming_birthday_listed(self):
        soon = timezone.localdate() + timedelta(days=3)
        profile = self.colleague.profile
        profile.birthday = date(1992, soon.month, soon.day)  # 1992 — високосный, 29.02 тоже подходит
        profile.save()
        self.login(make_user('bday_reader', ROLE_READER))
        content = self.client.get(reverse('home')).content.decode()
        self.assertIn('Ближайшие дни рождения', content)
        self.assertIn('Тест feed_author', content)

    def test_next_birthday_feb_29(self):
        self.assertEqual(_next_birthday(date(2000, 2, 29), date(2027, 1, 10)), date(2027, 2, 28))
        self.assertEqual(_next_birthday(date(2000, 2, 29), date(2028, 1, 10)), date(2028, 2, 29))
        self.assertEqual(_next_birthday(date(1990, 5, 1), date(2026, 10, 22)), date(2027, 5, 1))


class ActivityHooksTests(LoginMixin, TestCase):
    """Действия в разделах сайта попадают в историю активности."""

    def setUp(self):
        self.editor = make_user('hook_editor', ROLE_EDITOR, 'Отдел технической поддержки')
        self.login(self.editor)
        self.category = BdAeroflotCategory.objects.create(name='Инструкции', creator=self.editor)

    def _actions(self, user=None):
        return list(UserActivity.objects.filter(user=user or self.editor).values_list('action', flat=True))

    def test_article_create_and_edit(self):
        self.client.post(reverse('aeroflot:article_create'), {
            'title': 'Как перезагрузить', 'content': 'Текст', 'category_id': self.category.id,
        })
        article = BdAeroflotArticle.objects.get(title='Как перезагрузить')
        self.client.post(reverse('aeroflot:article_edit', args=[article.slug]), {
            'title': 'Как перезагрузить', 'content': 'Новый текст', 'category_id': self.category.id,
        })
        self.assertEqual(sorted(self._actions()),
                         [UserActivity.ARTICLE_CREATED, UserActivity.ARTICLE_EDITED])
        a = UserActivity.objects.get(action=UserActivity.ARTICLE_CREATED)
        self.assertEqual(a.url, reverse('aeroflot:article_detail', args=[article.slug]))
        self.assertEqual(a.section, 'БЗ Аэрофлот')

    def test_acknowledge_logged_once(self):
        article = BdAeroflotArticle.objects.create(
            title='Регламент', content='x', category=self.category, creator=self.editor)
        reader = make_user('hook_reader', ROLE_READER)
        self.login(reader)
        url = reverse('aeroflot:article_acknowledge', args=[article.slug])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(self._actions(reader), [UserActivity.ARTICLE_ACKNOWLEDGED])

    def test_schedule_edits_collapsed(self):
        manager = make_user('hook_manager', ROLE_MANAGER, 'Отдел технической поддержки')
        self.login(manager)
        for day in ('2026-10-01', '2026-10-02', '2026-10-03'):
            self.client.post(reverse('schedule_save_entry'), data=json.dumps({
                'employee_id': self.editor.profile.id, 'date': day, 'status': 'working',
            }), content_type='application/json')
        self.assertEqual(self._actions(manager), [UserActivity.SCHEDULE_EDITED])


class BackfillActivityCommandTests(TestCase):

    def test_backfill_is_idempotent(self):
        author = make_user('bf_author', ROLE_EDITOR)
        reader = make_user('bf_reader', ROLE_READER)
        category = BdAeroflotCategory.objects.create(name='Категория', creator=author)
        article = BdAeroflotArticle.objects.create(
            title='Статья', content='x', category=category, creator=author)
        ArticleAcknowledgement.objects.create(article=article, user=author)
        ArticleAcknowledgement.objects.create(article=article, user=reader)

        call_command('backfill_activity', stdout=open(os.devnull, 'w'))
        call_command('backfill_activity', stdout=open(os.devnull, 'w'))

        self.assertEqual(
            sorted(UserActivity.objects.filter(user=author).values_list('action', flat=True)),
            [UserActivity.ARTICLE_CREATED, UserActivity.CATEGORY_CREATED],
        )
        ack = UserActivity.objects.get(user=reader)
        self.assertEqual(ack.action, UserActivity.ARTICLE_ACKNOWLEDGED)
        self.assertEqual(ack.created_at, ArticleAcknowledgement.objects.get(user=reader).acknowledged_at)
