from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from .roles import ROLE_CHOICES


class Department(models.Model):
    """Отдел"""
    name = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'

    def __str__(self):
        return self.name


class Role(models.Model):
    """Роль сотрудника. Права определяются уровнем доступа (code), название — только подпись."""
    name = models.CharField(max_length=150, verbose_name='Название')
    code = models.CharField(
        max_length=20, choices=ROLE_CHOICES, unique=True, null=True, blank=True,
        verbose_name='Уровень доступа',
        help_text='Определяет права на сайте. Название роли можно менять свободно — права от него не зависят.',
    )

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    """Профиль сотрудника — 1 к 1 с User"""
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name      = models.CharField(max_length=255, verbose_name='ФИО')
    email          = models.EmailField(verbose_name='Почта')
    phone          = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    birthday       = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    position       = models.CharField(max_length=150, blank=True, verbose_name='Должность')
    department     = models.ForeignKey(
                         Department, null=True, blank=True,
                         on_delete=models.SET_NULL,
                         verbose_name='Отдел'
                     )
    role           = models.ForeignKey(
                         Role, null=True, blank=True,
                         on_delete=models.SET_NULL,
                         verbose_name='Роль'
                     )
    photo          = models.ImageField(
                         upload_to='employee_photos/',
                         null=True, blank=True,
                         verbose_name='Фото'
                     )

    class Meta:
        verbose_name = 'Профиль сотрудника'
        verbose_name_plural = 'Профили сотрудников'

    def __str__(self):
        return self.full_name or self.user.username

    def get_photo(self):
        """Возвращает фото или заглушку"""
        if self.photo:
            return self.photo.url
        return 'support/images/avatar_man.jpg'


class Employee(User):
    """Proxy над User — чтобы учётные записи жили в разделе «Сотрудники» админки"""

    class Meta:
        proxy = True
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'


class MeetingLink(models.Model):
    """Ссылка на созвон — карточка «Подключиться» на главной странице"""
    title       = models.CharField(max_length=150, verbose_name='Название')
    description = models.CharField(
                      max_length=255, blank=True, verbose_name='Описание',
                      help_text='Короткая подпись под названием, например «Ежедневная планёрка»',
                  )
    url         = models.URLField(max_length=500, verbose_name='Ссылка на созвон')
    schedule    = models.CharField(
                      max_length=100, blank=True, verbose_name='Расписание',
                      help_text='Например «Пн–Пт, 10:00». Показывается на карточке',
                  )
    order       = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_active   = models.BooleanField(
                      default=True, verbose_name='Показывать на главной',
                      help_text='Снимите галочку, чтобы скрыть ссылку, не удаляя её',
                  )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    # Площадка определяется по домену ссылки: (подстрока домена, название)
    PLATFORMS = [
        ('telemost.yandex', 'Яндекс Телемост'),
        ('zoom.us',         'Zoom'),
        ('teams.microsoft', 'Microsoft Teams'),
        ('teams.live',      'Microsoft Teams'),
        ('meet.google',     'Google Meet'),
        ('vk.com/call',     'VK Звонки'),
        ('jazz.sber',       'SberJazz'),
        ('ktalk',           'Контур.Толк'),
        ('webinar.ru',      'МТС Линк'),
        ('mts-link',        'МТС Линк'),
    ]

    class Meta:
        verbose_name        = 'Ссылка на созвон'
        verbose_name_plural = 'Ссылки на созвоны'
        ordering            = ['order', 'title']

    def __str__(self):
        return self.title

    @property
    def platform(self):
        url = self.url.lower()
        for needle, name in self.PLATFORMS:
            if needle in url:
                return name
        return 'Видеозвонок'


class UserActivity(models.Model):
    """Действие сотрудника на сайте — из них строится история активности в профиле"""
    ARTICLE_CREATED      = 'article_created'
    ARTICLE_EDITED       = 'article_edited'
    ARTICLE_DELETED      = 'article_deleted'
    ARTICLE_ACKNOWLEDGED = 'article_acknowledged'
    CATEGORY_CREATED     = 'category_created'
    CATEGORY_EDITED      = 'category_edited'
    CATEGORY_DELETED     = 'category_deleted'
    QUIZ_COMPLETED       = 'quiz_completed'
    SCHEDULE_EDITED      = 'schedule_edited'
    SCHEDULE_IMPORTED    = 'schedule_imported'
    PROFILE_UPDATED      = 'profile_updated'

    ACTION_CHOICES = [
        (ARTICLE_CREATED,      'Создана статья'),
        (ARTICLE_EDITED,       'Отредактирована статья'),
        (ARTICLE_DELETED,      'Удалена статья'),
        (ARTICLE_ACKNOWLEDGED, 'Ознакомление со статьёй'),
        (CATEGORY_CREATED,     'Создана категория'),
        (CATEGORY_EDITED,      'Отредактирована категория'),
        (CATEGORY_DELETED,     'Удалена категория'),
        (QUIZ_COMPLETED,       'Пройдена проверка знаний'),
        (SCHEDULE_EDITED,      'Изменён график дежурств'),
        (SCHEDULE_IMPORTED,    'Загружен график дежурств'),
        (PROFILE_UPDATED,      'Обновлён профиль'),
    ]

    user       = models.ForeignKey(
                     User, on_delete=models.CASCADE,
                     related_name='activities', verbose_name='Сотрудник'
                 )
    action     = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name='Действие')
    section    = models.CharField(max_length=100, blank=True, verbose_name='Раздел')
    target     = models.CharField(max_length=255, blank=True, verbose_name='Объект')
    url        = models.CharField(max_length=500, blank=True, verbose_name='Ссылка')
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата')

    class Meta:
        verbose_name        = 'Действие сотрудника'
        verbose_name_plural = 'Активность сотрудников'
        ordering            = ['-created_at']
        indexes             = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f'{self.user.username}: {self.get_action_display()} {self.target}'.strip()
