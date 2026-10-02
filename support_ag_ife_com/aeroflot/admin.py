from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.utils.html import format_html, mark_safe
from django.db.models import Count
from .models import (
    BdAeroflotCategory, BdAeroflotArticle, BdAeroflotAttachment,
    ArticleAcknowledgement,
)


# ══════════════════════════════════════════════════════════════
#  Вложения (inline)
# ══════════════════════════════════════════════════════════════

class BdAeroflotAttachmentInline(TabularInline):
    model           = BdAeroflotAttachment
    extra           = 0
    readonly_fields = ('uploaded_at', 'file_preview')
    fields          = ('file_name', 'file', 'file_preview', 'uploaded_at')

    def file_preview(self, obj):
        if not obj.pk:
            return '—'
        if obj.is_image():
            return format_html(
                '<img src="{}" style="height:48px;border-radius:4px;object-fit:cover">',
                obj.file.url
            )
        return format_html(
            '<a href="{}" target="_blank">📎 Скачать</a>', obj.file.url
        )
    file_preview.short_description = 'Предпросмотр'


# ══════════════════════════════════════════════════════════════
#  Ознакомления (inline)
# ══════════════════════════════════════════════════════════════

class ArticleAcknowledgementInline(TabularInline):
    model           = ArticleAcknowledgement
    extra           = 0
    readonly_fields = ('user', 'acknowledged_at')
    fields          = ('user', 'acknowledged_at')
    can_delete      = False
    verbose_name_plural = 'Кто ознакомился'

    def has_add_permission(self, request, obj=None):
        return False


# ══════════════════════════════════════════════════════════════
#  Категории
# ══════════════════════════════════════════════════════════════

@admin.register(BdAeroflotCategory)
class BdAeroflotCategoryAdmin(ModelAdmin):
    list_display   = ('name', 'parent_name', 'articles_count', 'creator', 'created_at')
    list_filter    = ('parent',)
    search_fields  = ('name', 'description')
    readonly_fields = ('slug', 'created_at', 'updated_at')
    ordering       = ('name',)

    fieldsets = (
        ('Основное', {
            'fields': ('name', 'description', 'parent', 'creator'),
        }),
        ('Служебное', {
            'fields': ('slug', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _articles_count=Count('articles')
        ).select_related('parent', 'creator')

    def parent_name(self, obj):
        return obj.parent.name if obj.parent else mark_safe('<span style="color:#aaa">— корневая —</span>')
    parent_name.short_description = 'Родитель'

    def articles_count(self, obj):
        return format_html('<b>{}</b>', obj._articles_count)
    articles_count.short_description = 'Статей'
    articles_count.admin_order_field = '_articles_count'


# ══════════════════════════════════════════════════════════════
#  Статьи
# ══════════════════════════════════════════════════════════════

@admin.register(BdAeroflotArticle)
class BdAeroflotArticleAdmin(ModelAdmin):
    list_display   = (
        'title', 'category_path', 'creator', 'last_editor',
        'views_badge', 'ack_count', 'created_at',
    )
    list_filter    = ('category', 'creator')
    search_fields  = ('title', 'content')
    readonly_fields = ('slug', 'views_count', 'created_at', 'updated_at')
    ordering       = ('-created_at',)
    inlines        = [BdAeroflotAttachmentInline, ArticleAcknowledgementInline]

    fieldsets = (
        ('Содержание', {
            'fields': ('title', 'content', 'category'),
        }),
        ('Авторство', {
            'fields': ('creator', 'last_editor'),
        }),
        ('Служебное', {
            'fields': ('slug', 'views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _ack_count=Count('acknowledgements')
        ).select_related('category', 'category__parent', 'creator', 'last_editor')

    def category_path(self, obj):
        return obj.category.get_full_path()
    category_path.short_description = 'Категория'

    def views_badge(self, obj):
        color = '#03a0dc' if obj.views_count > 0 else '#aaa'
        return format_html(
            '<span style="color:{};font-weight:600">👁 {}</span>',
            color, obj.views_count
        )
    views_badge.short_description = 'Просмотры'
    views_badge.admin_order_field = 'views_count'

    def ack_count(self, obj):
        return format_html('<b>{}</b>', obj._ack_count)
    ack_count.short_description = 'Ознакомились'
    ack_count.admin_order_field = '_ack_count'


# ══════════════════════════════════════════════════════════════
#  Вложения (отдельный раздел)
# ══════════════════════════════════════════════════════════════

@admin.register(BdAeroflotAttachment)
class BdAeroflotAttachmentAdmin(ModelAdmin):
    list_display   = ('file_name', 'article_link', 'file_preview', 'uploaded_at')
    search_fields  = ('file_name', 'article__title')
    readonly_fields = ('uploaded_at',)
    ordering       = ('-uploaded_at',)

    def article_link(self, obj):
        if obj.article is None:
            return '—'
        return format_html(
            '<a href="/bdaeroflot/article/{}/">{}</a>',
            obj.article.slug, obj.article.title
        )
    article_link.short_description = 'Статья'

    def file_preview(self, obj):
        if obj.is_image():
            return format_html(
                '<img src="{}" style="height:36px;border-radius:4px;object-fit:cover">',
                obj.file.url
            )
        ext = obj.file_name.rsplit('.', 1)[-1].upper() if '.' in obj.file_name else 'FILE'
        return format_html(
            '<span style="background:#f0f0f0;padding:2px 8px;border-radius:4px;'
            'font-size:11px;font-weight:600">{}</span>', ext
        )
    file_preview.short_description = 'Файл'


# ══════════════════════════════════════════════════════════════
#  Ознакомления
# ══════════════════════════════════════════════════════════════

@admin.register(ArticleAcknowledgement)
class ArticleAcknowledgementAdmin(ModelAdmin):
    list_display   = ('user', 'article_title', 'acknowledged_at')
    search_fields  = ('user__username', 'article__title')
    readonly_fields = ('user', 'article', 'acknowledged_at')
    ordering       = ('-acknowledged_at',)

    def article_title(self, obj):
        return obj.article.title
    article_title.short_description = 'Статья'

    def has_add_permission(self, request):
        return False