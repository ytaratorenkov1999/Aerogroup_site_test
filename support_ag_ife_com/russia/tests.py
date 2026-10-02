# russia/tests.py
#
# Тесты для приложения russia.
# Структура зеркалит aeroflot/tests.py, но использует russia-модели и урлы.
#
# Положить в: russia/tests.py  (заменить пустой файл)

import json

from django.test import TestCase
from django.urls import reverse

from russia.models import (
    BdRussiaCategory, BdRussiaArticle,
    RussiaArticleNotification, RussiaArticleAcknowledgement,
)
from support.tests_helpers import make_user, LoginMixin
from support.roles import ROLE_READER, ROLE_EDITOR, ROLE_MANAGER, ROLE_ADMIN


# ════════════════════════════════════════════════════════════════════════════
# Фабрики
# ════════════════════════════════════════════════════════════════════════════

def make_russia_category(name='Россия-категория', creator=None):
    return BdRussiaCategory.objects.create(name=name, creator=creator)


def make_russia_article(category, title='Россия-статья', creator=None):
    return BdRussiaArticle.objects.create(
        title=title,
        content='Содержание статьи Russia.',
        category=category,
        creator=creator,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. Доступ
# ════════════════════════════════════════════════════════════════════════════

class RussiaKnowledgebaseAccessTests(LoginMixin, TestCase):

    def test_anonymous_redirected(self):
        response = self.client.get(reverse('russia:index'))
        self.assertEqual(response.status_code, 302)

    def test_reader_can_view_main_page(self):
        user = make_user('ru1', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('russia:index'))
        self.assertEqual(response.status_code, 200)

    def test_category_detail_accessible(self):
        creator = make_user('ru_cr', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        user = make_user('ru2', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('russia:category_detail', args=[cat.slug]))
        self.assertEqual(response.status_code, 200)

    def test_article_detail_accessible(self):
        creator = make_user('ru_cr2', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        article = make_russia_article(cat, creator=creator)
        user = make_user('ru3', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('russia:article_detail', args=[article.slug]))
        self.assertEqual(response.status_code, 200)


# ════════════════════════════════════════════════════════════════════════════
# 2. Создание / удаление категорий
# ════════════════════════════════════════════════════════════════════════════

class RussiaCategoryCreateTests(LoginMixin, TestCase):

    def test_reader_gets_403(self):
        user = make_user('rcc1', ROLE_READER)
        self.login(user)
        response = self.client.post(
            reverse('russia:category_create'),
            {'name': 'Запрещённая'},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_category(self):
        user = make_user('rcc2', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('russia:category_create'),
            {'name': 'Новая Россия-категория', 'description': ''},
        )
        self.assertRedirects(response, reverse('russia:index'))
        self.assertTrue(BdRussiaCategory.objects.filter(name='Новая Россия-категория').exists())


class RussiaCategoryDeleteTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('rcd_cr', ROLE_EDITOR)
        self.cat = make_russia_category(creator=self.creator)

    def test_editor_gets_403_on_delete(self):
        user = make_user('rcd1', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('russia:category_delete', args=[self.cat.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete(self):
        user = make_user('rcd2', ROLE_MANAGER)
        self.login(user)
        self.client.post(reverse('russia:category_delete', args=[self.cat.id]))
        self.assertFalse(BdRussiaCategory.objects.filter(id=self.cat.id).exists())


# ════════════════════════════════════════════════════════════════════════════
# 3. Создание / удаление статей
# ════════════════════════════════════════════════════════════════════════════

class RussiaArticleCreateTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('rac_cr', ROLE_EDITOR)
        self.cat = make_russia_category(creator=self.creator)

    def test_reader_gets_403(self):
        user = make_user('rac1', ROLE_READER)
        self.login(user)
        response = self.client.post(
            reverse('russia:article_create'),
            {'title': 'x', 'content': 'x', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_article(self):
        user = make_user('rac2', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('russia:article_create'),
            {'title': 'Россия статья', 'content': 'Текст', 'category_id': self.cat.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BdRussiaArticle.objects.filter(title='Россия статья').exists())

    def test_creator_auto_acknowledged(self):
        user = make_user('rac3', ROLE_EDITOR)
        self.login(user)
        self.client.post(
            reverse('russia:article_create'),
            {'title': 'Авто-озн Россия', 'content': 'Текст', 'category_id': self.cat.id},
        )
        article = BdRussiaArticle.objects.get(title='Авто-озн Россия')
        self.assertTrue(
            RussiaArticleAcknowledgement.objects.filter(article=article, user=user).exists()
        )


class RussiaArticleDeleteTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('rad_cr', ROLE_EDITOR)
        self.cat = make_russia_category(creator=self.creator)
        self.article = make_russia_article(self.cat, creator=self.creator)

    def test_editor_gets_403(self):
        user = make_user('rad1', ROLE_EDITOR)
        self.login(user)
        response = self.client.post(
            reverse('russia:article_delete', args=[self.article.slug])
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete(self):
        user = make_user('rad2', ROLE_MANAGER)
        self.login(user)
        self.client.post(reverse('russia:article_delete', args=[self.article.slug]))
        self.assertFalse(BdRussiaArticle.objects.filter(id=self.article.id).exists())


# ════════════════════════════════════════════════════════════════════════════
# 4. Счётчик просмотров
# ════════════════════════════════════════════════════════════════════════════

class RussiaViewsCountTests(LoginMixin, TestCase):

    def test_views_increments_for_non_creator(self):
        creator = make_user('rvc_cr', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        article = make_russia_article(cat, creator=creator)
        reader = make_user('rvc_rd', ROLE_READER)
        self.login(reader)
        self.client.get(reverse('russia:article_detail', args=[article.slug]))
        article.refresh_from_db()
        self.assertEqual(article.views_count, 1)

    def test_views_not_incremented_for_creator(self):
        creator = make_user('rvc_cr2', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        article = make_russia_article(cat, creator=creator)
        self.login(creator)
        self.client.get(reverse('russia:article_detail', args=[article.slug]))
        article.refresh_from_db()
        self.assertEqual(article.views_count, 0)


# ════════════════════════════════════════════════════════════════════════════
# 5. Ознакомление
# ════════════════════════════════════════════════════════════════════════════

class RussiaAcknowledgeTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('rack_cr', ROLE_EDITOR)
        self.cat = make_russia_category(creator=self.creator)
        self.article = make_russia_article(self.cat, creator=self.creator)

    def test_acknowledge_creates_record(self):
        user = make_user('rack1', ROLE_READER)
        self.login(user)
        response = self.client.post(
            reverse('russia:article_acknowledge', args=[self.article.slug])
        )
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['already'])

    def test_repeated_acknowledge_returns_already(self):
        user = make_user('rack2', ROLE_READER)
        RussiaArticleAcknowledgement.objects.create(article=self.article, user=user)
        self.login(user)
        response = self.client.post(
            reverse('russia:article_acknowledge', args=[self.article.slug])
        )
        data = json.loads(response.content)
        self.assertTrue(data['already'])


# ════════════════════════════════════════════════════════════════════════════
# 6. Уведомления
# ════════════════════════════════════════════════════════════════════════════

class RussiaNotificationsTests(LoginMixin, TestCase):

    def setUp(self):
        self.creator = make_user('rn_cr', ROLE_EDITOR)
        self.cat = make_russia_category(creator=self.creator)
        self.article = make_russia_article(self.cat, creator=self.creator)
        self.user = make_user('rn_rd', ROLE_READER)
        self.notif = RussiaArticleNotification.objects.create(
            recipient=self.user,
            actor=self.creator,
            article=self.article,
            action='created',
        )

    def test_notifications_returns_json(self):
        self.login(self.user)
        response = self.client.get(reverse('russia:notifications_api'))
        data = json.loads(response.content)
        self.assertIn('notifications', data)

    def test_read_notification(self):
        self.login(self.user)
        self.client.post(reverse('russia:notification_read', args=[self.notif.id]))
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_delete_notification(self):
        self.login(self.user)
        self.client.post(reverse('russia:notification_delete', args=[self.notif.id]))
        self.assertFalse(RussiaArticleNotification.objects.filter(id=self.notif.id).exists())

    def test_other_user_gets_404_on_read(self):
        other = make_user('rn_other', ROLE_READER)
        self.login(other)
        response = self.client.post(
            reverse('russia:notification_read', args=[self.notif.id])
        )
        self.assertEqual(response.status_code, 404)


# ════════════════════════════════════════════════════════════════════════════
# 7. Поиск
# ════════════════════════════════════════════════════════════════════════════

class RussiaSearchTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('rsrch', ROLE_READER)
        self.login(self.user)
        creator = make_user('rsrch_cr', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        make_russia_article(cat, title='Уникальный ABC Россия', creator=creator)

    def test_search_finds_article(self):
        response = self.client.get(reverse('russia:search') + '?q=Уникальный')
        data = json.loads(response.content)
        self.assertEqual(len(data['results']), 1)

    def test_short_query_returns_empty(self):
        response = self.client.get(reverse('russia:search') + '?q=а')
        data = json.loads(response.content)
        self.assertEqual(data['results'], [])


# ════════════════════════════════════════════════════════════════════════════
# 8. Модели Russia
# ════════════════════════════════════════════════════════════════════════════

class RussiaModelTests(TestCase):

    def test_category_slug_auto_generated(self):
        creator = make_user('rm_cr', ROLE_EDITOR)
        cat = BdRussiaCategory.objects.create(name='Россия авто-слаг', creator=creator)
        self.assertTrue(len(cat.slug) > 0)

    def test_article_views_count_default_zero(self):
        creator = make_user('rm_cr2', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        article = make_russia_article(cat, creator=creator)
        self.assertEqual(article.views_count, 0)

    def test_markdown_rendered_to_html(self):
        creator = make_user('rm_cr3', ROLE_EDITOR)
        cat = make_russia_category(creator=creator)
        article = BdRussiaArticle.objects.create(
            title='MD Russia', content='**жирный**',
            category=cat, creator=creator,
        )
        html = article.get_content_as_html()
        self.assertIn('<strong>', html)