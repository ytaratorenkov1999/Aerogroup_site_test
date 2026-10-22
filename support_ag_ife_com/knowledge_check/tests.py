# knowledge_check/tests.py
#
# Тесты для приложения knowledge_check.
# Положить в: knowledge_check/tests.py  (заменить пустой файл)

import json
from django.utils import timezone
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from knowledge_check.models import (
    TestCategory, Question, AnswerOption, UserAttempt, UserAnswer,
)
from knowledge_check.services import (
    get_in_progress_attempt,
    get_last_completed_attempt,
    is_category_blocked,
    create_attempt,
)
from support.tests_helpers import make_user, LoginMixin
from support.roles import ROLE_READER, ROLE_ADMIN


# ════════════════════════════════════════════════════════════════════════════
# Фабрики
# ════════════════════════════════════════════════════════════════════════════

def make_category(name='Тест-категория', slug='test-cat', is_active=True):
    cat, _ = TestCategory.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'is_active': is_active},
    )
    return cat


def make_text_question(category, text='Вопрос текст?'):
    return Question.objects.create(
        category=category,
        text=text,
        question_type=Question.TYPE_TEXT,
    )


def make_choice_question(category, text='Вопрос выбор?', num_options=3):
    q = Question.objects.create(
        category=category,
        text=text,
        question_type=Question.TYPE_CHOICE,
        multiple=False,
    )
    for i in range(num_options):
        AnswerOption.objects.create(
            question=q,
            text=f'Вариант {i+1}',
            is_correct=(i == 0),
            order=i,
        )
    return q


# ════════════════════════════════════════════════════════════════════════════
# 1. Главная страница тестирования
# ════════════════════════════════════════════════════════════════════════════

class KnowledgeTestPageTests(LoginMixin, TestCase):

    def test_anonymous_redirected(self):
        response = self.client.get(reverse('knowledge_check:knowledge'))
        self.assertEqual(response.status_code, 302)

    def test_reader_sees_active_categories(self):
        make_category('Активная', 'active-cat', is_active=True)
        make_category('Неактивная', 'inactive-cat', is_active=False)
        user = make_user('kc1', ROLE_READER)
        self.login(user)
        response = self.client.get(reverse('knowledge_check:knowledge'))
        self.assertEqual(response.status_code, 200)
        cats = response.context['categories']
        names = [c['name'] for c in cats]
        self.assertIn('Активная', names)
        self.assertNotIn('Неактивная', names)


# ════════════════════════════════════════════════════════════════════════════
# 2. start_quiz
# ════════════════════════════════════════════════════════════════════════════

class StartQuizTests(LoginMixin, TestCase):

    def setUp(self):
        self.cat = make_category()
        make_text_question(self.cat)
        self.user = make_user('sq1', ROLE_READER)
        self.login(self.user)
        self.url = reverse('knowledge_check:start_quiz', args=[self.cat.slug])

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_start_creates_attempt(self):
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(UserAttempt.objects.filter(user=self.user, category=self.cat).exists())

    def test_start_returns_attempt_id(self):
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertIn('attempt_id', data)

    def test_cannot_start_if_already_in_progress(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_IN_PROGRESS,
        )
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'use_resume')

    def test_blocked_after_completion_without_retake(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=False,
        )
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(response.status_code, 403)

    def test_can_retake_if_retake_allowed(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=True,
        )
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_retake_flag_cleared_after_start(self):
        old = UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=True,
        )
        self.client.post(self.url)
        old.refresh_from_db()
        self.assertFalse(old.retake_allowed)

    def test_anonymous_redirected(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_inactive_category_returns_404(self):
        inactive = make_category('Неактивная', 'inactive-cat2', is_active=False)
        make_text_question(inactive)
        url = reverse('knowledge_check:start_quiz', args=[inactive.slug])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


# ════════════════════════════════════════════════════════════════════════════
# 3. resume_quiz
# ════════════════════════════════════════════════════════════════════════════

class ResumeQuizTests(LoginMixin, TestCase):

    def setUp(self):
        self.cat = make_category('Резюм кат', 'resume-cat')
        make_text_question(self.cat)
        self.user = make_user('rq1', ROLE_READER)
        self.login(self.user)
        self.url = reverse('knowledge_check:resume_quiz', args=[self.cat.slug])

    def test_resume_without_in_progress_returns_error(self):
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(response.status_code, 400)

    def test_resume_returns_attempt_info(self):
        attempt = UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_IN_PROGRESS,
        )
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['attempt_id'], attempt.id)
        self.assertIn('total_count', data)
        self.assertIn('answered_count', data)


# ════════════════════════════════════════════════════════════════════════════
# 4. get_question
#
# API принимает category_id (не attempt_id).
# Попытка ищется автоматически по (request.user, category).
# Если у пользователя нет активной попытки → 400 (не 403).
# ════════════════════════════════════════════════════════════════════════════

