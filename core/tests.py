from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.services.access import can_access_course
from courses.models import Course
from enrollments.models import Enrollment


class HomePageTests(TestCase):
    def test_anonymous_user_sees_polished_home_page(self):
        Course.objects.create(
            title='IM 마스터스 세미나 2026',
            description='대표 강의 설명',
            is_public=True,
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '위드브레인연구소 교육 영상 아카이브')
        self.assertContains(response, '교육 영상, 세미나 다시보기, 강의 영상')
        self.assertContains(response, '제한 공개')
        self.assertContains(response, 'img/withbrain-logo.png')
        self.assertContains(response, 'archive-console')
        self.assertContains(response, 'IM 마스터스 세미나 2026')
        self.assertContains(response, reverse('accounts:login'))
        self.assertContains(response, reverse('accounts:signup'))

    def test_student_home_redirects_to_classroom(self):
        user = User.objects.create_user(
            username='student_home',
            password='pass12345',
            name='수강생',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('enrollments:classroom'))

    def test_staff_home_redirects_to_admin(self):
        admin_user = User.objects.create_superuser(
            username='home_admin',
            password='pass12345',
            email='home-admin@example.com',
            name='관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('admin:index'))


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


class AdminThemeTests(TestCase):
    def test_admin_index_loads_custom_theme(self):
        admin_user = User.objects.create_superuser(
            username='admin',
            password='pass12345',
            email='admin@example.com',
            name='관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ONEDU LMS 관리자')
        self.assertContains(response, 'css/admin.css')


class UIPreviewTests(TestCase):
    def test_ui_preview_requires_staff_login(self):
        response = self.client.get(reverse('ui_preview'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])

    def test_staff_can_open_ui_preview(self):
        admin_user = User.objects.create_superuser(
            username='ui_admin',
            password='pass12345',
            email='ui-admin@example.com',
            name='UI 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('ui_preview'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UI 시안 선택')
        self.assertContains(response, 'Clear Blue')
        self.assertContains(response, 'Modern SaaS')
        self.assertContains(response, 'Calm Academy')
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Learning Timeline')
        self.assertContains(response, 'Kanban Course Board')
        self.assertContains(response, 'Focus Player')
        self.assertContains(response, 'Admin Console')
