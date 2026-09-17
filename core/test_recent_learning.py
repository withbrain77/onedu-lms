from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.services.learning import continue_lesson, recent_learning
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from progress.models import WatchProgress


class RecentLearningTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='recent-student', password='pass12345')
        self.course = Course.objects.create(title='최근 학습 강의', is_public=True)
        self.first = Lesson.objects.create(course=self.course, title='첫 차시', order=1)
        self.second = Lesson.objects.create(course=self.course, title='두 번째 차시', order=2)
        today = timezone.localdate()
        self.enrollment = Enrollment.objects.create(
            user=self.student, course=self.course, status=Enrollment.Status.APPROVED,
            start_date=today - timedelta(days=1), end_date=today + timedelta(days=7),
        )

    def save_progress(self, lesson):
        return WatchProgress.objects.create(user=self.student, enrollment=self.enrollment, lesson=lesson, last_position_seconds=42)

    def test_recent_lesson_link_and_position_on_home_and_classroom(self):
        self.save_progress(self.first)
        self.save_progress(self.second)
        self.client.force_login(self.student)
        for url in [reverse('home'), reverse('enrollments:classroom')]:
            response = self.client.get(url)
            self.assertEqual(response.context['recent_learning'].lesson, self.second)
            self.assertContains(response, '저장 위치 42초')
            self.assertContains(response, self.second.get_absolute_url())
        self.assertEqual(continue_lesson(self.enrollment), self.second)

    def test_new_learner_starts_at_first_public_lesson(self):
        self.assertEqual(continue_lesson(self.enrollment), self.first)
        self.assertIsNone(recent_learning(self.student))

    def test_hidden_expired_and_other_user_progress_are_not_exposed(self):
        self.save_progress(self.second)
        self.second.is_public = False
        self.second.save()
        self.assertIsNone(recent_learning(self.student))
        self.save_progress(self.first)
        other = User.objects.create_user(username='unrelated')
        self.assertIsNone(recent_learning(other))
        self.enrollment.end_date = timezone.localdate() - timedelta(days=1)
        self.enrollment.save()
        self.assertIsNone(recent_learning(self.student))

    def test_newer_pending_enrollment_blocks_old_progress(self):
        self.save_progress(self.second)
        Enrollment.objects.create(user=self.student, course=self.course)
        self.assertIsNone(recent_learning(self.student))