class GetQuestionTests(LoginMixin, TestCase):

    def setUp(self):
        self.cat = make_category('Вопросы', 'questions-cat')
        self.q = make_text_question(self.cat, 'Как дела?')
        self.user = make_user('gq1', ROLE_READER)
        self.login(self.user)
        # Создаём попытку
        self.client.post(reverse('knowledge_check:start_quiz', args=[self.cat.slug]))
        self.url = reverse('knowledge_check:get_question')

    def test_returns_question_data(self):
        # get_question принимает category_id
        response = self.client.get(self.url, {'category_id': self.cat.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('question', data)
        self.assertIn('finished', data)

    def test_missing_category_id_returns_error(self):
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_other_user_without_attempt_gets_400(self):
        # Другой пользователь не имеет активной попытки → 400
        other = make_user('gq2', ROLE_READER)
        self.login(other)
        response = self.client.get(self.url, {'category_id': self.cat.id})
        self.assertEqual(response.status_code, 400)

    def test_anonymous_redirected(self):
        self.client.logout()
        response = self.client.get(self.url, {'category_id': self.cat.id})
        self.assertEqual(response.status_code, 302)


# ════════════════════════════════════════════════════════════════════════════
# 5. submit_answer
#
# API принимает category_id + question_id (не attempt_id).
# Попытка ищется по (request.user, category).
# Чужой пользователь без попытки → 400 (не 403).
# ════════════════════════════════════════════════════════════════════════════

class SubmitAnswerTests(LoginMixin, TestCase):

    def setUp(self):
        self.cat = make_category('Ответы', 'answers-cat')
        self.q_text = make_text_question(self.cat, 'Текстовый вопрос?')
        self.q_choice = make_choice_question(self.cat, 'Вопрос с выбором?')
        self.user = make_user('sa1', ROLE_READER)
        self.login(self.user)
        self.client.post(reverse('knowledge_check:start_quiz', args=[self.cat.slug]))
        self.url = reverse('knowledge_check:submit_answer')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_submit_text_answer(self):
        response = self._post({
            'category_id': self.cat.id,
            'question_id': self.q_text.id,
            'answer_text': 'Мой ответ',
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(UserAnswer.objects.filter(
            attempt__user=self.user, question=self.q_text
        ).exists())

    def test_submit_choice_answer(self):
        option = self.q_choice.options.first()
        response = self._post({
            'category_id': self.cat.id,
            'question_id': self.q_choice.id,
            'option_ids': [option.id],
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_other_user_without_attempt_gets_400(self):
        # Другой пользователь не имеет активной попытки → 400
        other = make_user('sa2', ROLE_READER)
        self.login(other)
        response = self._post({
            'category_id': self.cat.id,
            'question_id': self.q_text.id,
            'answer_text': 'Чужой',
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_empty_text_answer_returns_error(self):
        response = self._post({
            'category_id': self.cat.id,
            'question_id': self.q_text.id,
            'answer_text': '',
        })
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_missing_category_id_returns_error(self):
        response = self._post({'question_id': self.q_text.id, 'answer_text': 'x'})
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_double_submit_same_question_returns_error(self):
        self._post({
            'category_id': self.cat.id,
            'question_id': self.q_text.id,
            'answer_text': 'Первый ответ',
        })
        response = self._post({
            'category_id': self.cat.id,
            'question_id': self.q_text.id,
            'answer_text': 'Второй ответ',
        })
        data = json.loads(response.content)
        self.assertFalse(data['success'])


# ════════════════════════════════════════════════════════════════════════════
# 6. complete_quiz
#
# API принимает category_id (не attempt_id).
# Попытка ищется по (request.user, category).
# Если нет активной попытки → 400.
# ════════════════════════════════════════════════════════════════════════════

class CompleteQuizTests(LoginMixin, TestCase):

    def setUp(self):
        self.cat = make_category('Завершение', 'complete-cat')
        make_text_question(self.cat)
        self.user = make_user('cq1', ROLE_READER)
        self.login(self.user)
        self.client.post(reverse('knowledge_check:start_quiz', args=[self.cat.slug]))
        self.url = reverse('knowledge_check:complete_quiz')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_complete_changes_status(self):
        self._post({'category_id': self.cat.id})
        attempt = UserAttempt.objects.get(user=self.user, category=self.cat)
        self.assertEqual(attempt.status, UserAttempt.STATUS_COMPLETED)

    def test_complete_sets_finished_at(self):
        self._post({'category_id': self.cat.id})
        attempt = UserAttempt.objects.get(user=self.user, category=self.cat)
        self.assertIsNotNone(attempt.finished_at)

    def test_other_user_without_attempt_gets_400(self):
        # Другой пользователь без попытки → 400 (нет активной попытки)
        other = make_user('cq2', ROLE_READER)
        self.login(other)
        response = self._post({'category_id': self.cat.id})
        self.assertEqual(response.status_code, 400)

    def test_complete_already_completed_returns_400(self):
        # Завершаем первый раз
        self._post({'category_id': self.cat.id})
        # Второй вызов — нет активной попытки → 400
        response = self._post({'category_id': self.cat.id})
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(response.status_code, 400)

    def test_missing_category_id_returns_error(self):
        response = self._post({})
        data = json.loads(response.content)
        self.assertFalse(data['success'])


# ════════════════════════════════════════════════════════════════════════════
# 7. services.py
# ════════════════════════════════════════════════════════════════════════════

class ServicesTests(TestCase):

    def setUp(self):
        self.cat = make_category('Сервис кат', 'service-cat')
        self.user = make_user('srv1', ROLE_READER)

    def test_get_in_progress_attempt_returns_none_if_none(self):
        self.assertIsNone(get_in_progress_attempt(self.user, self.cat))

    def test_get_in_progress_attempt_returns_attempt(self):
        attempt = UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_IN_PROGRESS,
        )
        result = get_in_progress_attempt(self.user, self.cat)
        self.assertEqual(result.id, attempt.id)

    def test_get_last_completed_returns_none_if_none(self):
        self.assertIsNone(get_last_completed_attempt(self.user, self.cat))

    def test_get_last_completed_returns_latest(self):
        # finished_at обязателен для сортировки: без него порядок не определён
        now = timezone.now()
        a1 = UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            finished_at=now - timedelta(minutes=10),
        )
        a2 = UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            finished_at=now,
        )
        result = get_last_completed_attempt(self.user, self.cat)
        self.assertEqual(result.id, a2.id)

    def test_is_category_blocked_true_when_completed_no_retake(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=False,
        )
        self.assertTrue(is_category_blocked(self.user, self.cat))

    def test_is_category_blocked_false_when_retake_allowed(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=True,
        )
        self.assertFalse(is_category_blocked(self.user, self.cat))

    def test_is_category_blocked_false_when_in_progress(self):
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_COMPLETED,
            retake_allowed=False,
        )
        UserAttempt.objects.create(
            user=self.user, category=self.cat,
            status=UserAttempt.STATUS_IN_PROGRESS,
        )
        self.assertFalse(is_category_blocked(self.user, self.cat))

    def test_is_category_blocked_false_when_no_attempts(self):
        self.assertFalse(is_category_blocked(self.user, self.cat))


# ════════════════════════════════════════════════════════════════════════════
# 8. Модели
# ════════════════════════════════════════════════════════════════════════════

class KnowledgeCheckModelTests(TestCase):

    def test_test_category_str(self):
        cat = make_category('Моя категория', 'my-cat')
        self.assertEqual(str(cat), 'Моя категория')

    def test_question_count_property(self):
        cat = make_category('Подсчёт', 'count-cat')
        make_text_question(cat, 'В1')
        make_text_question(cat, 'В2')
        self.assertEqual(cat.question_count, 2)

    def test_get_cc_emails(self):
        from knowledge_check.models import NotifyRecipientCC
        cat = make_category('CC кат', 'cc-cat')
        NotifyRecipientCC.objects.create(category=cat, email='a@a.com')
        NotifyRecipientCC.objects.create(category=cat, email='b@b.com')
        emails = cat.get_cc_emails()
        self.assertIn('a@a.com', emails)
        self.assertIn('b@b.com', emails)

    def test_answer_option_str_correct(self):
        cat = make_category('Варианты', 'opts-cat')
        q = make_choice_question(cat, 'Варианты?')
        correct = q.options.filter(is_correct=True).first()
        self.assertIn('✓', str(correct))

    def test_answer_option_str_incorrect(self):
        cat = make_category('Варианты2', 'opts-cat2')
        q = make_choice_question(cat, 'Варианты2?')
        wrong = q.options.filter(is_correct=False).first()
        self.assertNotIn('✓', str(wrong))

    def test_user_attempt_duration_minutes(self):
        cat = make_category('Длительность', 'dur-cat')
        user = make_user('dur1', ROLE_READER)
        now = timezone.now()
        attempt = UserAttempt.objects.create(
            user=user, category=cat,
            status=UserAttempt.STATUS_COMPLETED,
            started_at=now - timedelta(minutes=30),
            finished_at=now,
        )
        # auto_now_add перезаписывает started_at, поэтому обновляем напрямую
        UserAttempt.objects.filter(pk=attempt.pk).update(
            started_at=now - timedelta(minutes=30),
            finished_at=now,
        )
        attempt.refresh_from_db()
        self.assertAlmostEqual(attempt.duration_minutes, 30, delta=1)

    def test_user_attempt_duration_none_if_not_finished(self):
        cat = make_category('Незавершено', 'nofinish-cat')
        user = make_user('dur2', ROLE_READER)
        attempt = UserAttempt.objects.create(
            user=user, category=cat,
            status=UserAttempt.STATUS_IN_PROGRESS,
        )
        self.assertIsNone(attempt.duration_minutes)