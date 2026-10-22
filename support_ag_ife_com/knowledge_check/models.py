from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


class TestCategory(models.Model):
    """Категория тестирования"""
    name        = models.CharField(max_length=255, verbose_name='Название категории')
    slug        = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    order       = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_active   = models.BooleanField(
        default=True, verbose_name='Активна',
        help_text='Отображать категорию на странице тестирования'
    )
    notify_email_main = models.EmailField(
        blank=True,
        verbose_name='Основной получатель отчёта',
        help_text='На этот адрес придёт письмо (в поле «Кому»)'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Категория тестирования'
        verbose_name_plural = 'Категории тестирования'
        ordering            = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def question_count(self):
        return self.questions.count()

    def get_cc_emails(self):
        return list(self.cc_recipients.values_list('email', flat=True))


class NotifyRecipientCC(models.Model):
    """Дополнительный получатель отчёта (копия)"""
    category = models.ForeignKey(
        TestCategory, on_delete=models.CASCADE,
        related_name='cc_recipients', verbose_name='Категория'
    )
    email = models.EmailField(verbose_name='Email (копия)')
    name  = models.CharField(max_length=150, blank=True, verbose_name='Имя (необязательно)')

    class Meta:
        verbose_name        = 'Получатель копии'
        verbose_name_plural = 'Получатели копии'

    def __str__(self):
        return f'{self.email}{" (" + self.name + ")" if self.name else ""}'


class Question(models.Model):
    """Вопрос"""
    TYPE_TEXT   = 'text'
    TYPE_CHOICE = 'choice'
    TYPES = [
        (TYPE_TEXT,   'Текстовый ответ'),
        (TYPE_CHOICE, 'Выбор варианта'),
    ]

    category      = models.ForeignKey(
        TestCategory, on_delete=models.CASCADE,
        related_name='questions', verbose_name='Категория'
    )
    text          = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(
        max_length=10, choices=TYPES, default=TYPE_TEXT,
        verbose_name='Тип вопроса'
    )
    multiple = models.BooleanField(
        default=True,
        verbose_name='Несколько правильных ответов',
        help_text='Если включено — используются чекбоксы, иначе — радиокнопки'
    )

    class Meta:
        verbose_name        = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering            = ['category', 'id']

    def __str__(self):
        return f'[{self.category.name}] {self.text[:80]}'


class QuestionAttachment(models.Model):
    """Файл или изображение, прикреплённое к вопросу"""
    question    = models.ForeignKey(
        Question, on_delete=models.CASCADE,
        related_name='attachments', verbose_name='Вопрос'
    )
    file        = models.FileField(
        upload_to='knowledge_check/attachments/',
        verbose_name='Файл'
    )
    caption     = models.CharField(
        max_length=255, blank=True,
        verbose_name='Подпись',
        help_text='Необязательное описание файла'
    )
    order       = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Вложение к вопросу'
        verbose_name_plural = 'Вложения к вопросам'
        ordering            = ['order', 'uploaded_at']

    def __str__(self):
        return f'{self.question.text[:40]} → {self.filename}'

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def is_image(self):
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg')

    @property
    def file_type(self):
        """Тип для фронтенда: image / pdf / doc / other"""
        ext = os.path.splitext(self.file.name)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'):
            return 'image'
        if ext == '.pdf':
            return 'pdf'
        if ext in ('.doc', '.docx'):
            return 'doc'
        if ext in ('.xls', '.xlsx'):
            return 'xls'
        return 'other'


class AnswerOption(models.Model):
    """Вариант ответа для вопроса с выбором"""
    question   = models.ForeignKey(
        Question, on_delete=models.CASCADE,
        related_name='options', verbose_name='Вопрос'
    )
    text       = models.CharField(max_length=500, verbose_name='Текст варианта')
    is_correct = models.BooleanField(default=False, verbose_name='Правильный ответ')
    order      = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name        = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering            = ['order']

    def __str__(self):
        return f'{self.text}{" ✓" if self.is_correct else ""}'


class UserAttempt(models.Model):
    """Попытка прохождения категории"""
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUSES = [
        (STATUS_IN_PROGRESS, 'В процессе'),
        (STATUS_COMPLETED,   'Завершено'),
    ]

    user        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='kc_attempts', verbose_name='Сотрудник'
    )
    category    = models.ForeignKey(
        TestCategory, on_delete=models.CASCADE,
        related_name='attempts', verbose_name='Категория'
    )
    status      = models.CharField(
        max_length=20, choices=STATUSES,
        default=STATUS_IN_PROGRESS, verbose_name='Статус'
    )
    started_at  = models.DateTimeField(auto_now_add=True, verbose_name='Начало')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершение')
    email_sent  = models.BooleanField(default=False, verbose_name='Отчёт отправлен')
    retake_allowed = models.BooleanField(
        default=False,
        verbose_name='Разрешено повторное прохождение',
        help_text='Если включено — сотрудник может пройти категорию заново'
    )

    class Meta:
        verbose_name        = 'Попытка прохождения'
        verbose_name_plural = 'Попытки прохождения'
        ordering            = ['-started_at']

    def __str__(self):
        try:
            name = self.user.profile.full_name or self.user.username
        except Exception:
            name = self.user.username
        return f'{name} — {self.category.name} ({self.get_status_display()})'

    @property
    def duration_minutes(self):
        if self.finished_at and self.started_at:
            return round((self.finished_at - self.started_at).total_seconds() / 60, 1)
        return None


class UserAnswer(models.Model):
    """Ответ сотрудника на один вопрос"""
    attempt        = models.ForeignKey(
        UserAttempt, on_delete=models.CASCADE,
        related_name='answers', verbose_name='Попытка'
    )
    question       = models.ForeignKey(
        Question, on_delete=models.CASCADE, verbose_name='Вопрос'
    )
    text_answer    = models.TextField(blank=True, verbose_name='Текстовый ответ')
    chosen_options = models.ManyToManyField(
        AnswerOption, blank=True, verbose_name='Выбранные варианты'
    )
    answered_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Ответ сотрудника'
        verbose_name_plural = 'Ответы сотрудников'
        ordering            = ['answered_at']

    def __str__(self):
        return f'{self.attempt.user} → {self.question.text[:50]}'