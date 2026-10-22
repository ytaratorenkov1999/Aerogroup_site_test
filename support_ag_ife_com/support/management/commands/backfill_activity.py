"""
Заполняет историю активности из уже существующих данных — чтобы календарь
в профилях не начинался с нуля после включения функции.

    python manage.py backfill_activity

Берёт: созданные статьи и категории обеих баз знаний, последнюю правку статьи,
ознакомления со статьями, завершённые проверки знаний.
Повторный запуск безопасен — уже перенесённые записи не дублируются.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse

from aeroflot.models import BdAeroflotArticle, BdAeroflotCategory, ArticleAcknowledgement
from knowledge_check.models import UserAttempt
from russia.models import BdRussiaArticle, BdRussiaCategory, RussiaArticleAcknowledgement
from support.models import UserActivity

KNOWLEDGE_BASES = [
    ('aeroflot', 'БЗ Аэрофлот', BdAeroflotCategory, BdAeroflotArticle, ArticleAcknowledgement),
    ('russia',   'БЗ Россия',   BdRussiaCategory,   BdRussiaArticle,   RussiaArticleAcknowledgement),
]


class Command(BaseCommand):
    help = 'Заполняет историю активности сотрудников из существующих данных'

    def handle(self, *args, **options):
        self.created = 0
        for app, section, Category, Article, Acknowledgement in KNOWLEDGE_BASES:
            for c in Category.objects.exclude(creator=None):
                self._add(c.creator, UserActivity.CATEGORY_CREATED, c.name, section, c.created_at,
                          reverse(f'{app}:category_detail', args=[c.slug]))

            for a in Article.objects.exclude(creator=None):
                self._add(a.creator, UserActivity.ARTICLE_CREATED, a.title, section, a.created_at,
                          reverse(f'{app}:article_detail', args=[a.slug]))

            # Сохраняется только последний редактор — переносим его правку
            for a in Article.objects.exclude(last_editor=None):
                if a.updated_at - a.created_at > timedelta(minutes=1):
                    self._add(a.last_editor, UserActivity.ARTICLE_EDITED, a.title, section, a.updated_at,
                              reverse(f'{app}:article_detail', args=[a.slug]))

            # Автор и редактор отмечаются ознакомившимися автоматически — это не отдельное действие
            for ack in Acknowledgement.objects.select_related('article'):
                if ack.user_id in (ack.article.creator_id, ack.article.last_editor_id):
                    continue
                self._add(ack.user, UserActivity.ARTICLE_ACKNOWLEDGED, ack.article.title, section,
                          ack.acknowledged_at, reverse(f'{app}:article_detail', args=[ack.article.slug]))

        attempts = (UserAttempt.objects
                    .filter(status=UserAttempt.STATUS_COMPLETED, finished_at__isnull=False)
                    .select_related('category'))
        for at in attempts:
            self._add(at.user, UserActivity.QUIZ_COMPLETED, at.category.name, 'Проверка знаний',
                      at.finished_at, reverse('knowledge_check:knowledge'))

        self.stdout.write(self.style.SUCCESS(f'Добавлено записей активности: {self.created}'))

    def _add(self, user, action, target, section, created_at, url):
        _, created = UserActivity.objects.get_or_create(
            user=user, action=action, target=target[:255], created_at=created_at,
            defaults={'section': section, 'url': url},
        )
        self.created += created
