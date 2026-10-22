import os
import re
import uuid
import logging
import markdown
import bleach

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.html import mark_safe
from django.core.exceptions import ValidationError
from transliterate import translit

logger = logging.getLogger(__name__)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

CATEGORY_CYCLE_ERROR = 'Нельзя выбрать родителем саму категорию или её подкатегорию'

def transliterate_to_slug(text):
    try:
        transliterated = translit(text, 'ru', reversed=True)
    except Exception:
        transliterated = text
    transliterated = re.sub(r'[^\w\s-]', '', transliterated.lower())
    transliterated = re.sub(r'[-\s]+', '-', transliterated)
    return transliterated.strip('-')


def generate_unique_slug(model_class, base_slug, exclude_id=None):
    slug = base_slug
    counter = 1
    qs = model_class.objects.filter(slug=slug)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    while qs.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
        qs = model_class.objects.filter(slug=slug)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
    return slug


def validate_file_size(file):
    max_size = 50 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(
            f'Размер файла не должен превышать 50 МБ. '
            f'Текущий размер: {file.size / (1024 * 1024):.2f} МБ'
        )


# ==================== МИКСИНЫ ====================

class SlugMixin(models.Model):
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        abstract = True

    def _get_slug_source(self):
        raise NotImplementedError

    def _get_slug_fallback_prefix(self):
        return 'item'

    def _get_slug_min_length(self):
        return 1

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = transliterate_to_slug(self._get_slug_source())
            if not base_slug or len(base_slug) < self._get_slug_min_length():
                base_slug = f"{self._get_slug_fallback_prefix()}-{uuid.uuid4().hex[:8]}"
            base_slug = base_slug[:240]
            self.slug = generate_unique_slug(self.__class__, base_slug, exclude_id=self.pk)
        super().save(*args, **kwargs)


class MarkdownContentMixin:
    ALLOWED_TAGS = [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'p', 'br', 'hr',
        'strong', 'em', 'del', 's',
        'ul', 'ol', 'li',
        'blockquote', 'pre', 'code',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'a', 'img',
        'div', 'span',
    ]

    ALLOWED_ATTRIBUTES = {
        'a':    ['href', 'title', 'target'],
        'img':  ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],
        'div':  ['class'],
        'span': ['class'],
        'th':   ['align'],
        'td':   ['align'],
    }

    def get_content_as_html(self):
        md = markdown.Markdown(extensions=[
            'fenced_code', 'codehilite', 'tables', 'nl2br', 'sane_lists'
        ])
        raw_html = md.convert(self.content)
        clean_html = bleach.clean(
            raw_html,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            strip=True,
            strip_comments=True,
        )
        return mark_safe(clean_html)


class AttachmentMixin(models.Model):
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    TEXT_EXTENSIONS  = ('.txt', '.log')

    class Meta:
        abstract = True

    def is_image(self):
        return self.file.name.lower().endswith(self.IMAGE_EXTENSIONS)

    def is_text(self):
        return self.file.name.lower().endswith(self.TEXT_EXTENSIONS)


# ==================== МОДЕЛИ БАЗЫ ЗНАНИЙ АФЛ ====================

class BdAeroflotCategory(SlugMixin):
    name        = models.CharField(max_length=255, verbose_name='Название категории')
    description = models.TextField(blank=True, verbose_name='Описание категории')
    parent      = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='subcategories', verbose_name='Родительская категория'
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    creator     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='bdafl_created_categories', verbose_name='Создатель'
    )

    class Meta:
        db_table = 'BdAeroflot_category'
        verbose_name = 'Категория БЗ Аэрофлот'
        verbose_name_plural = 'Категории БЗ Аэрофлот'
        ordering = ['name']

    def __str__(self):
        return self.name

    def _get_slug_source(self):
        return self.name

    def _get_slug_fallback_prefix(self):
        return 'category'

    def get_full_path(self):
        parts = []
        seen = set()
        node = self
        # seen — защита от зацикленных родителей в старых данных (иначе бесконечный цикл)
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parts.append(node.name)
            node = node.parent
        return ' → '.join(reversed(parts))

    def get_descendant_ids(self):
        """id всех подкатегорий на любой глубине (одним запросом, с защитой от циклов)."""
        children = {}
        for pk, parent_id in type(self).objects.values_list('id', 'parent_id'):
            children.setdefault(parent_id, []).append(pk)
        found, stack = set(), [self.pk]
        while stack:
            for child in children.get(stack.pop(), []):
                if child != self.pk and child not in found:
                    found.add(child)
                    stack.append(child)
        return found

    def is_valid_parent(self, parent_id):
        """Родителем нельзя сделать саму категорию или её подкатегорию — получится цикл."""
        if parent_id is None or self.pk is None:
            return True
        return parent_id != self.pk and parent_id not in self.get_descendant_ids()

    def clean(self):
        super().clean()
        if not self.is_valid_parent(self.parent_id):
            raise ValidationError({'parent': CATEGORY_CYCLE_ERROR})


class BdAeroflotArticle(SlugMixin, MarkdownContentMixin):
    title       = models.CharField(max_length=255, verbose_name='Название статьи')
    content     = models.TextField(verbose_name='Содержание статьи')
    category    = models.ForeignKey(
        BdAeroflotCategory, on_delete=models.CASCADE,
        related_name='articles', verbose_name='Категория'
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    creator     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='bdafl_created_articles', verbose_name='Создатель'
    )
    views_count = models.IntegerField(default=0, verbose_name='Количество просмотров')
    last_editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bdafl_edited_articles', verbose_name='Последний редактор'
    )

    class Meta:
        db_table = 'BdAeroflot_article'
        verbose_name = 'Статья БЗ Аэрофлот'
        verbose_name_plural = 'Статьи БЗ Аэрофлот'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def _get_slug_source(self):
        return self.title

    def _get_slug_fallback_prefix(self):
        return 'article'

    def _get_slug_min_length(self):
        return 3


