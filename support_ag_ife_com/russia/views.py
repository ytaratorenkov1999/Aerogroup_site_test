import os
import re
import logging

from django.db.models import Q, F
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from .models import (
    CATEGORY_CYCLE_ERROR,
    BdRussiaCategory, BdRussiaArticle, BdRussiaAttachment,
    RussiaArticleNotification, RussiaArticleAcknowledgement,
)
from support.roles import role_required, ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR

logger = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.log', '.csv',
    '.zip', '.7z', '.rar',
    '.vsdx', '.json', '.xml'
}


def _validate_attachment_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return f'Недопустимый тип файла: {ext}. Разрешены: {", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}'
    return None


def _existing_category_id(raw):
    """id существующей категории из POST или None — если пусто, не число или такой нет."""
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    return pk if BdRussiaCategory.objects.filter(pk=pk).exists() else None


def _parent_choices(category):
    """Категории, которые можно выбрать родителем: без самой категории и её подкатегорий."""
    excluded = {category.id} | category.get_descendant_ids()
    return BdRussiaCategory.objects.exclude(id__in=excluded).select_related('parent', 'parent__parent')


def _safe_preview(content, max_len=150):
    text = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'[*_`~]{1,3}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0] + '...'


def _build_knowledge_structure():
    """Строит дерево категорий за 2 SQL-запроса."""
    all_categories = list(
        BdRussiaCategory.objects.all().values('id', 'name', 'slug', 'parent_id')
    )
    all_articles = list(
        BdRussiaArticle.objects.all().values('id', 'title', 'slug', 'category_id')
    )

    articles_by_category = {}
    for a in all_articles:
        articles_by_category.setdefault(a['category_id'], []).append({
            'id': a['id'], 'title': a['title'], 'slug': a['slug'],
        })

    nodes = {
        c['id']: {
            'id':            c['id'],
            'name':          c['name'],
            'slug':          c['slug'],
            'articles':      articles_by_category.get(c['id'], []),
            'subcategories': [],
            '_parent_id':    c['parent_id'],
        }
        for c in all_categories
    }

    # Расставляем подкатегории. Узлы, зацикленные через parent (старые данные),
    # становятся корневыми — иначе они пропадают из дерева.
    parent_of = {c['id']: c['parent_id'] for c in all_categories}

    def creates_cycle(node_id, parent_id):
        seen = set()
        current = parent_id
        while current is not None and current not in seen:
            if current == node_id:
                return True
            seen.add(current)
            current = parent_of.get(current)
        return False

    roots = []
    for node in nodes.values():
        parent_id = node.pop('_parent_id')
        if parent_id is None:
            roots.append(node)
        elif parent_id in nodes and not creates_cycle(node['id'], parent_id):
            nodes[parent_id]['subcategories'].append(node)
        else:
            logger.warning("Категория id=%d: родитель id=%s не найден или образует цикл", node['id'], parent_id)
            roots.append(node)

    return roots


# ============================ ОСНОВНЫЕ VIEWS ============================

@login_required
def knowledgebase(request):
    logger.debug("Пользователь '%s' открыл базу знаний Россия", request.user.username)
    return render(request, 'russia/knowledgebase.html', {
        'title': 'База знаний | Россия',
    })


@login_required
def get_knowledge_structure(request):
    structure = _build_knowledge_structure()
    return JsonResponse({'structure': structure})


