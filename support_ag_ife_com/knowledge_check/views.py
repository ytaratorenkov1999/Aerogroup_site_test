"""
knowledge_check/views.py
Обработчики HTTP-запросов. Только маршрутизация и ответы —
бизнес-логика вынесена в services.py, email — в email.py.
"""
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from .models import TestCategory, Question, AnswerOption, UserAttempt, UserAnswer
from .services import (
    get_category_info,
    get_in_progress_attempt,
    get_last_completed_attempt,
    get_next_question,
    build_question_data,
    create_attempt,
    clear_question_order,
    get_or_restore_question_order,
)
from .email import send_attempt_report

logger = logging.getLogger('knowledge_check')


# ── Главная страница ──────────────────────────────────────────────────────────

@login_required
def knowledge_test(request):
    logger.info(f'Страница тестирования открыта пользователем «{request.user.username}»')

    raw_cats   = TestCategory.objects.filter(is_active=True).order_by('order', 'name')
    categories = [get_category_info(request.user, cat) for cat in raw_cats]

    return render(request, 'knowledge_check/knowledge.html', {
        'title':      'Проверка знаний',
        'categories': categories,
    })


# ── API: начать новую попытку ─────────────────────────────────────────────────

@login_required
@require_POST
def start_quiz(request, category_slug):
    category = get_object_or_404(TestCategory, slug=category_slug, is_active=True)
    logger.info(f'Пользователь «{request.user.username}» запускает тест «{category.name}»')

    # Если уже есть незавершённая — не создаём новую, говорим продолжить
    in_progress = get_in_progress_attempt(request.user, category)
    if in_progress:
        logger.info(f' Найдена незавершённая попытка #{in_progress.id}, перенаправление на продолжение')
        return JsonResponse({'success': False, 'error': 'use_resume'}, status=400)

    # Проверяем блокировку
    last_done = get_last_completed_attempt(request.user, category)
    if last_done and not last_done.retake_allowed:
        logger.warning(
            f' ОТКАЗ: пользователь «{request.user.username}» '
            f'уже прошёл тест «{category.name}», повтор не разрешён'
        )
        return JsonResponse({'success': False, 'error': 'Повторное прохождение не разрешено'}, status=403)

    # Снимаем флаг повтора если был разрешён
    if last_done and last_done.retake_allowed:
        last_done.retake_allowed = False
        last_done.save(update_fields=['retake_allowed'])
        logger.info(f' Флаг повторного прохождения снят с попытки #{last_done.id}')

    attempt = create_attempt(request, category)
    return JsonResponse({'success': True, 'attempt_id': attempt.id})


# ── API: продолжить незавершённую попытку ─────────────────────────────────────

@login_required
@require_POST
def resume_quiz(request, category_slug):
    category = get_object_or_404(TestCategory, slug=category_slug, is_active=True)

    attempt = get_in_progress_attempt(request.user, category)
    if not attempt:
        logger.warning(
            f'Продолжение теста «{category.name}»: '
            f'у пользователя «{request.user.username}» нет незавершённой попытки'
        )
        return JsonResponse({'success': False, 'error': 'Нет незавершённой попытки'}, status=400)

    logger.info(
        f'Пользователь «{request.user.username}» продолжает '
        f'тест «{category.name}», попытка #{attempt.id}'
    )

    # Восстанавливаем порядок вопросов в сессии если нужно
    question_ids   = get_or_restore_question_order(request, attempt)
    answered_count = attempt.answers.count()

    return JsonResponse({
        'success':        True,
        'attempt_id':     attempt.id,
        'answered_count': answered_count,
        'total_count':    len(question_ids),
    })


# ── API: получить следующий вопрос ────────────────────────────────────────────

