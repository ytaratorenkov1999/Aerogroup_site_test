import mimetypes
import os
from datetime import date, timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils._os import safe_join
from .activity import (
    log_activity, build_activity_calendar, activity_stats, recent_activities, decorate,
    plural_ru, MONTHS_GENITIVE,
)
from .models import EmployeeProfile, MeetingLink, UserActivity
from .roles import get_user_role, is_admin, ROLE_EXTERNAL

# Поля профиля, которые сотрудник меняет сам (для записи активности «Обновлён профиль»)
_PROFILE_FIELDS = ('full_name', 'email', 'phone', 'position', 'birthday', 'photo')


def _next_birthday(born, today):
    """Ближайший день рождения начиная с today (29 февраля в невисокосный год — 28-го)."""
    for year in (today.year, today.year + 1):
        try:
            day = born.replace(year=year)
        except ValueError:
            day = date(year, 2, 28)
        if day >= today:
            return day


def _upcoming_birthdays(today, days=30, limit=5):
    result = []
    profiles = (EmployeeProfile.objects
                .filter(birthday__isnull=False, user__is_active=True)
                .select_related('user'))
    for p in profiles:
        day = _next_birthday(p.birthday, today)
        delta = (day - today).days
        if delta > days:
            continue
        if delta == 0:
            when = 'Сегодня'
        elif delta == 1:
            when = 'Завтра'
        else:
            when = f'Через {delta} {plural_ru(delta, ("день", "дня", "дней"))}'
        result.append({
            'profile': p,
            'date':    f'{day.day} {MONTHS_GENITIVE[day.month - 1]}',
            'when':    when,
            'today':   delta == 0,
            'delta':   delta,
        })
    result.sort(key=lambda b: b['delta'])
    return result[:limit]


def _greeting_name(user):
    """Имя для приветствия: из ФИО «Фамилия Имя Отчество» берём имя."""
    profile = EmployeeProfile.objects.filter(user=user).first()
    words = ((profile and profile.full_name) or '').split()
    if len(words) >= 2:
        return words[1]
    return (words and words[0]) or user.first_name or user.username


@login_required(login_url='login')
def index(request):
    context = {
        'title':         "Главная страница",
        'meetings':      MeetingLink.objects.filter(is_active=True),
        'greeting_name': _greeting_name(request.user),
        'is_admin':      is_admin(request.user),
    }
    # Сторонний отдел видит только созвоны — ленты сотрудников ему не показываем
    if get_user_role(request.user) != ROLE_EXTERNAL:
        context['team_feed'] = decorate(list(
            UserActivity.objects
            .exclude(action=UserActivity.PROFILE_UPDATED)
            .select_related('user', 'user__profile')[:8]
        ))
        context['birthdays'] = _upcoming_birthdays(timezone.localdate())
        context['show_team'] = True
    return render(request, 'support/index.html', context)


def _activity_context(user):
    return {
        'calendar':   build_activity_calendar(user),
        'stats':      activity_stats(user),
        'activities': recent_activities(user),
    }


@login_required(login_url='login')
def profile(request):
    try:
        employee = request.user.profile
    except EmployeeProfile.DoesNotExist:
        employee = EmployeeProfile.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
            email=request.user.email,
        )

    if request.method == 'POST':
        before = {f: getattr(employee, f) for f in _PROFILE_FIELDS}
        employee.full_name = request.POST.get('full_name', '').strip()
        employee.email     = request.POST.get('email', '').strip()
        employee.phone     = request.POST.get('phone', '').strip()
        employee.position  = request.POST.get('position', '').strip()

        if request.POST.get('birthday'):
            employee.birthday = request.POST.get('birthday')

        if request.POST.get('delete_photo'):
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = None
        elif 'photo' in request.FILES:
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = request.FILES['photo']

        employee.save()
        employee.refresh_from_db(fields=['birthday'])
        if any(getattr(employee, f) != v for f, v in before.items()):
            log_activity(request.user, UserActivity.PROFILE_UPDATED)
        messages.success(request, 'Профиль успешно обновлён')
        return redirect('profile')

    return render(request, 'support/profile.html', {
        'title':    'Профиль',
        'employee': employee,
        **_activity_context(request.user),
    })


@login_required(login_url='login')
def employee_profile(request, username):
    """Профиль коллеги: должность, отдел и история активности (только просмотр)."""
    if username == request.user.username:
        return redirect('profile')
    if get_user_role(request.user) == ROLE_EXTERNAL:
        raise Http404
    user = get_object_or_404(User, username=username, is_active=True)
    employee = EmployeeProfile.objects.filter(user=user).select_related('role', 'department').first()
    return render(request, 'support/employee_profile.html', {
        'title':    (employee and employee.full_name) or user.username,
        'person':   user,
        'employee': employee,
        **_activity_context(user),
    })

@login_required(login_url='login')
def protected_media(request, path):
    """
    Файлы из MEDIA (вложения БЗ, фото сотрудников, вложения к вопросам)
    отдаются только вошедшим пользователям.

    В продакшене (MEDIA_X_ACCEL=True) Django лишь проверяет доступ, а сам файл
    отдаёт nginx через внутренний location /protected-media/ (X-Accel-Redirect).
    Без nginx (локальная разработка) файл отдаёт Django.
    """
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except SuspiciousFileOperation:
        raise Http404
    if not os.path.isfile(full_path):
        raise Http404

    content_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
    if settings.MEDIA_X_ACCEL:
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = settings.MEDIA_X_ACCEL_PREFIX + quote(path)
        return response
    return FileResponse(open(full_path, 'rb'), content_type=content_type)