@login_required
def knowledge_search(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    articles = BdRussiaArticle.objects.filter(
        Q(title__icontains=query) | Q(content__icontains=query)
    ).select_related('category', 'category__parent', 'creator')[:6]

    results = [
        {
            'id':           a.id,
            'title':        a.title,
            'slug':         a.slug,
            'preview':      _safe_preview(a.content),
            'category':     a.category.name,
            'category_path': a.category.get_full_path(),
            'created_at':   a.created_at.strftime('%d.%m.%Y'),
            'views':        a.views_count,
        }
        for a in articles
    ]
    return JsonResponse({'results': results})


@login_required
def category_detail(request, category_slug):
    category = get_object_or_404(BdRussiaCategory, slug=category_slug)
    return render(request, 'russia/category_detail.html', {
        'title':         category.name,
        'category':      category,
        'subcategories': category.subcategories.all(),
        'articles':      category.articles.all(),
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Название категории обязательно')
            return redirect('russia:index')
        raw_parent = request.POST.get('parent_id') or None
        parent_id  = _existing_category_id(raw_parent)
        if raw_parent and parent_id is None:
            messages.error(request, 'Родительская категория не найдена')
            return redirect('russia:index')
        category = BdRussiaCategory.objects.create(
            name=name,
            description=request.POST.get('description', ''),
            parent_id=parent_id,
            creator=request.user,
        )
        logger.info("Категория Russia создана: id=%d '%s', пользователь='%s'",
                    category.id, category.name, request.user.username)
        return redirect('russia:index')

    return render(request, 'russia/category_form.html', {
        'title':              'Создать категорию',
        'categories':         BdRussiaCategory.objects.all().select_related('parent', 'parent__parent'),
        'selected_parent_id': request.GET.get('parent_id'),
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def category_edit(request, category_id):
    category = get_object_or_404(BdRussiaCategory, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Название не может быть пустым')
            return redirect('russia:index')
        raw_parent = request.POST.get('parent_id') or None
        parent_id  = _existing_category_id(raw_parent)
        if raw_parent and parent_id is None:
            messages.error(request, 'Родительская категория не найдена')
            return redirect('russia:index')
        if not category.is_valid_parent(parent_id):
            return render(request, 'russia/category_form.html', {
                'title': 'Редактировать категорию',
                'category': category,
                'categories': _parent_choices(category),
                'parent_error': CATEGORY_CYCLE_ERROR,
            })
        old_name = category.name
        category.name        = name
        category.description = request.POST.get('description', '')
        category.parent_id   = parent_id
        category.save()
        logger.info("Категория Russia обновлена: id=%d '%s'→'%s', пользователь='%s'",
                    category.id, old_name, name, request.user.username)
        return redirect('russia:index')

    return render(request, 'russia/category_form.html', {
        'title':      'Редактировать категорию',
        'category':   category,
        'categories': _parent_choices(category),
    })


@login_required
@require_POST
@role_required(ROLE_ADMIN, ROLE_MANAGER)
def category_delete(request, category_id):
    category = get_object_or_404(BdRussiaCategory, id=category_id)
    logger.info("Категория Russia удалена: id=%d '%s', пользователь='%s'",
                category.id, category.name, request.user.username)
    category.delete()
    return redirect('russia:index')


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def article_create(request):
    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        content     = request.POST.get('content', '').strip()
        category_id = request.POST.get('category_id', '').strip()

        errors = {}
        if not title:       errors['title']    = 'Введите название статьи'
        if not content:     errors['content']  = 'Введите содержание статьи'
        if not category_id: errors['category'] = 'Выберите категорию'
        elif _existing_category_id(category_id) is None: errors['category'] = 'Выбранная категория не найдена'

        attachment_error = None
        for f in request.FILES.getlist('attachments'):
            err = _validate_attachment_file(f)
            if err:
                attachment_error = err
                break

        if errors or attachment_error:
            if attachment_error:
                messages.error(request, attachment_error)
            return render(request, 'russia/article_form.html', {
                'title':               'Создать статью',
                'categories':          BdRussiaCategory.objects.all().select_related('parent', 'parent__parent'),
                'selected_category_id': category_id,
                'form_data':           {'title': title, 'content': content},
                'form_errors':         errors,
            })

        article = BdRussiaArticle.objects.create(
            title=title, content=content,
            category_id=category_id, creator=request.user,
        )
        for f in request.FILES.getlist('attachments'):
            BdRussiaAttachment.objects.create(article=article, file=f, file_name=f.name)

        pending = request.session.pop('russia_pending_image_attachments', [])
        if pending:
            BdRussiaAttachment.objects.filter(id__in=pending, article=None).update(article=article)

        RussiaArticleAcknowledgement.objects.get_or_create(article=article, user=request.user)

        logger.info("Статья Russia создана: id=%d '%s', пользователь='%s'",
                    article.id, article.title, request.user.username)
        return redirect('russia:article_detail', article_slug=article.slug)

    return render(request, 'russia/article_form.html', {
        'title':               'Создать статью',
        'categories':          BdRussiaCategory.objects.all().select_related('parent', 'parent__parent'),
        'selected_category_id': request.GET.get('category_id'),
    })


@login_required
def article_detail(request, article_slug):
    article = get_object_or_404(BdRussiaArticle, slug=article_slug)
    if request.user != article.creator:
        BdRussiaArticle.objects.filter(pk=article.pk).update(views_count=F('views_count') + 1)
        article.refresh_from_db(fields=['views_count'])

    acknowledgements = (
        RussiaArticleAcknowledgement.objects
        .filter(article=article)
        .select_related('user', 'user__profile')
        .order_by('acknowledged_at')
    )
    user_acknowledged = acknowledgements.filter(user=request.user).exists()

    return render(request, 'russia/article_detail.html', {
        'title':             article.title,
        'article':           article,
        'acknowledgements':  acknowledgements,
        'user_acknowledged': user_acknowledged,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def article_edit(request, article_slug):
    article = get_object_or_404(BdRussiaArticle, slug=article_slug)
    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        content     = request.POST.get('content', '').strip()
        category_id = request.POST.get('category_id', '').strip()

        errors = {}
        if not title:       errors['title']    = 'Введите название статьи'
        if not content:     errors['content']  = 'Введите содержание статьи'
        if not category_id: errors['category'] = 'Выберите категорию'
        elif _existing_category_id(category_id) is None: errors['category'] = 'Выбранная категория не найдена'

        attachment_error = None
        for f in request.FILES.getlist('attachments'):
            err = _validate_attachment_file(f)
            if err:
                attachment_error = err
                break

        if errors or attachment_error:
            if attachment_error:
                messages.error(request, attachment_error)
            return render(request, 'russia/article_form.html', {
                'title':      'Редактировать статью',
                'article':    article,
                'categories': BdRussiaCategory.objects.all().select_related('parent', 'parent__parent'),
                'form_data':  {'title': title, 'content': content},
                'form_errors': errors,
            })

        old_title = article.title
        article.title       = title
        article.content     = content
        article.category_id = category_id
        if request.user != article.creator:
            article.last_editor = request.user
        article.save()

        for f in request.FILES.getlist('attachments'):
            BdRussiaAttachment.objects.create(article=article, file=f, file_name=f.name)

        RussiaArticleAcknowledgement.objects.filter(article=article).exclude(
            user=request.user
        ).delete()
        RussiaArticleAcknowledgement.objects.get_or_create(article=article, user=request.user)

        logger.info("Статья Russia обновлена: id=%d '%s'→'%s', пользователь='%s'",
                    article.id, old_title, title, request.user.username)
        return redirect('russia:article_detail', article_slug=article.slug)

    return render(request, 'russia/article_form.html', {
        'title':      'Редактировать статью',
        'article':    article,
        'categories': BdRussiaCategory.objects.all().select_related('parent', 'parent__parent'),
    })


@login_required
@require_POST
@role_required(ROLE_ADMIN, ROLE_MANAGER)
def article_delete(request, article_slug):
    article = get_object_or_404(BdRussiaArticle, slug=article_slug)
    category_slug = article.category.slug
    logger.info("Статья Russia удалена: id=%d '%s', пользователь='%s'",
                article.id, article.title, request.user.username)
    article.delete()
    return redirect('russia:category_detail', category_slug=category_slug)


@login_required
@require_POST
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def attachment_delete(request, attachment_id):
    attachment = get_object_or_404(BdRussiaAttachment, id=attachment_id)
    logger.info("Вложение Russia удалено: id=%d '%s', пользователь='%s'",
                attachment.id, attachment.file_name, request.user.username)
    attachment.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def attachment_delete_pending(request, attachment_id):
    attachment = get_object_or_404(
        BdRussiaAttachment, id=attachment_id, article__isnull=True
    )
    attachment.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_EDITOR)
def attachment_upload_image(request):
    file = request.FILES.get('image')
    if not file:
        return JsonResponse({'success': False, 'error': 'Файл не передан'}, status=400)

    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return JsonResponse({'success': False, 'error': 'Допустимы только изображения'}, status=400)

    err = _validate_attachment_file(file)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=400)

    article_id = request.POST.get('article_id')
    article    = None
    if article_id:
        try:
            article = BdRussiaArticle.objects.get(id=article_id)
        except BdRussiaArticle.DoesNotExist:
            pass

    attachment = BdRussiaAttachment.objects.create(
        article=article, file=file, file_name=file.name,
    )

    if article is None:
        pending = request.session.get('russia_pending_image_attachments', [])
        pending.append(attachment.id)
        request.session['russia_pending_image_attachments'] = pending
        request.session.modified = True

    return JsonResponse({
        'success':       True,
        'url':           request.build_absolute_uri(attachment.file.url),
        'attachment_id': attachment.id,
        'file_name':     attachment.file_name,
    })


# ============================ УВЕДОМЛЕНИЯ ============================

@login_required
def notifications_api(request):
    notifs = (
        RussiaArticleNotification.objects
        .filter(recipient=request.user)
        .select_related('actor', 'actor__profile', 'article')
        .order_by('-created_at')[:30]
    )

    data = []
    for n in notifs:
        actor_name = n.get_actor_display_name()
        if n.action == 'created':
            text = 'Была добавлена новая статья'
        else:
            text = f'{actor_name} изменил статью'
        data.append({
            'id':            n.id,
            'text':          text,
            'article_title': n.article.title,
            'article_url':   reverse('russia:article_detail', args=[n.article.slug]),
            'is_read':       n.is_read,
            'created_at':    n.created_at.strftime('%d.%m.%Y %H:%M'),
        })

    unread_count = sum(1 for n in data if not n['is_read'])
    return JsonResponse({'notifications': data, 'unread_count': unread_count})


@login_required
@require_POST
def notification_read(request, notification_id):
    notif = get_object_or_404(
        RussiaArticleNotification, id=notification_id, recipient=request.user
    )
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def notification_delete(request, notification_id):
    notif = get_object_or_404(
        RussiaArticleNotification, id=notification_id, recipient=request.user
    )
    notif.delete()
    return JsonResponse({'success': True})


# ============================ ОЗНАКОМЛЕНИЕ ============================

@login_required
@require_POST
def article_acknowledge(request, article_slug):
    article = get_object_or_404(BdRussiaArticle, slug=article_slug)
    _, created = RussiaArticleAcknowledgement.objects.get_or_create(
        article=article, user=request.user
    )

    try:
        profile   = request.user.profile
        full_name = profile.full_name.strip() or request.user.username
        photo_url = profile.photo.url if profile.photo else None
    except Exception:
        full_name = request.user.username
        photo_url = None

    return JsonResponse({
        'success':   True,
        'already':   not created,
        'username':  request.user.username,
        'full_name': full_name,
        'photo_url': photo_url,
    })