class BdAeroflotAttachment(AttachmentMixin):
    # null — изображение загружено в редактор новой статьи, которая ещё не сохранена
    article    = models.ForeignKey(
        BdAeroflotArticle, on_delete=models.CASCADE, null=True, blank=True,
        related_name='attachments', verbose_name='Статья'
    )
    file       = models.FileField(
        upload_to='bdaeroflot_attachments/%Y/%m/%d/',
        verbose_name='Файл', validators=[validate_file_size]
    )
    file_name  = models.CharField(max_length=255, verbose_name='Название файла')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        db_table = 'BdAeroflot_attachment'
        verbose_name = 'Вложение БЗ Аэрофлот'
        verbose_name_plural = 'Вложения БЗ Аэрофлот'

    def __str__(self):
        if self.article is None:
            return f"Вложение без статьи: {self.file_name}"
        return f"Вложение к статье: {self.article.title}"


# ==================== ОЗНАКОМЛЕНИЕ СО СТАТЬЁЙ ====================

class ArticleAcknowledgement(models.Model):
    """Факт ознакомления сотрудника со статьёй"""
    article        = models.ForeignKey(
        BdAeroflotArticle, on_delete=models.CASCADE,
        related_name='acknowledgements', verbose_name='Статья'
    )
    user           = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='article_acknowledgements', verbose_name='Пользователь'
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата ознакомления')

    class Meta:
        db_table = 'BdAeroflot_acknowledgement'
        unique_together = ('article', 'user')
        verbose_name = 'Ознакомление со статьёй'
        verbose_name_plural = 'Ознакомления со статьями'

    def __str__(self):
        return f"{self.user} ознакомился с «{self.article.title}»"


# ==================== УВЕДОМЛЕНИЯ ====================

TECH_SUPPORT_DEPT = 'Отдел технической поддержки'


class ArticleNotification(models.Model):
    """Уведомление о создании/изменении статьи"""

    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Создана'),
        (ACTION_UPDATED, 'Изменена'),
    ]

    recipient   = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='article_notifications', verbose_name='Получатель'
    )
    article     = models.ForeignKey(
        BdAeroflotArticle, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Статья'
    )
    actor       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='sent_article_notifications', verbose_name='Автор действия'
    )
    action      = models.CharField(
        max_length=10, choices=ACTION_CHOICES, verbose_name='Действие'
    )
    is_read     = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        db_table = 'BdAeroflot_notification'
        verbose_name = 'Уведомление о статье'
        verbose_name_plural = 'Уведомления о статьях'
        ordering = ['-created_at']

    def __str__(self):
        return f"Уведомление для {self.recipient} — «{self.article.title}»"

    def get_actor_display_name(self):
        """ФИО если есть профиль, иначе логин"""
        try:
            full_name = self.actor.profile.full_name
            return full_name if full_name.strip() else self.actor.username
        except Exception:
            return self.actor.username if self.actor else '—'


# ==================== СИГНАЛЫ ====================

@receiver(post_delete, sender=BdAeroflotAttachment)
def _cleanup_attachment_file(instance, **kwargs):
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
                logger.debug("Файл удалён с диска: %s", instance.file.path)
        except Exception as e:
            logger.error("Не удалось удалить файл с диска: %s — %s", instance.file.path, e)


@receiver(post_save, sender=BdAeroflotArticle)
def _create_article_notifications(sender, instance, created, **kwargs):
    """
    При создании или изменении статьи рассылает уведомления
    всем сотрудникам отдела технической поддержки кроме автора.

    Уведомления НЕ отправляются если:
    - сохраняются только технические поля (views_count и т.п.)
    - явно передан флаг _skip_notifications=True
    """
    # Пропускаем технические сохранения (например обновление views_count)
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        content_fields = {'title', 'content', 'category', 'category_id', 'last_editor', 'last_editor_id'}
        if not content_fields.intersection(set(update_fields)):
            return

    # Пропускаем если явно выставлен флаг (например из Django admin без изменений)
    if getattr(instance, '_skip_notifications', False):
        return

    # Импорт здесь чтобы избежать circular import
    from support.models import EmployeeProfile

    action = ArticleNotification.ACTION_CREATED if created else ArticleNotification.ACTION_UPDATED
    actor  = instance.creator if created else (instance.last_editor or instance.creator)

    # Получаем всех сотрудников нужного отдела
    profiles = EmployeeProfile.objects.filter(
        department__name=TECH_SUPPORT_DEPT
    ).select_related('user')

    notifications = []
    for profile in profiles:
        recipient = profile.user
        # Не отправляем автору действия
        if actor and recipient == actor:
            continue
        notifications.append(ArticleNotification(
            recipient=recipient,
            article=instance,
            actor=actor,
            action=action,
        ))

    if notifications:
        # При обновлении статьи — удаляем старые непрочитанные уведомления
        # об этой же статье чтобы не засорять список дублями
        if action == ArticleNotification.ACTION_UPDATED:
            recipient_ids = [n.recipient_id for n in notifications]
            ArticleNotification.objects.filter(
                article=instance,
                recipient_id__in=recipient_ids,
                is_read=False,
                action=ArticleNotification.ACTION_UPDATED,
            ).delete()

        ArticleNotification.objects.bulk_create(notifications)
        logger.info(
            "Уведомления о статье id=%d '%s' (%s) разосланы %d получателям",
            instance.id, instance.title, action, len(notifications)
        )