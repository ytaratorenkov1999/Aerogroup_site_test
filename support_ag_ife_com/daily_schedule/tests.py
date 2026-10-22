# daily_schedule/tests.py
#
# Тесты для приложения daily_schedule:
#   - Доступ к вьюхам
#   - get_data API
#   - save_entry: роли, валидация, логика
#   - import_schedule: формат файла
#   - Модели DailyTable
#
# Положить в: daily_schedule/tests.py  (заменить пустой файл)

import json
import io
from datetime import date

from django.test import TestCase
from django.urls import reverse

from daily_schedule.models import DailyTable
from support.models import EmployeeProfile, Department
from support.tests_helpers import make_user, make_department, LoginMixin
from support.roles import ROLE_READER, ROLE_EDITOR, ROLE_MANAGER, ROLE_ADMIN


# ════════════════════════════════════════════════════════════════════════════
# Вспомогательная функция
# ════════════════════════════════════════════════════════════════════════════

def make_employee_in_dept(username: str, role_name: str) -> EmployeeProfile:
    dept = make_department('Отдел технической поддержки')
    user = make_user(username, role_name=role_name, department_name='Отдел технической поддержки')
    return user.profile


# ════════════════════════════════════════════════════════════════════════════
# 1. Доступ к вьюхам
# ════════════════════════════════════════════════════════════════════════════

class ScheduleAccessTests(LoginMixin, TestCase):

    def test_anonymous_redirected_from_schedule(self):
        response = self.client.get(reverse('schedule'))
        self.assertEqual(response.status_code, 302)

    def test_reader_can_view_schedule(self):
        user = make_user('sch1', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('schedule'))
        self.assertEqual(response.status_code, 200)


# ════════════════════════════════════════════════════════════════════════════
# 2. get_data API
# ════════════════════════════════════════════════════════════════════════════

class GetDataTests(LoginMixin, TestCase):

    def setUp(self):
        self.emp = make_employee_in_dept('gd1', ROLE_READER)
        self.login(self.emp.user)
        self.url = reverse('schedule_get_data')

    def test_returns_employees_and_schedule(self):
        DailyTable.objects.create(
            employee=self.emp,
            date=date(2025, 6, 1),
            status='working',
        )
        response = self.client.get(self.url, {'year': 2025, 'month': 6})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('employees', data)
        self.assertIn('schedule', data)

    def test_invalid_params_return_error(self):
        response = self.client.get(self.url, {'year': 'abc', 'month': 'xyz'})
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_missing_params_return_error(self):
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_anonymous_redirected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_empty_month_returns_empty_schedule(self):
        response = self.client.get(self.url, {'year': 2000, 'month': 1})
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['schedule'], {})


# ════════════════════════════════════════════════════════════════════════════
# 3. save_entry — ролевая защита и логика
# ════════════════════════════════════════════════════════════════════════════

