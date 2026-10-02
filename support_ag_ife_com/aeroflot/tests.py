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
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from django.urls import reverse

from aeroflot.models import (
    CATEGORY_CYCLE_ERROR,
    BdAeroflotCategory, BdAeroflotArticle, BdAeroflotAttachment,
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


# ════════════════════════════════════════════════════════════════════════════
# 12. Изображения в редакторе новой статьи (pending-вложения)
# ════════════════════════════════════════════════════════════════════════════

PNG_1PX = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082'
)


class PendingImageUploadTests(LoginMixin, TestCase):
    """Изображение загружается до сохранения статьи — article_id ещё нет."""

    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self._override = override_settings(MEDIA_ROOT=self._media.name)
        self._override.enable()
        self.user = make_user('afl_img', ROLE_EDITOR)
        self.login(self.user)
        self.cat = make_category(creator=self.user)

    def tearDown(self):
        self._override.disable()
        self._media.cleanup()

    def _upload(self):
        return self.client.post(
            reverse('aeroflot:attachment_upload_image'),
            {'image': SimpleUploadedFile('pic.png', PNG_1PX, content_type='image/png')},
        )

    def test_upload_without_article_succeeds(self):
        response = self._upload()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        attachment = BdAeroflotAttachment.objects.get(id=data['attachment_id'])
        self.assertIsNone(attachment.article)
        self.assertIn(attachment.id, self.client.session['pending_image_attachments'])

    def test_pending_image_bound_to_created_article(self):
        attachment_id = self._upload().json()['attachment_id']
        self.client.post(
            reverse('aeroflot:article_create'),
            {'title': 'Статья с картинкой', 'content': 'Текст', 'category_id': self.cat.id},
        )
        article = BdAeroflotArticle.objects.get(title='Статья с картинкой')
        self.assertEqual(BdAeroflotAttachment.objects.get(id=attachment_id).article, article)

    def test_pending_image_can_be_deleted(self):
        attachment_id = self._upload().json()['attachment_id']
        response = self.client.post(
            reverse('aeroflot:attachment_delete_pending', args=[attachment_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BdAeroflotAttachment.objects.filter(id=attachment_id).exists())


# ════════════════════════════════════════════════════════════════════════════
# 13. Некорректные category_id / parent_id — без ошибки 500
# ════════════════════════════════════════════════════════════════════════════

class InvalidCategoryIdTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('afl_bad', ROLE_EDITOR)
        self.login(self.user)
        self.cat = make_category(creator=self.user)

    def test_article_create_with_bad_category_id_shows_form(self):
        for bad in ('abc', '999999', '-1'):
            response = self.client.post(
                reverse('aeroflot:article_create'),
                {'title': 'Статья', 'content': 'Текст', 'category_id': bad},
            )
            self.assertEqual(response.status_code, 200, bad)
            self.assertIn('category', response.context['form_errors'])
        self.assertFalse(BdAeroflotArticle.objects.filter(title='Статья').exists())

    def test_article_edit_with_bad_category_id_keeps_category(self):
        article = make_article(self.cat, creator=self.user)
        response = self.client.post(
            reverse('aeroflot:article_edit', args=[article.slug]),
            {'title': 'Новое', 'content': 'Текст', 'category_id': '999999'},
        )
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.category, self.cat)

    def test_category_create_with_bad_parent_id_redirects(self):
        for bad in ('abc', '999999'):
            response = self.client.post(
                reverse('aeroflot:category_create'), {'name': 'Подкатегория', 'parent_id': bad},
            )
            self.assertEqual(response.status_code, 302, bad)
        self.assertFalse(BdAeroflotCategory.objects.filter(name='Подкатегория').exists())

    def test_category_edit_with_bad_parent_id_keeps_parent(self):
        response = self.client.post(
            reverse('aeroflot:category_edit', args=[self.cat.id]), {'name': 'Новое имя', 'parent_id': 'abc'},
        )
        self.assertEqual(response.status_code, 302)
        self.cat.refresh_from_db()
        self.assertIsNone(self.cat.parent)
        self.assertNotEqual(self.cat.name, 'Новое имя')


# ════════════════════════════════════════════════════════════════════════════
# 14. Защита от зацикливания категорий
# ════════════════════════════════════════════════════════════════════════════

class CategoryCycleTests(LoginMixin, TestCase):

    def setUp(self):
        self.user = make_user('afl_cycle', ROLE_EDITOR)
        self.login(self.user)
        self.a = BdAeroflotCategory.objects.create(name='А', creator=self.user)
        self.b = BdAeroflotCategory.objects.create(name='Б', parent=self.a, creator=self.user)
        self.c = BdAeroflotCategory.objects.create(name='В', parent=self.b, creator=self.user)

    def _edit(self, category, parent):
        return self.client.post(
            reverse('aeroflot:category_edit', args=[category.id]),
            {'name': category.name, 'parent_id': parent.id},
        )

    def test_cannot_set_descendant_as_parent(self):
        for descendant in (self.b, self.c):
            response = self._edit(self.a, descendant)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['parent_error'], CATEGORY_CYCLE_ERROR)
        self.a.refresh_from_db()
        self.assertIsNone(self.a.parent)

    def test_cannot_set_self_as_parent(self):
        response = self._edit(self.b, self.b)
        self.assertEqual(response.status_code, 200)
        self.b.refresh_from_db()
        self.assertEqual(self.b.parent, self.a)

    def test_valid_parent_change_still_works(self):
        other = BdAeroflotCategory.objects.create(name='Другая', creator=self.user)
        self.assertEqual(self._edit(self.b, other).status_code, 302)
        self.b.refresh_from_db()
        self.assertEqual(self.b.parent, other)

    def test_edit_form_hides_self_and_descendants(self):
        response = self.client.get(reverse('aeroflot:category_edit', args=[self.a.id]))
        self.assertEqual(list(response.context['categories']), [])
        response = self.client.get(reverse('aeroflot:category_edit', args=[self.c.id]))
        self.assertEqual({c.name for c in response.context['categories']}, {'А', 'Б'})

    def test_admin_form_rejects_cycle(self):
        form = modelform_factory(BdAeroflotCategory, fields=['name', 'parent'])(
            data={'name': 'А', 'parent': self.c.id}, instance=self.a,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('parent', form.errors)

    def test_legacy_cycle_does_not_hang(self):
        """Цикл, уже записанный в БД старой версией, не вешает поиск и не прячет категории."""
        BdAeroflotCategory.objects.filter(pk=self.a.pk).update(parent=self.c)
        BdAeroflotArticle.objects.create(title='Статья про цикл', content='текст', category=self.b, creator=self.user)
        self.assertIn('А', self.c.get_full_path())
        response = self.client.get(reverse('aeroflot:search'), {'q': 'цикл'})
        self.assertEqual(len(response.json()['results']), 1)
        structure = self.client.get(reverse('aeroflot:get_structure')).json()['structure']
        names = set()
        def walk(nodes):
            for n in nodes:
                names.add(n['name']); walk(n['subcategories'])
        walk(structure)
        self.assertEqual(names, {'А', 'Б', 'В'})
        self.assertEqual(self.client.get(reverse('aeroflot:article_create')).status_code, 200)
