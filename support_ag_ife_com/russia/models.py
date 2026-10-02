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


# ==================== МОДЕЛИ БАЗЫ ЗНАНИЙ РОССИЯ ====================

class BdRussiaCategory(SlugMixin):
    """Категория базы знаний Россия"""

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
        related_name='bdrussia_created_categories', verbose_name='Создатель'
    )

    class Meta:
        db_table = 'BdRussia_category'
        verbose_name = 'Категория БЗ Россия'
        verbose_name_plural = 'Категории БЗ Россия'
        ordering = ['name']

    def __str__(self):
        return self.name

    def _get_slug_source(self):
        return self.name

    def _get_slug_fallback_prefix(self):
        return 'category'

    def get_full_path(self):
        parts = []
        node = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return ' → '.join(reversed(parts))


class BdRussiaArticle(SlugMixin, MarkdownContentMixin):
    """Статья базы знаний Россия"""

    title       = models.CharField(max_length=255, verbose_name='Название статьи')
    content     = models.TextField(verbose_name='Содержание статьи')
    category    = models.ForeignKey(
        BdRussiaCategory, on_delete=models.CASCADE,
        related_name='articles', verbose_name='Категория'
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    creator     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='bdrussia_created_articles', verbose_name='Создатель'
    )
    views_count = models.IntegerField(default=0, verbose_name='Количество просмотров')
    last_editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bdrussia_edited_articles', verbose_name='Последний редактор'
    )

    class Meta:
        db_table = 'BdRussia_article'
        verbose_name = 'Статья БЗ Россия'
        verbose_name_plural = 'Статьи БЗ Россия'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def _get_slug_source(self):
        return self.title

    def _get_slug_fallback_prefix(self):
        return 'article'

    def _get_slug_min_length(self):
        return 3


class BdRussiaAttachment(AttachmentMixin):
    """Вложение к статье базы знаний Россия"""

    article    = models.ForeignKey(
        BdRussiaArticle, on_delete=models.CASCADE,
        related_name='attachments', verbose_name='Статья'
    )
    file       = models.FileField(
        upload_to='bdrussia_attachments/%Y/%m/%d/',
        verbose_name='Файл', validators=[validate_file_size]
    )
    file_name  = models.CharField(max_length=255, verbose_name='Название файла')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        db_table = 'BdRussia_attachment'
        verbose_name = 'Вложение БЗ Россия'
        verbose_name_plural = 'Вложения БЗ Россия'

    def __str__(self):
        return f"Вложение к статье: {self.article.title}"


# ==================== ОЗНАКОМЛЕНИЕ ====================

class RussiaArticleAcknowledgement(models.Model):
    """Факт ознакомления сотрудника со статьёй"""

    article         = models.ForeignKey(
        BdRussiaArticle, on_delete=models.CASCADE,
        related_name='acknowledgements', verbose_name='Статья'
    )
    user            = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='russia_article_acknowledgements', verbose_name='Пользователь'
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата ознакомления')

    class Meta:
        db_table = 'BdRussia_acknowledgement'
        unique_together = ('article', 'user')
        verbose_name = 'Ознакомление со статьёй'
        verbose_name_plural = 'Ознакомления со статьями'

    def __str__(self):
        return f"{self.user} ознакомился с «{self.article.title}»"


# ==================== УВЕДОМЛЕНИЯ ====================

TECH_SUPPORT_DEPT = 'Отдел технической поддержки'


class RussiaArticleNotification(models.Model):
    """Уведомление о создании/изменении статьи Россия"""

    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Создана'),
        (ACTION_UPDATED, 'Изменена'),
    ]

    recipient  = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='russia_article_notifications', verbose_name='Получатель'
    )
    article    = models.ForeignKey(
        BdRussiaArticle, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Статья'
    )
    actor      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='russia_sent_notifications', verbose_name='Автор действия'
    )
    action     = models.CharField(
        max_length=10, choices=ACTION_CHOICES, verbose_name='Действие'
    )
    is_read    = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        db_table = 'BdRussia_notification'
        verbose_name = 'Уведомление о статье Россия'
        verbose_name_plural = 'Уведомления о статьях Россия'
        ordering = ['-created_at']

    def __str__(self):
        return f"Уведомление для {self.recipient} — «{self.article.title}»"

    def get_actor_display_name(self):
        try:
            full_name = self.actor.profile.full_name
            return full_name if full_name.strip() else self.actor.username
        except Exception:
            return self.actor.username if self.actor else '—'


# ==================== СИГНАЛЫ ====================

@receiver(post_delete, sender=BdRussiaAttachment)
def _cleanup_russia_attachment_file(instance, **kwargs):
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
                logger.debug("Файл удалён с диска: %s", instance.file.path)
        except Exception as e:
            logger.error("Не удалось удалить файл с диска: %s — %s", instance.file.path, e)


@receiver(post_save, sender=BdRussiaArticle)
def _create_russia_article_notifications(sender, instance, created, **kwargs):
    """
    При создании или изменении статьи рассылает уведомления
    всем сотрудникам отдела технической поддержки кроме автора.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        content_fields = {'title', 'content', 'category', 'category_id', 'last_editor', 'last_editor_id'}
        if not content_fields.intersection(set(update_fields)):
            return

    if getattr(instance, '_skip_notifications', False):
        return

    from support.models import EmployeeProfile

    action = RussiaArticleNotification.ACTION_CREATED if created else RussiaArticleNotification.ACTION_UPDATED
    actor  = instance.creator if created else (instance.last_editor or instance.creator)

    profiles = EmployeeProfile.objects.filter(
        department__name=TECH_SUPPORT_DEPT
    ).select_related('user')

    notifications = []
    for profile in profiles:
        recipient = profile.user
        if actor and recipient == actor:
            continue
        notifications.append(RussiaArticleNotification(
            recipient=recipient,
            article=instance,
            actor=actor,
            action=action,
        ))

    if notifications:
        if action == RussiaArticleNotification.ACTION_UPDATED:
            recipient_ids = [n.recipient_id for n in notifications]
            RussiaArticleNotification.objects.filter(
                article=instance,
                recipient_id__in=recipient_ids,
                is_read=False,
                action=RussiaArticleNotification.ACTION_UPDATED,
            ).delete()

        RussiaArticleNotification.objects.bulk_create(notifications)
        logger.info(
            "Уведомления о статье Russia id=%d '%s' (%s) разосланы %d получателям",
            instance.id, instance.title, action, len(notifications)
        )