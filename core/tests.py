from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.services.access import can_access_course
from courses.models import Course
from enrollments.models import Enrollment


class CourseAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student1',
            password='pass12345',
            name='수강생',
        )
        self.course = Course.objects.create(title='업무 기본 교육', is_public=True)
        self.today = timezone.localdate()

    def test_course_requires_enrollment(self):
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'not_applied')

    def test_requested_enrollment_is_blocked(self):
        Enrollment.objects.create(user=self.user, course=self.course)
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'waiting_approval')

    def test_future_start_date_is_blocked(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=10),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'not_started')

    def test_expired_enrollment_is_blocked(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=10),
            end_date=self.today - timedelta(days=1),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'ended')

    def test_active_approved_enrollment_is_allowed(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertTrue(result.allowed)
        self.assertEqual(result.code, 'allowed')