@login_required
@require_GET
def get_question(request):
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'success': False, 'error': 'category_id required'}, status=400)

    category = get_object_or_404(TestCategory, pk=category_id)
    attempt  = get_in_progress_attempt(request.user, category)

    if not attempt:
        logger.warning(
            f'Запрос вопроса: у пользователя «{request.user.username}» '
            f'нет активной попытки по категории #{category_id}'
        )
        return JsonResponse({'success': False, 'error': 'Нет активной попытки'}, status=400)

    next_q = get_next_question(request, attempt)

    if next_q is None:
        logger.info(f' Все вопросы отвечены в попытке #{attempt.id}, тест завершается')
        return JsonResponse({'success': True, 'finished': True})

    q_data = build_question_data(
        question = next_q['question'],
        number   = next_q['number'],
        total    = next_q['total'],
        is_last  = next_q['is_last'],
    )

    return JsonResponse({
        'success':  True,
        'finished': False,
        'is_last':  next_q['is_last'],
        'question': q_data,
    })


# ── API: сохранить ответ ──────────────────────────────────────────────────────

@login_required
@require_POST
def submit_answer(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.error(f'Ошибка разбора ответа: некорректный JSON от пользователя «{request.user.username}»')
        return JsonResponse({'success': False, 'error': 'Bad JSON'}, status=400)

    category_id = body.get('category_id')
    question_id = body.get('question_id')
    answer_text = body.get('answer_text', '').strip()
    option_ids  = body.get('option_ids', [])

    if not category_id or not question_id:
        return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)

    category = get_object_or_404(TestCategory, pk=category_id)
    question = get_object_or_404(Question, pk=question_id)
    attempt  = get_in_progress_attempt(request.user, category)

    if not attempt:
        logger.warning(f'Сохранение ответа: у пользователя «{request.user.username}» нет активной попытки')
        return JsonResponse({'success': False, 'error': 'Нет активной попытки'}, status=400)

    if attempt.answers.filter(question=question).exists():
        logger.warning(f'Попытка повторного ответа на вопрос #{question_id} в попытке #{attempt.id} — пропускается')
        return JsonResponse({'success': False, 'error': 'Ответ уже сохранён'}, status=400)

    if question.question_type == Question.TYPE_TEXT:
        if not answer_text:
            return JsonResponse({'success': False, 'error': 'Пустой ответ'}, status=400)
        UserAnswer.objects.create(attempt=attempt, question=question, text_answer=answer_text)
        logger.info(f' Текстовый ответ сохранён (вопрос #{question_id}, попытка #{attempt.id})')

    else:
        if not option_ids:
            return JsonResponse({'success': False, 'error': 'Не выбран вариант'}, status=400)
        ans    = UserAnswer.objects.create(attempt=attempt, question=question)
        chosen = AnswerOption.objects.filter(pk__in=option_ids, question=question)
        ans.chosen_options.set(chosen)
        logger.info(f' Ответ с выбором сохранён (вопрос #{question_id}, попытка #{attempt.id}, варианты: {option_ids})')

    return JsonResponse({'success': True})


# ── API: завершить тест ───────────────────────────────────────────────────────

@login_required
@require_POST
def complete_quiz(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Bad JSON'}, status=400)

    category_id = body.get('category_id')
    if not category_id:
        return JsonResponse({'success': False, 'error': 'category_id required'}, status=400)

    category = get_object_or_404(TestCategory, pk=category_id)
    attempt  = get_in_progress_attempt(request.user, category)

    if not attempt:
        logger.warning(f'Завершение теста: у пользователя «{request.user.username}» нет активной попытки')
        return JsonResponse({'success': False, 'error': 'Нет активной попытки'}, status=400)

    attempt.status      = UserAttempt.STATUS_COMPLETED
    attempt.finished_at = timezone.now()
    attempt.save()
    logger.info(f'Тест «{category.name}» завершён пользователем «{request.user.username}» (попытка #{attempt.id})')

    clear_question_order(request, attempt)
    send_attempt_report(attempt)

    return JsonResponse({'success': True})