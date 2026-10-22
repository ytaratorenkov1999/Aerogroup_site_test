"""
knowledge_check/services.py
Бизнес-логика: управление попытками, вопросами, сессией.
"""
import random
import logging

from .models import TestCategory, Question, UserAttempt

logger = logging.getLogger('knowledge_check')


# ── Сессия ───────────────────────────────────────────────────────────────────

def get_session_key(attempt: UserAttempt) -> str:
    """Ключ сессии для хранения порядка вопросов."""
    return f'kc_order_{attempt.id}'


def get_or_restore_question_order(request, attempt: UserAttempt) -> list:
    """
    Возвращает порядок вопросов из сессии.
    Если сессия пуста (перезагрузка страницы) — восстанавливает:
    сначала уже отвеченные (по времени), затем оставшиеся в случайном порядке.
    """
    session_key  = get_session_key(attempt)
    question_ids = request.session.get(session_key)

    if not question_ids:
        answered_ids  = list(
            attempt.answers
            .values_list('question_id', flat=True)
            .order_by('answered_at')
        )
        remaining_ids = list(
            attempt.category.questions
            .exclude(id__in=answered_ids)
            .values_list('id', flat=True)
        )
        random.shuffle(remaining_ids)
        question_ids = answered_ids + remaining_ids
        request.session[session_key] = question_ids
        logger.debug(f' Порядок вопросов восстановлен из БД: {question_ids}')

    return question_ids


def save_question_order(request, attempt: UserAttempt, question_ids: list) -> None:
    """Сохраняет порядок вопросов в сессии."""
    request.session[get_session_key(attempt)] = question_ids


def clear_question_order(request, attempt: UserAttempt) -> None:
    """Удаляет порядок вопросов из сессии после завершения."""
    request.session.pop(get_session_key(attempt), None)


# ── Попытки ───────────────────────────────────────────────────────────────────

def get_last_completed_attempt(user, category: TestCategory):
    """Последняя завершённая попытка пользователя по категории."""
    return (
        UserAttempt.objects
        .filter(user=user, category=category, status=UserAttempt.STATUS_COMPLETED)
        .order_by('-finished_at')
        .first()
    )


def get_in_progress_attempt(user, category: TestCategory):
    """Незавершённая попытка пользователя по категории."""
    return UserAttempt.objects.filter(
        user=user, category=category,
        status=UserAttempt.STATUS_IN_PROGRESS
    ).first()


def is_category_blocked(user, category: TestCategory) -> bool:
    """
    Категория заблокирована если:
    - есть завершённая попытка без права повтора
    - И нет незавершённой (незавершённая = не завершил, нужно продолжить)
    """
    last_done   = get_last_completed_attempt(user, category)
    in_progress = get_in_progress_attempt(user, category)
    return (
        last_done is not None
        and not last_done.retake_allowed
        and in_progress is None
    )


def create_attempt(request, category: TestCategory) -> UserAttempt:
    """
    Создаёт новую попытку и сохраняет случайный порядок вопросов в сессии.
    """
    attempt = UserAttempt.objects.create(
        user     = request.user,
        category = category,
        status   = UserAttempt.STATUS_IN_PROGRESS,
    )
    logger.info(f'Создана новая попытка #{attempt.id}')

    question_ids = list(category.questions.values_list('id', flat=True))
    random.shuffle(question_ids)
    save_question_order(request, attempt, question_ids)
    logger.debug(f'Порядок вопросов (случайный): {question_ids}')

    return attempt


# ── Вопросы ───────────────────────────────────────────────────────────────────

def get_next_question(request, attempt: UserAttempt) -> dict | None:
    """
    Возвращает данные следующего вопроса или None если все отвечены.
    Формат: {'question': Question, 'number': int, 'total': int, 'is_last': bool}
    """
    question_ids = get_or_restore_question_order(request, attempt)
    answered_ids = set(attempt.answers.values_list('question_id', flat=True))
    pending_ids  = [qid for qid in question_ids if qid not in answered_ids]

    if not pending_ids:
        return None

    question = Question.objects.get(pk=pending_ids[0])
    total    = len(question_ids)
    number   = len(answered_ids) + 1
    is_last  = len(pending_ids) == 1

    logger.debug(
        f' Выдаётся вопрос «{question.text[:60]}» '
        f'({number} из {total}), попытка #{attempt.id}'
    )

    return {
        'question': question,
        'number':   number,
        'total':    total,
        'is_last':  is_last,
    }


def build_question_data(question: Question, number: int, total: int, is_last: bool) -> dict:
    """
    Формирует JSON-совместимый словарь с данными вопроса
    для отправки на фронтенд.
    """
    data = {
        'id':       question.id,
        'text':     question.text,
        'type':     question.question_type,
        'multiple': question.multiple,
        'number':   number,
        'total':    total,
    }

    # Варианты ответа (в случайном порядке)
    if question.question_type == Question.TYPE_CHOICE:
        opts = list(question.options.all())
        random.shuffle(opts)
        data['options'] = [{'id': o.id, 'text': o.text} for o in opts]

    # Вложения — все отдаются как файлы для скачивания
    attachments = question.attachments.order_by('order', 'uploaded_at')
    data['attachments'] = [
        {
            'url':  a.file.url,
            'name': a.caption or a.filename,
            'type': a.file_type,
        }
        for a in attachments
    ]

    return data


def get_category_info(user, category: TestCategory) -> dict:
    """
    Возвращает полную информацию о категории для отображения на странице.
    """
    last_done   = get_last_completed_attempt(user, category)
    in_progress = get_in_progress_attempt(user, category)
    blocked     = is_category_blocked(user, category)
    q_count     = category.questions.count()

    return {
        'id':           category.id,
        'name':         category.name,
        'slug':         category.slug,
        'description':  category.description,
        'q_count':      q_count,
        'last_done':    last_done,
        'in_progress':  in_progress,
        'is_blocked':   blocked,
        # Кликабельна если: есть вопросы И не заблокирована (или есть незавершённая)
        'can_start':    q_count > 0 and (not blocked or in_progress is not None),
    }