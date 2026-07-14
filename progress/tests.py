import json
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson

from .admin import WatchProgressAdmin
from .models import WatchProgress


class SaveLessonProgressTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='student',
            password='pass12345',
            name='테스트 수강생',
        )
        self.other_student = User.objects.create_user(
            username='other',
            password='pass12345',
            name='다른 수강생',
        )
        self.course = Course.objects.create(title='Progress Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Progress Lesson',
            order=1,
            duration_seconds=120,
            is_public=True,
        )
        self.url = reverse('progress:save_lesson', kwargs={'lesson_id': self.lesson.pk})

    def post_progress(self, user, payload):
        self.client.force_login(user)
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def approve(self, user=None, start_offset=-1, end_offset=7):
        return Enrollment.objects.create(
            user=user or self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=start_offset),
            end_date=self.today + timedelta(days=end_offset),
        )

    def test_approved_student_can_save_progress(self):
        enrollment = self.approve()

        response = self.post_progress(
            self.student,
            {
                'position_seconds': 45,
                'duration_seconds': 120,
                'watched_increment_seconds': 12,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['last_position_seconds'], 45)
        self.assertEqual(data['total_watched_seconds'], 12)
        self.assertEqual(data['progress_percent'], 10)

        progress = WatchProgress.objects.get(enrollment=enrollment, lesson=self.lesson)
        self.assertEqual(progress.user, self.student)
        self.assertEqual(progress.last_position_seconds, 45)
        self.assertEqual(progress.total_watched_seconds, 12)

    def test_video_ended_marks_completed(self):
        self.approve()
        self.post_progress(
            self.student,
            {
                'position_seconds': 60,
                'duration_seconds': 120,
                'watched_increment_seconds': 60,
            },
        )

        response = self.post_progress(
            self.student,
            {
                'position_seconds': 120,
                'duration_seconds': 120,
                'watched_increment_seconds': 50,
                'completed': True,
            },
        )

        self.assertEqual(response.status_code, 200)
        progress = WatchProgress.objects.get(user=self.student, lesson=self.lesson)
        self.assertTrue(progress.is_completed)
        self.assertEqual(progress.progress_percent, 100)
        self.assertIsNotNone(progress.completed_at)

    def test_seek_position_does_not_inflate_progress(self):
        self.approve()

        response = self.post_progress(
            self.student,
            {
                'position_seconds': 110,
                'duration_seconds': 120,
                'watched_increment_seconds': 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['last_position_seconds'], 110)
        self.assertEqual(data['total_watched_seconds'], 10)
        self.assertEqual(data['progress_percent'], 8)
        self.assertFalse(data['is_completed'])

    def test_video_ended_does_not_complete_when_watched_time_is_low(self):
        self.approve()

        response = self.post_progress(
            self.student,
            {
                'position_seconds': 120,
                'duration_seconds': 120,
                'watched_increment_seconds': 10,
                'completed': True,
            },
        )

        self.assertEqual(response.status_code, 200)
        progress = WatchProgress.objects.get(user=self.student, lesson=self.lesson)
        self.assertFalse(progress.is_completed)
        self.assertEqual(progress.progress_percent, 8)
        self.assertIsNone(progress.completed_at)

    def test_total_watched_time_can_exceed_duration_for_rewatch_analysis(self):
        enrollment = self.approve()
        progress = WatchProgress.objects.create(
            user=self.student,
            enrollment=enrollment,
            lesson=self.lesson,
            duration_seconds=120,
        )

        progress.mark_position(120, duration_seconds=120, watched_increment_seconds=120, completed=True)
        progress.mark_position(60, duration_seconds=120, watched_increment_seconds=330)
        progress.save()

        progress.refresh_from_db()
        self.assertEqual(progress.total_watched_seconds, 450)
        self.assertEqual(progress.progress_percent, 100)
        self.assertTrue(progress.is_completed)

    def test_requested_student_cannot_save_progress(self):
        Enrollment.objects.create(user=self.student, course=self.course)

        response = self.post_progress(
            self.student,
            {'position_seconds': 30, 'duration_seconds': 120, 'watched_increment_seconds': 12},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(WatchProgress.objects.exists())

    def test_expired_student_cannot_save_progress(self):
        self.approve(start_offset=-10, end_offset=-1)

        response = self.post_progress(
            self.student,
            {'position_seconds': 30, 'duration_seconds': 120, 'watched_increment_seconds': 12},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(WatchProgress.objects.exists())

    def test_other_student_cannot_save_progress_without_own_enrollment(self):
        self.approve(user=self.student)

        response = self.post_progress(
            self.other_student,
            {'position_seconds': 30, 'duration_seconds': 120, 'watched_increment_seconds': 12},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(WatchProgress.objects.exists())


class WatchProgressAdminDisplayTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='admin_progress_student',
            password='pass12345',
            name='Admin Progress Student',
        )
        self.course = Course.objects.create(title='Admin Progress Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Admin Progress Lesson',
            order=1,
            duration_seconds=5280,
            is_public=True,
        )
        self.enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        self.admin = WatchProgressAdmin(WatchProgress, AdminSite())

    def test_admin_displays_time_values_as_human_readable_duration_and_multiplier(self):
        progress = WatchProgress.objects.create(
            user=self.student,
            enrollment=self.enrollment,
            lesson=self.lesson,
            duration_seconds=5280,
            total_watched_seconds=4224,
            last_position_seconds=4224,
            progress_percent=80,
        )

        self.assertIn('1시간 10분 24초', str(self.admin.total_watched_display(progress)))
        self.assertIn('(0.8배)', str(self.admin.total_watched_display(progress)))
        self.assertEqual(self.admin.last_position_display(progress), '1시간 10분 24초')

    def test_admin_multiplier_can_show_repeat_viewing_above_one(self):
        progress = WatchProgress.objects.create(
            user=self.student,
            enrollment=self.enrollment,
            lesson=self.lesson,
            duration_seconds=5280,
            total_watched_seconds=19536,
            last_position_seconds=5280,
            progress_percent=100,
        )

        self.assertIn('(3.7배)', str(self.admin.total_watched_display(progress)))
