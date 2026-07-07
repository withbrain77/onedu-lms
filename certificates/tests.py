from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from certificates.models import Certificate
from core.services.completion import evaluate_enrollment_completion
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from progress.models import WatchProgress
from quizzes.models import AnswerChoice, Question, Quiz
from quizzes.services import grade_quiz_attempt


class CompletionAndCertificateTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='completion_student',
            password='pass12345',
            name='Completion Student',
        )
        self.other_student = User.objects.create_user(
            username='other_completion',
            password='pass12345',
            name='Other Student',
        )
        self.course = Course.objects.create(
            title='Completion Course',
            is_public=True,
            required_progress_percent=90,
            require_quiz_pass=True,
            certificate_enabled=True,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Completion Lesson',
            order=1,
            duration_seconds=100,
            is_public=True,
        )
        self.quiz = Quiz.objects.create(
            course=self.course,
            title='Completion Quiz',
            pass_score=70,
            max_attempts=3,
            is_public=True,
        )
        self.question = Question.objects.create(
            quiz=self.quiz,
            type=Question.Type.MULTIPLE_CHOICE,
            text='Correct?',
            points=100,
            order=1,
        )
        self.correct_choice = AnswerChoice.objects.create(
            question=self.question,
            text='Yes',
            is_correct=True,
            order=1,
        )
        self.wrong_choice = AnswerChoice.objects.create(
            question=self.question,
            text='No',
            is_correct=False,
            order=2,
        )

    def enrollment(self, user=None, course=None):
        return Enrollment.objects.create(
            user=user or self.student,
            course=course or self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )

    def set_progress(self, enrollment, percent):
        WatchProgress.objects.update_or_create(
            user=enrollment.user,
            enrollment=enrollment,
            lesson=self.lesson,
            defaults={
                'last_position_seconds': percent,
                'duration_seconds': 100,
                'progress_percent': percent,
                'is_completed': percent >= 90,
            },
        )

    def submit_quiz(self, enrollment, choice):
        return grade_quiz_attempt(
            user=enrollment.user,
            enrollment=enrollment,
            quiz=self.quiz,
            payload={f'question_{self.question.pk}': str(choice.pk)},
        )

    def test_progress_shortfall_cannot_complete(self):
        enrollment = self.enrollment()
        self.set_progress(enrollment, 75)
        self.submit_quiz(enrollment, self.correct_choice)

        status = evaluate_enrollment_completion(enrollment)
        enrollment.refresh_from_db()

        self.assertFalse(status['can_complete'])
        self.assertFalse(enrollment.is_completed)
        self.assertFalse(Certificate.objects.exists())
        self.assertIn('영상 진도 75% / 필요 90%', status['missing'])

    def test_progress_and_passed_quiz_complete_and_issue_certificate(self):
        enrollment = self.enrollment()
        self.set_progress(enrollment, 90)
        self.submit_quiz(enrollment, self.correct_choice)

        status = evaluate_enrollment_completion(enrollment)
        enrollment.refresh_from_db()

        self.assertTrue(status['can_complete'])
        self.assertTrue(enrollment.is_completed)
        self.assertIsNotNone(enrollment.completed_at)
        self.assertEqual(enrollment.completion_progress_percent, 90)
        certificate = Certificate.objects.get(enrollment=enrollment)
        self.assertEqual(certificate.user, self.student)
        self.assertEqual(certificate.course, self.course)
        self.assertGreaterEqual(len(certificate.verification_code), 20)

    def test_failed_quiz_cannot_complete(self):
        enrollment = self.enrollment()
        self.set_progress(enrollment, 100)
        self.submit_quiz(enrollment, self.wrong_choice)

        status = evaluate_enrollment_completion(enrollment)
        enrollment.refresh_from_db()

        self.assertFalse(status['can_complete'])
        self.assertFalse(enrollment.is_completed)
        self.assertIn('Completion Quiz: 시험 미합격', status['missing'])

    def test_course_without_quiz_can_complete_with_progress_only(self):
        course = Course.objects.create(
            title='No Quiz Course',
            is_public=True,
            required_progress_percent=90,
            require_quiz_pass=True,
            certificate_enabled=True,
        )
        lesson = Lesson.objects.create(course=course, title='Only Video', order=1, is_public=True)
        enrollment = self.enrollment(course=course)
        WatchProgress.objects.create(
            user=self.student,
            enrollment=enrollment,
            lesson=lesson,
            last_position_seconds=90,
            duration_seconds=100,
            progress_percent=90,
            is_completed=True,
        )

        status = evaluate_enrollment_completion(enrollment)
        enrollment.refresh_from_db()

        self.assertTrue(status['can_complete'])
        self.assertTrue(enrollment.is_completed)
        self.assertTrue(Certificate.objects.filter(enrollment=enrollment).exists())

    def test_owner_can_download_certificate_pdf(self):
        enrollment = self.enrollment()
        self.set_progress(enrollment, 100)
        self.submit_quiz(enrollment, self.correct_choice)
        evaluate_enrollment_completion(enrollment)
        certificate = Certificate.objects.get(enrollment=enrollment)

        self.client.force_login(self.student)
        response = self.client.get(reverse('certificates:download', kwargs={'pk': certificate.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        response.close()

    def test_other_user_cannot_download_certificate(self):
        enrollment = self.enrollment()
        self.set_progress(enrollment, 100)
        self.submit_quiz(enrollment, self.correct_choice)
        evaluate_enrollment_completion(enrollment)
        certificate = Certificate.objects.get(enrollment=enrollment)

        self.client.force_login(self.other_student)
        response = self.client.get(reverse('certificates:download', kwargs={'pk': certificate.pk}))

        self.assertEqual(response.status_code, 404)

    def test_incomplete_certificate_download_is_blocked(self):
        enrollment = self.enrollment()
        certificate = Certificate.objects.create(
            user=self.student,
            course=self.course,
            enrollment=enrollment,
        )

        self.client.force_login(self.student)
        response = self.client.get(reverse('certificates:download', kwargs={'pk': certificate.pk}))

        self.assertEqual(response.status_code, 404)

    def test_admin_certificate_screen_accessible(self):
        admin = User.objects.create_superuser(
            username='certificate_admin',
            password='pass12345',
            email='admin@example.com',
        )
        client = Client()
        client.force_login(admin)

        response = client.get('/admin/certificates/certificate/')

        self.assertEqual(response.status_code, 200)