class SaveEntryTests(LoginMixin, TestCase):

    def setUp(self):
        self.emp = make_employee_in_dept('se_emp', ROLE_READER)
        self.url = reverse('schedule_save_entry')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def _login_as(self, role_name):
        user = make_user(f'se_{role_name}', role_name)
        self.login(user)
        return user

    def test_reader_gets_403(self):
        self._login_as(ROLE_READER)
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-01', 'status': 'working'})
        self.assertEqual(resp.status_code, 403)

    def test_editor_gets_403(self):
        self._login_as(ROLE_EDITOR)
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-01', 'status': 'working'})
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_save_entry(self):
        self._login_as(ROLE_MANAGER)
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-01', 'status': 'working'})
        data = json.loads(resp.content)
        self.assertTrue(data['success'])
        self.assertTrue(DailyTable.objects.filter(employee=self.emp, date=date(2025, 6, 1)).exists())

    def test_admin_can_save_entry(self):
        self._login_as(ROLE_ADMIN)
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-02', 'status': 'vacation'})
        data = json.loads(resp.content)
        self.assertTrue(data['success'])

    def test_save_updates_existing_entry(self):
        DailyTable.objects.create(employee=self.emp, date=date(2025, 6, 3), status='working')
        self._login_as(ROLE_MANAGER)
        self._post({'employee_id': self.emp.id, 'date': '2025-06-03', 'status': 'vacation'})
        entry = DailyTable.objects.get(employee=self.emp, date=date(2025, 6, 3))
        self.assertEqual(entry.status, 'vacation')

    def test_empty_status_deletes_entry(self):
        DailyTable.objects.create(employee=self.emp, date=date(2025, 6, 4), status='working')
        self._login_as(ROLE_MANAGER)
        self._post({'employee_id': self.emp.id, 'date': '2025-06-04', 'status': ''})
        self.assertFalse(DailyTable.objects.filter(employee=self.emp, date=date(2025, 6, 4)).exists())

    def test_invalid_status_returns_error(self):
        self._login_as(ROLE_MANAGER)
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-05', 'status': 'invalid_status'})
        data = json.loads(resp.content)
        self.assertFalse(data['success'])

    def test_invalid_date_format_returns_error(self):
        self._login_as(ROLE_MANAGER)
        resp = self._post({'employee_id': self.emp.id, 'date': 'not-a-date', 'status': 'working'})
        data = json.loads(resp.content)
        self.assertFalse(data['success'])

    def test_nonexistent_employee_returns_error(self):
        self._login_as(ROLE_MANAGER)
        resp = self._post({'employee_id': 999999, 'date': '2025-06-06', 'status': 'working'})
        data = json.loads(resp.content)
        self.assertFalse(data['success'])

    def test_get_method_not_allowed(self):
        self._login_as(ROLE_MANAGER)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_anonymous_redirected(self):
        resp = self._post({'employee_id': self.emp.id, 'date': '2025-06-01', 'status': 'working'})
        self.assertEqual(resp.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 4. import_schedule
# ════════════════════════════════════════════════════════════════════════════

class ImportScheduleTests(LoginMixin, TestCase):

    def setUp(self):
        self.url = reverse('schedule_import')

    def test_reader_gets_403(self):
        user = make_user('imp1', ROLE_READER)
        self.login(user)
        resp = self.client.post(self.url, {'file': io.BytesIO(b'fake')})
        self.assertEqual(resp.status_code, 403)

    def test_manager_without_file_returns_error(self):
        user = make_user('imp2', ROLE_MANAGER)
        self.login(user)
        resp = self.client.post(self.url, {})
        data = json.loads(resp.content)
        self.assertFalse(data['success'])

    def test_manager_with_wrong_format_returns_error(self):
        user = make_user('imp3', ROLE_MANAGER)
        self.login(user)
        fake_file = io.BytesIO(b'not xlsx content')
        fake_file.name = 'schedule.csv'
        resp = self.client.post(self.url, {'file': fake_file})
        data = json.loads(resp.content)
        self.assertFalse(data['success'])

    def test_anonymous_redirected(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        user = make_user('imp4', ROLE_MANAGER)
        self.login(user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)


# ════════════════════════════════════════════════════════════════════════════
# 5. Модели DailyTable
# ════════════════════════════════════════════════════════════════════════════

class DailyTableModelTests(TestCase):

    def setUp(self):
        self.emp = make_employee_in_dept('dt_emp', ROLE_READER)

    def test_str_contains_employee_name(self):
        entry = DailyTable.objects.create(
            employee=self.emp,
            date=date(2025, 7, 1),
            status='working',
        )
        self.assertIn(self.emp.full_name, str(entry))

    def test_unique_together_employee_date(self):
        DailyTable.objects.create(employee=self.emp, date=date(2025, 7, 2), status='working')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            DailyTable.objects.create(employee=self.emp, date=date(2025, 7, 2), status='vacation')

    def test_all_statuses_are_valid(self):
        valid = [s[0] for s in DailyTable.STATUS_CHOICES]
        self.assertIn('working', valid)
        self.assertIn('working_holiday', valid)
        self.assertIn('vacation', valid)