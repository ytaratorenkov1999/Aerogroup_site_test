# aeroflot/tests.py
#
# Тесты для приложения aeroflot:
#   - Доступ к страницам
#   - Ролевые ограничения (create/edit/delete категорий и статей)
#   - Счётчик просмотров
#   - Ознакомление со статьёй
#   - Уведомления API
#   - Поиск
#   - Структура базы знаний (2 SQL-запроса)
#   - Модели
#
# Положить в: aeroflot/tests.py  (заменить пустой файл)

import json

from django.test import TestCase
from django.urls import reverse

from aeroflot.models import (
    BdAeroflotCategory, BdAeroflotArticle,
    ArticleNotification, ArticleAcknowledgement,
)
from support.tests_helpers import make_user, LoginMixin
from support.roles import ROLE_READER, ROLE_EDITOR, ROLE_MANAGER, ROLE_ADMIN, ROLE_EXTERNAL


# ════════════════════════════════════════════════════════════════════════════
# Фабрики данных
# ════════════════════════════════════════════════════════════════════════════

def make_category(name='Тест категория', creator=None):
    return BdAeroflotCategory.objects.create(name=name, creator=creator)


def make_article(category, title='Тест статья', creator=None):
    return BdAeroflotArticle.objects.create(
        title=title,
        content='Содержание тестовой статьи.',
        category=category,
        creator=creator,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. Доступ к основным страницам
# ════════════════════════════════════════════════════════════════════════════

class KnowledgebaseAccessTests(LoginMixin, TestCase):

    def test_anonymous_redirected(self):
        response = self.client.get(reverse('aeroflot:index'))
        self.assertEqual(response.status_code, 302)

    def test_reader_can_view_main_page(self):
        user = make_user('afl1', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('aeroflot:index'))
        self.assertEqual(response.status_code, 200)

    def test_external_can_view_main_page(self):
        # Внешний видит главную, но в меню у него только home
        user = make_user('afl2', ROLE_EXTERNAL)
        self.login(user)
        response = self.client.get(reverse('aeroflot:index'))
        self.assertEqual(response.status_code, 200)

    def test_category_detail_accessible_to_reader(self):
        creator = make_user('afl_cr', ROLE_EDITOR)
        cat = make_category(creator=creator)
        user = make_user('afl3', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('aeroflot:category_detail', args=[cat.slug]))
        self.assertEqual(response.status_code, 200)

    def test_article_detail_accessible_to_reader(self):
        creator = make_user('afl_cr2', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = make_article(cat, creator=creator)
        user = make_user('afl4', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('aeroflot:article_detail', args=[article.slug]))
        self.assertEqual(response.status_code, 200)


# ════════════════════════════════════════════════════════════════════════════
# 2. Создание категорий — ролевая защита
# ════════════════════════════════════════════════════════════════════════════

class CategoryCreateTests(LoginMixin, TestCase):

    def test_reader_gets_403_on_category_create(self):
        user = make_user('cc1', ROLE_READER)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_create'),
            {'name': 'Запрещённая категория'},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_category(self):
        user = make_user('cc2', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_create'),
            {'name': 'Новая категория', 'description': ''},
        )
        self.assertRedirects(response, reverse('aeroflot:index'))
        self.assertTrue(BdAeroflotCategory.objects.filter(name='Новая категория').exists())

    def test_manager_can_create_category(self):
        user = make_user('cc3', ROLE_MANAGER)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_create'),
            {'name': 'Категория менеджера', 'description': ''},
        )
        self.assertRedirects(response, reverse('aeroflot:index'))

    def test_empty_name_shows_form_again(self):
        user = make_user('cc4', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_create'),
            {'name': ''},
        )
        # Пустое имя — редиректит на главную с сообщением об ошибке
        self.assertRedirects(response, reverse('aeroflot:index'))
        self.assertFalse(BdAeroflotCategory.objects.filter(name='').exists())

    def test_anonymous_redirected_from_create(self):
        response = self.client.get(reverse('aeroflot:category_create'))
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 3. Удаление категорий — ролевая защита
# ════════════════════════════════════════════════════════════════════════════

class CategoryDeleteTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('cd_cr', ROLE_EDITOR)
        self.cat = make_category(creator=self.creator)

    def test_editor_gets_403_on_delete(self):
        user = make_user('cd1', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_delete', args=[self.cat.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete_category(self):
        user = make_user('cd2', ROLE_MANAGER)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:category_delete', args=[self.cat.id])
        )
        self.assertRedirects(response, reverse('aeroflot:index'))
        self.assertFalse(BdAeroflotCategory.objects.filter(id=self.cat.id).exists())

    def test_get_not_allowed(self):
        user = make_user('cd3', ROLE_MANAGER)
        self.login(user)
        response = self.client.get(
            reverse('aeroflot:category_delete', args=[self.cat.id])
        )
        self.assertEqual(response.status_code, 405)


# ════════════════════════════════════════════════════════════════════════════
# 4. Создание статей
# ════════════════════════════════════════════════════════════════════════════

class ArticleCreateTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('ac_cr', ROLE_EDITOR)
        self.cat = make_category(creator=self.creator)

    def test_reader_gets_403(self):
        user = make_user('ac1', ROLE_READER)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_create'),
            {'title': 'x', 'content': 'x', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_article(self):
        user = make_user('ac2', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_create'),
            {'title': 'Новая статья', 'content': 'Текст статьи', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BdAeroflotArticle.objects.filter(title='Новая статья').exists())

    def test_creator_auto_acknowledged(self):
        """Создатель статьи автоматически считается ознакомленным."""
        user = make_user('ac3', ROLE_EDITOR)
        self.login(user)
        self.client.post(
            reverse('aeroflot:article_create'),
            {'title': 'Авто-ознакомление', 'content': 'Текст', 'category_id': self.cat.id},
        )
        article = BdAeroflotArticle.objects.get(title='Авто-ознакомление')
        self.assertTrue(ArticleAcknowledgement.objects.filter(article=article, user=user).exists())

    def test_empty_title_shows_form(self):
        user = make_user('ac4', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_create'),
            {'title': '', 'content': 'Текст', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('form_errors', response.context)

    def test_empty_content_shows_form(self):
        user = make_user('ac5', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_create'),
            {'title': 'Заголовок', 'content': '', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 200)


# ════════════════════════════════════════════════════════════════════════════
# 5. Удаление статей
# ════════════════════════════════════════════════════════════════════════════

class ArticleDeleteTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('ad_cr', ROLE_EDITOR)
        self.cat = make_category(creator=self.creator)
        self.article = make_article(self.cat, creator=self.creator)

    def test_editor_gets_403_on_delete(self):
        user = make_user('ad1', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_delete', args=[self.article.slug])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete_article(self):
        user = make_user('ad2', ROLE_MANAGER)
        self.login(user)
        response = self.client.post(
            reverse('aeroflot:article_delete', args=[self.article.slug])
        )
        self.assertFalse(BdAeroflotArticle.objects.filter(id=self.article.id).exists())


# ════════════════════════════════════════════════════════════════════════════
# 6. Счётчик просмотров
# ════════════════════════════════════════════════════════════════════════════

class ViewsCountTests(LoginMixin, TestCase):

    def test_views_count_increments_for_non_creator(self):
        creator = make_user('vc_cr', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = make_article(cat, creator=creator)
        initial_views = article.views_count

        reader = make_user('vc_rd', ROLE_READER)
        self.login(reader)
        self.client.get(reverse('aeroflot:article_detail', args=[article.slug]))
        article.refresh_from_db()
        self.assertEqual(article.views_count, initial_views + 1)

    def test_views_count_not_incremented_for_creator(self):
        creator = make_user('vc_cr2', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = make_article(cat, creator=creator)
        initial_views = article.views_count

        self.login(creator)
        self.client.get(reverse('aeroflot:article_detail', args=[article.slug]))
        article.refresh_from_db()
        self.assertEqual(article.views_count, initial_views)


# ════════════════════════════════════════════════════════════════════════════
# 7. Ознакомление со статьёй
# ════════════════════════════════════════════════════════════════════════════

class ArticleAcknowledgeTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('ack_cr', ROLE_EDITOR)
        self.cat = make_category(creator=self.creator)
        self.article = make_article(self.cat, creator=self.creator)
        self.url = reverse('aeroflot:article_acknowledge', args=[self.article.slug])

    def test_acknowledge_creates_record(self):
        user = make_user('ack1', ROLE_READER)
        self.login(user)
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['already'])
        self.assertTrue(ArticleAcknowledgement.objects.filter(article=self.article, user=user).exists())

    def test_repeated_acknowledge_returns_already_true(self):
        user = make_user('ack2', ROLE_READER)
        ArticleAcknowledgement.objects.create(article=self.article, user=user)
        self.login(user)
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['already'])

    def test_get_not_allowed(self):
        user = make_user('ack3', ROLE_READER)
        self.login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_anonymous_redirected(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 8. Уведомления
# ════════════════════════════════════════════════════════════════════════════

class NotificationsAPITests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('notif_cr', ROLE_EDITOR)
        self.cat = make_category(creator=self.creator)
        self.article = make_article(self.cat, creator=self.creator)
        self.user = make_user('notif_rd', ROLE_READER)
        self.notif = ArticleNotification.objects.create(
            recipient=self.user,
            actor=self.creator,
            article=self.article,
            action='created',
        )

    def test_notifications_returns_json(self):
        self.login(self.user)
        response = self.client.get(reverse('aeroflot:notifications_api'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('notifications', data)
        self.assertIn('unread_count', data)

    def test_unread_count_correct(self):
        self.login(self.user)
        response = self.client.get(reverse('aeroflot:notifications_api'))
        data = json.loads(response.content)
        self.assertEqual(data['unread_count'], 1)

    def test_notification_read_marks_as_read(self):
        self.login(self.user)
        response = self.client.post(
            reverse('aeroflot:notification_read', args=[self.notif.id])
        )
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_notification_delete(self):
        self.login(self.user)
        self.client.post(reverse('aeroflot:notification_delete', args=[self.notif.id]))
        self.assertFalse(ArticleNotification.objects.filter(id=self.notif.id).exists())

    def test_other_user_cannot_read_notification(self):
        other = make_user('notif_other', ROLE_READER)
        self.login(other)
        response = self.client.post(
            reverse('aeroflot:notification_read', args=[self.notif.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_redirected_from_notifications(self):
        response = self.client.get(reverse('aeroflot:notifications_api'))
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 9. Поиск
# ════════════════════════════════════════════════════════════════════════════

class KnowledgeSearchTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('srch1', ROLE_READER)
        self.login(self.user)
        creator = make_user('srch_cr', ROLE_EDITOR)
        cat = make_category(creator=creator)
        make_article(cat, title='Уникальный заголовок XYZ', creator=creator)

    def test_search_returns_results(self):
        response = self.client.get(reverse('aeroflot:search') + '?q=Уникальный')
        data = json.loads(response.content)
        self.assertEqual(len(data['results']), 1)
        self.assertIn('XYZ', data['results'][0]['title'])

    def test_short_query_returns_empty(self):
        response = self.client.get(reverse('aeroflot:search') + '?q=а')
        data = json.loads(response.content)
        self.assertEqual(data['results'], [])

    def test_no_query_returns_empty(self):
        response = self.client.get(reverse('aeroflot:search'))
        data = json.loads(response.content)
        self.assertEqual(data['results'], [])

    def test_anonymous_redirected(self):
        self.client.logout()
        response = self.client.get(reverse('aeroflot:search') + '?q=test')
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 10. get_knowledge_structure
# ════════════════════════════════════════════════════════════════════════════

class KnowledgeStructureTests(LoginMixin, TestCase):

    def test_structure_returns_json(self):
        user = make_user('ks1', ROLE_READER)
        creator = make_user('ks_cr', ROLE_EDITOR)
        cat = make_category(creator=creator)
        make_article(cat, creator=creator)
        self.login(user)
        response = self.client.get(reverse('aeroflot:get_structure'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('structure', data)
        self.assertIsInstance(data['structure'], list)

    def test_structure_contains_category(self):
        user = make_user('ks2', ROLE_READER)
        creator = make_user('ks_cr2', ROLE_EDITOR)
        cat = make_category(name='Особая категория', creator=creator)
        self.login(user)
        response = self.client.get(reverse('aeroflot:get_structure'))
        data = json.loads(response.content)
        names = [c['name'] for c in data['structure']]
        self.assertIn('Особая категория', names)


# ════════════════════════════════════════════════════════════════════════════
# 11. Модели
# ════════════════════════════════════════════════════════════════════════════

class AeroflotModelTests(TestCase):

    def test_category_slug_auto_generated(self):
        creator = make_user('mdl_cr', ROLE_EDITOR)
        cat = BdAeroflotCategory.objects.create(name='Тест авто-слаг', creator=creator)
        self.assertTrue(len(cat.slug) > 0)

    def test_article_slug_auto_generated(self):
        creator = make_user('mdl_cr2', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = BdAeroflotArticle.objects.create(
            title='Статья авто-слаг',
            content='Текст',
            category=cat,
            creator=creator,
        )
        self.assertTrue(len(article.slug) > 0)

    def test_category_str(self):
        creator = make_user('mdl_cr3', ROLE_EDITOR)
        cat = make_category(name='Моя категория', creator=creator)
        self.assertEqual(str(cat), 'Моя категория')

    def test_article_str(self):
        creator = make_user('mdl_cr4', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = make_article(cat, title='Моя статья', creator=creator)
        self.assertIn('Моя статья', str(article))

    def test_views_count_default_zero(self):
        creator = make_user('mdl_cr5', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = make_article(cat, creator=creator)
        self.assertEqual(article.views_count, 0)

    def test_get_content_as_html_renders_markdown(self):
        creator = make_user('mdl_cr6', ROLE_EDITOR)
        cat = make_category(creator=creator)
        article = BdAeroflotArticle.objects.create(
            title='Markdown', content='**жирный текст**',
            category=cat, creator=creator,
        )
        html = article.get_content_as_html()
        self.assertIn('<strong>', html)