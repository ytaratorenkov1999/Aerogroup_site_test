from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.utils.html import format_html
from .models import (
    TestCategory, NotifyRecipientCC,
    Question, QuestionAttachment, AnswerOption,
    UserAttempt, UserAnswer,
)


# ══════════════════════════════════════════════════════════════
#  1. КАТЕГОРИИ
# ══════════════════════════════════════════════════════════════

class NotifyRecipientCCInline(TabularInline):
    model   = NotifyRecipientCC
    extra   = 1
    fields  = ('email', 'name')
    verbose_name        = 'Получатель копии'
    verbose_name_plural = 'Получатели копии (CC)'


@admin.register(TestCategory)
class TestCategoryAdmin(ModelAdmin):
    list_display  = ('name', 'is_active', 'question_count_display', 'order', 'notify_email_main')
    list_filter   = ('is_active',)
    list_editable = ('is_active', 'order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines       = [NotifyRecipientCCInline]
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'order', 'is_active')}),
        ('Отправка отчёта', {
            'fields': ('notify_email_main',),
            'description': 'Основной получатель — «Кому». Дополнительные — ниже.',
        }),
    )

    @admin.display(description='Вопросов')
    def question_count_display(self, obj):
        n = obj.questions.count()
        color = '#28a745' if n > 0 else '#dc3545'
        return format_html('<b style="color:{}">{}</b>', color, n)


# ══════════════════════════════════════════════════════════════
#  2. ВОПРОСЫ
# ══════════════════════════════════════════════════════════════

class AnswerOptionInline(TabularInline):
    model    = AnswerOption
    extra    = 3
    fields   = ('text', 'is_correct', 'order')
    ordering = ('order',)
    verbose_name        = 'Вариант ответа'
    verbose_name_plural = 'Варианты ответов'


class QuestionAttachmentInline(TabularInline):
    model   = QuestionAttachment
    extra   = 1
    fields  = ('file', 'caption', 'order', 'preview')
    readonly_fields = ('preview',)
    ordering = ('order',)
    verbose_name        = 'Вложение'
    verbose_name_plural = 'Вложения (файлы / фото)'

    @admin.display(description='Предпросмотр')
    def preview(self, obj):
        if not obj.pk or not obj.file:
            return '—'
        if obj.is_image:
            return format_html(
                '<img src="{}" style="max-height:80px;max-width:120px;border-radius:4px;">',
                obj.file.url
            )
        return format_html(
            '<a href="{}" target="_blank">📎 {}</a>',
            obj.file.url, obj.filename
        )


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display  = ('short_text', 'category', 'question_type', 'multiple', 'attachment_count')
    list_filter   = ('question_type', 'multiple', 'category')
    search_fields = ('text',)
    ordering      = ('category', 'id')
    inlines       = [QuestionAttachmentInline, AnswerOptionInline]
    fieldsets = (
        (None, {
            'fields': ('category', 'text', 'question_type', 'multiple'),
            'description': (
                'Выберите категорию, введите вопрос. '
                'Файлы и фото добавляются в блоке «Вложения» ниже. '
                'Варианты ответов — в блоке «Варианты ответов».'
            ),
        }),
    )

    @admin.display(description='Вопрос')
    def short_text(self, obj):
        t = obj.text
        return (t[:90] + '…') if len(t) > 90 else t

    @admin.display(description='Файлов')
    def attachment_count(self, obj):
        n = obj.attachments.count()
        if n == 0:
            return '—'
        return format_html('<span style="color:#03a0dc;font-weight:bold;">📎 {}</span>', n)


# ══════════════════════════════════════════════════════════════
#  3. РЕЗУЛЬТАТЫ
# ══════════════════════════════════════════════════════════════

class UserAnswerInline(TabularInline):
    model           = UserAnswer
    extra           = 0
    can_delete      = False
    readonly_fields = ('question_text', 'answer_display', 'answered_at')
    fields          = ('question_text', 'answer_display', 'answered_at')

    @admin.display(description='Вопрос')
    def question_text(self, obj):
        return obj.question.text

    @admin.display(description='Ответ')
    def answer_display(self, obj):
        if obj.question.question_type == 'text':
            return obj.text_answer or '—'
        opts = obj.chosen_options.all()
        return ', '.join(o.text for o in opts) or '—'


@admin.register(UserAttempt)
class UserAttemptAdmin(ModelAdmin):
    list_display  = ('employee_name', 'category', 'status_display',
                     'started_at', 'finished_at', 'email_sent', 'retake_allowed')
    list_filter   = ('status', 'email_sent', 'retake_allowed', 'category')
    search_fields = ('user__username', 'user__profile__full_name')
    ordering      = ('-started_at',)
    list_editable = ('retake_allowed',)
    readonly_fields = ('user', 'category', 'status', 'started_at', 'finished_at', 'email_sent')
    inlines       = [UserAnswerInline]
    fieldsets = (
        ('Информация', {
            'fields': ('user', 'category', 'status', 'started_at', 'finished_at', 'email_sent'),
        }),
        ('Управление повторным прохождением', {
            'fields': ('retake_allowed',),
        }),
    )

    @admin.display(description='Сотрудник')
    def employee_name(self, obj):
        try:
            return obj.user.profile.full_name or obj.user.username
        except Exception:
            return obj.user.username

    @admin.display(description='Статус')
    def status_display(self, obj):
        if obj.status == UserAttempt.STATUS_COMPLETED:
            return format_html('<span style="color:{};font-weight:bold;">{}</span>', '#28a745', '✓ Завершено')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', '#f0ad4e', '⏳ В процессе')


# ══════════════════════════════════════════════════════════════
#  4. ПОВТОРНОЕ ПРОХОЖДЕНИЕ
# ══════════════════════════════════════════════════════════════

class RetakeProxy(UserAttempt):
    class Meta:
        proxy               = True
        verbose_name        = 'Разрешение повторного прохождения'
        verbose_name_plural = 'Разрешения повторного прохождения'


@admin.register(RetakeProxy)
class RetakeAdmin(ModelAdmin):
    list_display  = ('employee_name', 'category', 'finished_at', 'retake_allowed')
    list_filter   = ('category', 'retake_allowed')
    search_fields = ('user__username', 'user__profile__full_name')
    list_editable = ('retake_allowed',)
    ordering      = ('-finished_at',)
    readonly_fields = ('user', 'category', 'started_at', 'finished_at', 'email_sent', 'status')
    fields          = ('user', 'category', 'started_at', 'finished_at', 'retake_allowed')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(status=UserAttempt.STATUS_COMPLETED)

    def has_add_permission(self, request):
        return False

    @admin.display(description='Сотрудник')
    def employee_name(self, obj):
        try:
            return obj.user.profile.full_name or obj.user.username
        except Exception:
            return obj.user.username