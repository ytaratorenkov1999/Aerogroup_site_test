"""
knowledge_check/email.py
Отправка отчёта о прохождении тестирования на email.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from .models import Question, UserAttempt

logger = logging.getLogger('knowledge_check')


def _get_employee_info(user: object) -> dict:
    """Извлекает данные сотрудника из профиля."""
    try:
        profile = user.profile
        return {
            'full_name':  profile.full_name or user.get_full_name() or user.username,
            'email':      profile.email or user.email,
            'position':   profile.position or '—',
            'department': profile.department.name if profile.department else '—',
        }
    except Exception:
        return {
            'full_name':  user.get_full_name() or user.username,
            'email':      user.email,
            'position':   '—',
            'department': '—',
        }


def _build_text_body(attempt: UserAttempt, employee: dict, answers) -> str:
    """Формирует текстовую версию отчёта."""
    started  = attempt.started_at.strftime('%d.%m.%Y %H:%M')
    finished = attempt.finished_at.strftime('%d.%m.%Y %H:%M') if attempt.finished_at else '—'

    lines = [
        'Отчёт о прохождении тестирования',
        '',
        f'Категория:   {attempt.category.name}',
        f'Сотрудник:   {employee["full_name"]}',
        f'Должность:   {employee["position"]}',
        f'Отдел:       {employee["department"]}',
        f'Email:       {employee["email"]}',
        '',
        f'Начало:      {started}',
        f'Завершение:  {finished}',
        f'Время:       {attempt.duration_minutes} мин.',
        '',
        '─' * 60,
        'ВОПРОСЫ И ОТВЕТЫ',
        '─' * 60,
    ]

    for i, ans in enumerate(answers, 1):
        q = ans.question
        lines.append(f'\n{i}. {q.text}')
        if q.question_type == Question.TYPE_TEXT:
            lines.append(f'   Ответ: {ans.text_answer or "(пусто)"}')
        else:
            chosen = ans.chosen_options.all()
            lines.append(f'   Выбрано: {", ".join(o.text for o in chosen) or "(ничего не выбрано)"}')

    return '\n'.join(lines)


def _build_html_body(attempt: UserAttempt, employee: dict, answers) -> str:
    """Формирует HTML-версию отчёта."""
    started  = attempt.started_at.strftime('%d.%m.%Y %H:%M')
    finished = attempt.finished_at.strftime('%d.%m.%Y %H:%M') if attempt.finished_at else '—'

    rows = ''
    for i, ans in enumerate(answers, 1):
        q = ans.question
        if q.question_type == Question.TYPE_TEXT:
            answer_text = ans.text_answer or '<em>пусто</em>'
        else:
            chosen = ans.chosen_options.all()
            answer_text = ', '.join(o.text for o in chosen) or '<em>ничего не выбрано</em>'

        rows += (
            f'<tr>'
            f'<td style="padding:8px;border:1px solid #ddd;vertical-align:top;width:30px;">{i}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{q.text}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{answer_text}</td>'
            f'</tr>'
        )

    return f'''
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">

  <h2 style="color:#03a0dc;">Отчёт о прохождении тестирования</h2>

  <table style="border-collapse:collapse;margin-bottom:24px;">
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Категория</td>  <td><b>{attempt.category.name}</b></td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Сотрудник</td>  <td><b>{employee["full_name"]}</b></td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Должность</td>  <td>{employee["position"]}</td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Отдел</td>      <td>{employee["department"]}</td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Email</td>      <td>{employee["email"]}</td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Начало</td>     <td>{started}</td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Завершение</td> <td>{finished}</td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#666;">Время</td>      <td>{attempt.duration_minutes} мин.</td></tr>
  </table>

  <h3 style="color:#03a0dc;">Вопросы и ответы</h3>
  <table style="border-collapse:collapse;width:100%;">
    <thead>
      <tr style="background:#e8f7fd;">
        <th style="padding:8px;border:1px solid #ddd;text-align:center;">#</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Вопрос</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Ответ сотрудника</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

</body>
</html>'''


def send_attempt_report(attempt: UserAttempt) -> None:
    """
    Главная функция — отправляет HTML + текстовый отчёт о попытке.
    Вызывается после завершения теста.
    """
    category = attempt.category
    to_email = category.notify_email_main

    if not to_email:
        logger.info(
            f'Email не отправлен: адрес получателя не указан '
            f'для категории «{category.name}»'
        )
        return

    cc_emails = category.get_cc_emails()
    logger.info(
        f'   Отправка отчёта: '
        f'кому={to_email}, '
        f'копия={", ".join(cc_emails) if cc_emails else "нет"}'
    )

    employee = _get_employee_info(attempt.user)

    answers = (
        attempt.answers
        .select_related('question')
        .prefetch_related('chosen_options')
        .order_by('answered_at')
    )

    finished = attempt.finished_at.strftime('%d.%m.%Y %H:%M') if attempt.finished_at else '—'
    subject  = f'[Проверка знаний] {category.name} — {employee["full_name"]} — {finished}'

    try:
        msg = EmailMultiAlternatives(
            subject    = subject,
            body       = _build_text_body(attempt, employee, answers),
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            to         = [to_email],
            cc         = cc_emails,
        )
        msg.attach_alternative(_build_html_body(attempt, employee, answers), 'text/html')
        msg.send(fail_silently=False)

        attempt.email_sent = True
        attempt.save(update_fields=['email_sent'])
        logger.info(f'Отчёт успешно отправлен (попытка #{attempt.id})')

    except Exception as e:
        logger.error(
            f'ОШИБКА отправки отчёта (попытка #{attempt.id}): {e}',
            exc_info=True
        )