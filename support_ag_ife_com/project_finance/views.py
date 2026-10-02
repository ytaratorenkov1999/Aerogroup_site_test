"""
project_finance/views.py

Раздел «Финансы проектов → Микросайты». Только для администраторов
(support.roles.admin_required). Все изменения — POST-формы с редиректом
обратно на страницу (PRG), формы открываются во всплывающих окнах.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from support.roles import admin_required
from .forms import PriceItemForm, ProjectForm, TaskForm
from .models import MicrositeProject, PriceItem, Task, totals

logger = logging.getLogger('project_finance')


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return 'Проверьте заполнение формы.'


def _plain(value):
    """Decimal → строка для поля ввода без лишних нулей: 1500.00 → «1500», 12.50 → «12.5»."""
    if value is None:
        return ''
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _project_url(project, open_dialog=None):
    url = reverse('project_finance:project', args=[project.pk])
    return f'{url}?open={open_dialog}' if open_dialog else url


# ── Сводка ──────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@admin_required
def summary(request):
    projects = (
        MicrositeProject.objects
        .annotate(is_archived=Case(When(status=MicrositeProject.STATUS_ARCHIVED, then=Value(1)),
                                   default=Value(0), output_field=IntegerField()))
        .order_by('is_archived', 'order', 'name')
        .prefetch_related('tasks')
    )
    rows = []
    for project in projects:
        tasks = list(project.tasks.all())
        rows.append({'project': project, 'count': len(tasks), **totals(tasks)})
    grand = {
        'count': sum(r['count'] for r in rows),
        'total': sum((r['total'] for r in rows), 0),
        'paid':  sum((r['paid'] for r in rows), 0),
        'due':   sum((r['due'] for r in rows), 0),
    }
    return render(request, 'project_finance/summary.html', {
        'title': 'Финансы проектов · Микросайты',
        'rows': rows,
        'grand': grand,
        'status_choices': MicrositeProject.STATUS_CHOICES,
    })


@login_required(login_url='login')
@admin_required
@require_POST
def project_create(request):
    form = ProjectForm(request.POST)
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect('project_finance:summary')
    project = form.save()
    logger.info("Проект создан: id=%d '%s', пользователь='%s'", project.pk, project.name, request.user.username)
    messages.success(request, 'Проект создан')
    return redirect(_project_url(project))


# ── Проект ──────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@admin_required
def project_detail(request, pk):
    project = get_object_or_404(MicrositeProject, pk=pk)
    tasks = list(project.tasks.select_related('price_item'))
    price_items = list(project.price_items.all())
    usage = {}
    for task in tasks:
        if task.price_item_id:
            usage[task.price_item_id] = usage.get(task.price_item_id, 0) + 1
    for item in price_items:
        item.usage = usage.get(item.pk, 0)
    sums = totals(tasks)
    return render(request, 'project_finance/project.html', {
        'title': project.name,
        'project': project,
        'tasks': tasks,
        'price_items': price_items,
        'sums': sums,
        'paid_pct': round(sums['paid'] / sums['total'] * 100) if sums['total'] else 0,
        'status_choices': MicrositeProject.STATUS_CHOICES,
        'today': timezone.localdate(),
        # Данные для заполнения форм редактирования в JS
        'js_data': {
            'price': {item.pk: {'price': _plain(item.price),
                                'negotiable': item.is_negotiable} for item in price_items},
            'tasks': {task.pk: {
                'number': task.number, 'title': task.title, 'description': task.description,
                'price_item': task.price_item_id or '', 'service_name': task.service_name,
                'price': _plain(task.price),
                'quantity': task.quantity, 'time_spent': task.time_spent,
                'date': task.date.isoformat(), 'is_free': task.is_free, 'is_paid': task.is_paid,
            } for task in tasks},
        },
    })


@login_required(login_url='login')
@admin_required
@require_POST
def project_edit(request, pk):
    project = get_object_or_404(MicrositeProject, pk=pk)
    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
        messages.success(request, 'Проект сохранён')
    else:
        messages.error(request, _first_error(form))
    return redirect(_project_url(project))


@login_required(login_url='login')
@admin_required
@require_POST
def project_delete(request, pk):
    project = get_object_or_404(MicrositeProject, pk=pk)
    logger.info("Проект удалён: id=%d '%s', пользователь='%s'", project.pk, project.name, request.user.username)
    project.delete()
    messages.success(request, 'Проект удалён')
    return redirect('project_finance:summary')


# ── Прайс-лист ──────────────────────────────────────────────────────────────

@login_required(login_url='login')
@admin_required
@require_POST
def price_save(request, pk):
    project = get_object_or_404(MicrositeProject, pk=pk)
    item_id = request.POST.get('item_id')
    instance = get_object_or_404(PriceItem, pk=item_id, project=project) if item_id else PriceItem(project=project)
    form = PriceItemForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, 'Позиция обновлена' if item_id else 'Позиция добавлена')
    else:
        messages.error(request, _first_error(form))
    return redirect(_project_url(project, 'price'))


@login_required(login_url='login')
@admin_required
@require_POST
def price_delete(request, pk, item_id):
    project = get_object_or_404(MicrositeProject, pk=pk)
    item = get_object_or_404(PriceItem, pk=item_id, project=project)
    used = item.tasks.count()
    if used:
        replacement = project.price_items.exclude(pk=item.pk).filter(pk=request.POST.get('replace_with') or 0).first()
        if replacement is None:
            messages.error(request, f'Позицию «{item.name}» используют задачи ({used}). Выберите замену.')
            return redirect(_project_url(project, 'price'))
        with transaction.atomic():
            item.tasks.update(price_item=replacement, service_name=replacement.name)
            item.delete()
        messages.success(request, 'Задачи переведены, позиция удалена')
    else:
        item.delete()
        messages.success(request, 'Позиция удалена')
    return redirect(_project_url(project, 'price'))


# ── Задачи ──────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@admin_required
@require_POST
def task_save(request, pk):
    project = get_object_or_404(MicrositeProject, pk=pk)
    task_id = request.POST.get('task_id')
    instance = get_object_or_404(Task, pk=task_id, project=project) if task_id else Task(project=project)
    was_paid = instance.is_paid
    form = TaskForm(request.POST, instance=instance, project=project)
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect(_project_url(project))
    task = form.save(commit=False)
    if task.price_item:
        task.service_name = task.price_item.name
    if task.is_paid and not was_paid:
        task.paid_at = timezone.now()
    elif not task.is_paid:
        task.paid_at = None
    task.save()
    messages.success(request, 'Задача сохранена' if task_id else 'Задача добавлена')
    return redirect(_project_url(project))


@login_required(login_url='login')
@admin_required
@require_POST
def task_delete(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    project = task.project
    task.delete()
    messages.success(request, 'Задача удалена')
    return redirect(_project_url(project))


@login_required(login_url='login')
@admin_required
@require_POST
def task_toggle_paid(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task.is_paid = not task.is_paid
    task.paid_at = timezone.now() if task.is_paid else None
    task.save(update_fields=['is_paid', 'paid_at'])
    return redirect(_project_url(task.project))
