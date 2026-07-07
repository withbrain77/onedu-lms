from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment

from .models import AnswerChoice, Question, Quiz, QuizAttempt, QuizAttemptAnswer


class QuizFlowTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='quiz_student',
            password='pass12345',
            name='Quiz Student',
        )
        self.other_student = User.objects.create_user(
            username='other_student',
            password='pass12345',
            name='Other Student',
        )
        self.course = Course.objects.create(title='Quiz Course', is_public=True)
        self.quiz = Quiz.objects.create(
            course=self.course,
            title='Final Quiz',
            pass_score=70,
            max_attempts=3,
            is_public=True,
        )
        self.question_one = Question.objects.create(
            quiz=self.quiz,
            type=Question.Type.MULTIPLE_CHOICE,
            text='2 + 2 = ?',
            points=50,
            order=1,
        )
        self.correct_choice = AnswerChoice.objects.create(
            question=self.question_one,
            text='4',
            is_correct=True,
            order=1,
        )
        self.wrong_choice = AnswerChoice.objects.create(
            question=self.question_one,
            text='5',
            is_correct=False,
            order=2,
        )
        self.question_two = Question.objects.create(
            quiz=self.quiz,
            type=Question.Type.MULTIPLE_CHOICE,
            text='3 + 3 = ?',
            points=50,
            order=2,
        )
        self.correct_choice_two = AnswerChoice.objects.create(
            question=self.question_two,
            text='6',
            is_correct=True,
            order=1,
        )
        self.short_question = Question.objects.create(
            quiz=self.quiz,
            type=Question.Type.SHORT_ANSWER,
            text='Describe the policy.',
            points=20,
            order=3,
        )
        self.take_url = self.quiz.get_take_url()

    def approve(self, user=None, start_offset=-1, end_offset=7):
        return Enrollment.objects.create(
            user=user or self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=start_offset),
            end_date=self.today + timedelta(days=end_offset),
        )

    def login_student(self):
        self.client.force_login(self.student)

    def test_unenrolled_student_cannot_take_quiz(self):
        self.login_student()
        response = self.client.get(self.take_url)
        self.assertEqual(response.status_code, 403)

    def test_requested_student_cannot_take_quiz(self):
        Enrollment.objects.create(user=self.student, course=self.course)
        self.login_student()
        response = self.client.get(self.take_url)
        self.assertEqual(response.status_code, 403)

    def test_expired_student_cannot_take_quiz(self):
        self.approve(start_offset=-10, end_offset=-1)
        self.login_student()
        response = self.client.get(self.take_url)
        self.assertEqual(response.status_code, 403)

    def test_approved_student_can_open_quiz(self):
        self.approve()
        self.login_student()
        response = self.client.get(self.take_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.quiz.title)
        self.assertContains(response, '제출하기')

    def test_multiple_choice_is_auto_graded_and_short_answer_is_stored(self):
        enrollment = self.approve()
        self.login_student()
        self.client.get(self.take_url)

        response = self.client.post(
            self.take_url,
            {
                f'question_{self.question_one.pk}': str(self.correct_choice.pk),
                f'question_{self.question_two.pk}': str(self.correct_choice_two.pk),
                f'question_{self.short_question.pk}': 'Stored short answer',
            },
        )

        attempt = QuizAttempt.objects.get(user=self.student, quiz=self.quiz)
        self.assertRedirects(response, reverse('quizzes:result', kwargs={'pk': attempt.pk}))
        self.assertEqual(attempt.enrollment, enrollment)
        self.assertEqual(attempt.score, 100)
        self.assertTrue(attempt.passed)

        short_answer = QuizAttemptAnswer.objects.get(attempt=attempt, question=self.short_question)
        self.assertEqual(short_answer.text_answer, 'Stored short answer')
        self.assertEqual(short_answer.earned_points, 0)

    def test_failed_result_is_displayed(self):
        self.approve()
        self.login_student()
        self.client.get(self.take_url)
        self.client.post(
            self.take_url,
            {
                f'question_{self.question_one.pk}': str(self.wrong_choice.pk),
                f'question_{self.question_two.pk}': '',
                f'question_{self.short_question.pk}': 'No score',
            },
        )
        attempt = QuizAttempt.objects.get(user=self.student, quiz=self.quiz)
        response = self.client.get(reverse('quizzes:result', kwargs={'pk': attempt.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '불합격')

    def test_attempt_limit_is_enforced(self):
        self.quiz.max_attempts = 1
        self.quiz.save(update_fields=['max_attempts'])
        self.approve()
        self.login_student()
        self.client.get(self.take_url)
        self.client.post(
            self.take_url,
            {
                f'question_{self.question_one.pk}': str(self.correct_choice.pk),
                f'question_{self.question_two.pk}': str(self.correct_choice_two.pk),
                f'question_{self.short_question.pk}': 'Answer',
            },
        )

        response = self.client.get(self.take_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(QuizAttempt.objects.filter(user=self.student, quiz=self.quiz).count(), 1)

    def test_other_user_cannot_view_attempt_result(self):
        self.approve()
        self.login_student()
        self.client.get(self.take_url)
        self.client.post(
            self.take_url,
            {
                f'question_{self.question_one.pk}': str(self.correct_choice.pk),
                f'question_{self.question_two.pk}': str(self.correct_choice_two.pk),
                f'question_{self.short_question.pk}': 'Answer',
            },
        )
        attempt = QuizAttempt.objects.get(user=self.student, quiz=self.quiz)

        self.client.force_login(self.other_student)
        response = self.client.get(reverse('quizzes:result', kwargs={'pk': attempt.pk}))
        self.assertEqual(response.status_code, 404)
