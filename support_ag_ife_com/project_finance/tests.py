# project_finance/tests.py
#
# Тесты раздела «Финансы проектов · Микросайты»:
#   - доступ только для Администратора (и суперпользователя)
#   - расчёт сумм (не в стоимости, оплачено / не оплачено)
#   - проекты, прайс-лист, задачи: создание, изменение, удаление
#   - удаление используемой позиции прайса с заменой

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from project_finance.models import MicrositeProject, PriceItem, Task, totals
from project_finance.templatetags.finance import rub
from support.roles import ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR, ROLE_READER, ROLE_EXTERNAL
from support.tests_helpers import make_user, LoginMixin


def make_project(name='Игры'):
    return MicrositeProject.objects.create(name=name)


def make_task(project, item=None, price='1500', **kw):
    return Task.objects.create(
        project=project, title=kw.pop('title', 'Задача'), price_item=item,
        service_name=item.name if item else '', price=Decimal(price) if price is not None else None,
        date=datetime.date(2026, 10, 2), **kw,
    )


class AccessTests(LoginMixin, TestCase):

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('project_finance:summary'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_non_admin_roles_forbidden(self):
        project = make_project()
        for i, role in enumerate((ROLE_MANAGER, ROLE_EDITOR, ROLE_READER, ROLE_EXTERNAL)):
            self.login(make_user(f'pf_user{i}', role))
            self.assertEqual(self.client.get(reverse('project_finance:summary')).status_code, 403, role)
            self.assertEqual(self.client.get(reverse('project_finance:project', args=[project.pk])).status_code, 403, role)
            response = self.client.post(reverse('project_finance:project_create'), {'name': 'X', 'status': 'active'})
            self.assertEqual(response.status_code, 403, role)
        self.assertFalse(MicrositeProject.objects.filter(name='X').exists())

    def test_admin_and_superuser_allowed(self):
        self.login(make_user('pf_admin', ROLE_ADMIN))
        self.assertEqual(self.client.get(reverse('project_finance:summary')).status_code, 200)
        self.login(make_user('pf_su', is_superuser=True))
        self.assertEqual(self.client.get(reverse('project_finance:summary')).status_code, 200)

    def test_menu_item_only_for_admin(self):
        url = reverse('project_finance:summary')
        self.login(make_user('pf_menu_admin', ROLE_ADMIN))
        self.assertContains(self.client.get(reverse('home')), url)
        self.login(make_user('pf_menu_mgr', ROLE_MANAGER))
        self.assertNotContains(self.client.get(reverse('home')), url)


class CalculationTests(TestCase):

    def test_amounts_and_totals(self):
        project = make_project()
        paid = make_task(project, price='1500', quantity=2, is_paid=True)
        due = make_task(project, price='2500')
        free = make_task(project, price='1000', is_free=True)
        self.assertEqual(paid.amount, Decimal('3000'))
        self.assertEqual(free.amount, Decimal('0'))
        self.assertEqual(free.full_amount, Decimal('1000'))
        self.assertEqual(totals([paid, due, free]), {'total': Decimal('5500'), 'paid': Decimal('3000'), 'due': Decimal('2500')})

    def test_task_numbers_per_project(self):
        a, b = make_project('А'), make_project('Б')
        self.assertEqual([make_task(a).number, make_task(a).number, make_task(b).number], [1, 2, 1])

    def test_rub_filter(self):
        self.assertEqual(rub(Decimal('1500')), '1 500 ₽')
        self.assertEqual(rub(Decimal('1234567.50')), '1 234 567,5 ₽')
        self.assertEqual(rub(None), '0 ₽')


class ManagementTests(LoginMixin, TestCase):

    def setUp(self):
        self.login(make_user('pf_mgmt', ROLE_ADMIN))
        self.project = make_project()

    def url(self, name, *args):
        return reverse(f'project_finance:{name}', args=args)

    def test_summary_shows_totals(self):
        item = PriceItem.objects.create(project=self.project, name='Добавить игру', price=Decimal('2500'))
        make_task(self.project, item, price='2500', is_paid=True)
        make_task(self.project, item, price='1500')
        response = self.client.get(self.url('summary'))
        row = response.context['rows'][0]
        self.assertEqual((row['total'], row['paid'], row['due']), (Decimal('4000'), Decimal('2500'), Decimal('1500')))
        self.assertContains(response, '4 000 ₽')

    def test_create_and_edit_project(self):
        response = self.client.post(self.url('project_create'), {'name': 'Викторины', 'description': '', 'status': 'active'})
        project = MicrositeProject.objects.get(name='Викторины')
        self.assertRedirects(response, self.url('project', project.pk), fetch_redirect_response=False)
        self.client.post(self.url('project_edit', project.pk), {'name': 'Викторины 2', 'description': 'Описание', 'status': 'archived'})
        project.refresh_from_db()
        self.assertEqual((project.name, project.status), ('Викторины 2', 'archived'))

    def test_delete_project_cascades(self):
        item = PriceItem.objects.create(project=self.project, name='Услуга', price=Decimal('100'))
        make_task(self.project, item)
        self.client.post(self.url('project_delete', self.project.pk))
        self.assertFalse(MicrositeProject.objects.exists())
        self.assertFalse(PriceItem.objects.exists())
        self.assertFalse(Task.objects.exists())

    def test_price_item_validation_and_negotiable(self):
        self.client.post(self.url('price_save', self.project.pk), {'name': 'Без цены'})
        self.assertFalse(PriceItem.objects.filter(name='Без цены').exists())
        self.client.post(self.url('price_save', self.project.pk), {'name': 'Иные доработки', 'price': '500', 'is_negotiable': 'on'})
        item = PriceItem.objects.get(name='Иные доработки')
        self.assertTrue(item.is_negotiable)
        self.assertIsNone(item.price)

    def test_editing_price_keeps_existing_task_price(self):
        item = PriceItem.objects.create(project=self.project, name='Слайдер', price=Decimal('1500'))
        task = make_task(self.project, item, price='1500')
        self.client.post(self.url('price_save', self.project.pk), {'item_id': item.pk, 'name': 'Слайдер', 'price': '2000'})
        item.refresh_from_db(); task.refresh_from_db()
        self.assertEqual(item.price, Decimal('2000'))
        self.assertEqual(task.price, Decimal('1500'))

    def test_delete_used_price_item_requires_replacement(self):
        old = PriceItem.objects.create(project=self.project, name='Старая', price=Decimal('100'))
        new = PriceItem.objects.create(project=self.project, name='Новая', price=Decimal('200'))
        task = make_task(self.project, old, price='100')
        self.client.post(self.url('price_delete', self.project.pk, old.pk))
        self.assertTrue(PriceItem.objects.filter(pk=old.pk).exists())
        self.client.post(self.url('price_delete', self.project.pk, old.pk), {'replace_with': new.pk})
        self.assertFalse(PriceItem.objects.filter(pk=old.pk).exists())
        task.refresh_from_db()
        self.assertEqual((task.price_item, task.service_name, task.price), (new, 'Новая', Decimal('100')))

    def test_price_item_of_other_project_rejected(self):
        other = make_project('Другой')
        foreign = PriceItem.objects.create(project=other, name='Чужая', price=Decimal('1'))
        self.client.post(self.url('task_save', self.project.pk), {
            'price_item': foreign.pk, 'title': 'T', 'price': '10', 'quantity': '1', 'date': '2026-10-02'})
        self.assertFalse(Task.objects.exists())

    def test_create_edit_task(self):
        item = PriceItem.objects.create(project=self.project, name='Добавить игру', price=Decimal('2500'))
        self.client.post(self.url('task_save', self.project.pk), {
            'price_item': item.pk, 'title': 'Игра Баскетбол', 'price': '2500', 'quantity': '1',
            'date': '2026-10-02', 'is_free': 'on'})
        task = Task.objects.get(title='Игра Баскетбол')
        self.assertEqual((task.number, task.service_name, task.amount), (1, 'Добавить игру', Decimal('0')))
        self.client.post(self.url('task_save', self.project.pk), {
            'task_id': task.pk, 'price_item': item.pk, 'title': 'Игра Баскетбол', 'price': '2500',
            'quantity': '2', 'date': '2026-10-03', 'is_paid': 'on'})
        task.refresh_from_db()
        self.assertEqual((task.quantity, task.is_free, task.is_paid, task.amount), (2, False, True, Decimal('5000')))
        self.assertIsNotNone(task.paid_at)

    def test_task_requires_price_unless_free(self):
        item = PriceItem.objects.create(project=self.project, name='Иные', is_negotiable=True)
        self.client.post(self.url('task_save', self.project.pk), {
            'price_item': item.pk, 'title': 'Без цены', 'quantity': '1', 'date': '2026-10-02'})
        self.assertFalse(Task.objects.exists())

    def test_toggle_paid_and_delete_task(self):
        task = make_task(self.project)
        self.client.post(self.url('task_toggle_paid', task.pk))
        task.refresh_from_db()
        self.assertTrue(task.is_paid)
        self.assertIsNotNone(task.paid_at)
        self.client.post(self.url('task_toggle_paid', task.pk))
        task.refresh_from_db()
        self.assertFalse(task.is_paid)
        self.assertIsNone(task.paid_at)
        self.client.post(self.url('task_delete', task.pk))
        self.assertFalse(Task.objects.exists())

    def test_get_not_allowed_for_changes(self):
        task = make_task(self.project)
        self.assertEqual(self.client.get(self.url('task_delete', task.pk)).status_code, 405)
        self.assertEqual(self.client.get(self.url('project_delete', self.project.pk)).status_code, 405)
