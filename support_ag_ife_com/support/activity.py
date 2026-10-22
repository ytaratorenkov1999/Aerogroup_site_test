"""
support/activity.py

История активности сотрудников: запись действий и данные для профиля.

Запись действия (вызывается из вьюх после успешного сохранения):
    from support.activity import log_activity
    from support.models import UserActivity

    log_activity(request.user, UserActivity.ARTICLE_EDITED,
                 target=article.title, section='БЗ Аэрофлот', url=article_url)

Данные для профиля:
    build_activity_calendar(user)  → сетка «как в GitLab» за последний год
    activity_stats(user)           → счётчики за год / 30 дней, серия дней подряд
    recent_activities(user)        → последние действия с иконками
"""

import logging
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import UserActivity

logger = logging.getLogger(__name__)

# Иконки Tabler (подключены в base.html) и цвет кружка для каждого действия
ACTION_ICONS = {
    UserActivity.ARTICLE_CREATED:      ('ti-file-plus',     'green'),
    UserActivity.ARTICLE_EDITED:       ('ti-pencil',        'blue'),
    UserActivity.ARTICLE_DELETED:      ('ti-trash',         'red'),
    UserActivity.ARTICLE_ACKNOWLEDGED: ('ti-eye-check',     'teal'),
    UserActivity.CATEGORY_CREATED:     ('ti-folder-plus',   'green'),
    UserActivity.CATEGORY_EDITED:      ('ti-folder',        'blue'),
    UserActivity.CATEGORY_DELETED:     ('ti-folder-x',      'red'),
    UserActivity.QUIZ_COMPLETED:       ('ti-circle-check',  'violet'),
    UserActivity.SCHEDULE_EDITED:      ('ti-calendar-cog',  'orange'),
    UserActivity.SCHEDULE_IMPORTED:    ('ti-calendar-plus', 'orange'),
    UserActivity.PROFILE_UPDATED:      ('ti-user-edit',     'gray'),
}

MONTHS_SHORT = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
MONTHS_GENITIVE = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                   'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

# Порог числа действий за день → уровень заливки клетки (0…4)
LEVEL_THRESHOLDS = (1, 3, 6, 10)


def plural_ru(n, forms):
    """plural_ru(5, ('действие', 'действия', 'действий')) → 'действий'"""
    n = abs(n) % 100
    if 11 <= n <= 14:
        return forms[2]
    n %= 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]


def log_activity(user, action, target='', section='', url='', dedupe_minutes=0):
    """
    Записывает действие пользователя. Ошибка записи не ломает основное действие.
    dedupe_minutes — не писать повтор того же действия чаще, чем раз в N минут
    (например, правки графика идут по одной клетке за запрос).
    """
    if not user or not user.is_authenticated:
        return None
    try:
        if dedupe_minutes:
            since = timezone.now() - timedelta(minutes=dedupe_minutes)
            if UserActivity.objects.filter(
                user=user, action=action, target=target[:255], created_at__gte=since,
            ).exists():
                return None
        return UserActivity.objects.create(
            user=user, action=action,
            target=target[:255], section=section[:100], url=url[:500],
        )
    except Exception:
        logger.exception('Не удалось записать активность %s для пользователя %s', action, user)
        return None


def _level(count):
    return sum(count >= t for t in LEVEL_THRESHOLDS)


def _daily_counts(user, start):
    rows = (
        UserActivity.objects
        .filter(user=user, created_at__date__gte=start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(n=Count('id'))
    )
    return {r['day']: r['n'] for r in rows}


def build_activity_calendar(user, today=None, weeks=53):
    """
    Сетка активности за последние `weeks` недель: колонки — недели (с понедельника),
    строки — дни недели. Будущие дни текущей недели — None.
    """
    today = today or timezone.localdate()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    counts = _daily_counts(user, start)

    columns, months = [], []
    for w in range(weeks):
        week_start = start + timedelta(weeks=w)
        days = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            if day.day == 1:
                # Подпись месяца — над неделей с его 1-м числом (колонка 1 — дни недели)
                months.append({'col': w + 2, 'label': MONTHS_SHORT[day.month - 1]})
            if day > today:
                days.append(None)
                continue
            n = counts.get(day, 0)
            days.append({
                'date':  day,
                'count': n,
                'level': _level(n),
                'title': f'{n} {plural_ru(n, ("действие", "действия", "действий"))} · '
                         f'{day.day} {MONTHS_GENITIVE[day.month - 1]} {day.year}',
            })
        columns.append(days)

    return {'weeks': columns, 'months': months, 'thresholds': LEVEL_THRESHOLDS}


def activity_stats(user, today=None):
    today = today or timezone.localdate()
    counts = _daily_counts(user, today - timedelta(days=365))
    year_total = sum(counts.values())
    month_total = sum(n for day, n in counts.items() if day > today - timedelta(days=30))

    # Серия: дни подряд с активностью, заканчивая сегодня (или вчера, если сегодня ещё пусто)
    streak, day = 0, today if counts.get(today) else today - timedelta(days=1)
    while counts.get(day):
        streak += 1
        day -= timedelta(days=1)

    return {
        'year_total':  year_total,
        'month_total': month_total,
        'active_days': len(counts),
        'streak':      streak,
        'streak_word': plural_ru(streak, ('день', 'дня', 'дней')),
    }


def decorate(activities):
    """Добавляет к действиям иконку и цвет для шаблона."""
    for a in activities:
        a.icon, a.color = ACTION_ICONS.get(a.action, ('ti-point', 'gray'))
    return activities


def recent_activities(user, limit=20):
    return decorate(list(UserActivity.objects.filter(user=user)[:limit]))
