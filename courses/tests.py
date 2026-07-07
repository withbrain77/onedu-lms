from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson


class MVPFlowViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='student',
            password='pass12345',
            name='테스트 수강생',
        )
        self.course = Course.objects.create(
            title='업무 보안 기본 교육',
            description='업무에 필요한 기본 보안 강의입니다.',
            is_public=True,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='1차시 보안 기본',
            order=1,
            is_public=True,
        )

    def login_student(self):
        self.client.force_login(self.student)

    def test_anonymous_course_detail_redirects_to_login(self):
        response = self.client.get(self.course.get_absolute_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_anonymous_classroom_redirects_to_login(self):
        response = self.client.get(reverse('enrollments:classroom'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_logged_in_student_can_view_course_list(self):
        self.login_student()
        response = self.client.get(reverse('courses:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertContains(response, '수강 신청')

    def test_student_can_apply_and_waiting_state_is_visible(self):
        self.login_student()
        response = self.client.post(reverse('courses:apply', kwargs={'slug': self.course.slug}))
        self.assertRedirects(response, reverse('enrollments:classroom'))

        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, Enrollment.Status.REQUESTED)

        classroom = self.client.get(reverse('enrollments:classroom'))
        self.assertContains(classroom, '신청 대기')
        self.assertContains(classroom, '관리자 승인 대기')

    def test_requested_enrollment_cannot_access_lesson(self):
        Enrollment.objects.create(user=self.student, course=self.course)
        self.login_student()
        response = self.client.get(self.lesson.get_absolute_url())
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '관리자 승인 대기 중입니다.', status_code=403)

    def test_approved_enrollment_can_access_lesson(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        self.login_student()
        response = self.client.get(self.lesson.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '접근 가능')

    def test_future_start_date_cannot_access_classroom_course(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        self.login_student()
        response = self.client.get(reverse('enrollments:course_detail', kwargs={'course_id': self.course.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '아직 수강 시작일 전입니다.', status_code=403)

    def test_expired_enrollment_cannot_access_classroom_course(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=7),
            end_date=self.today - timedelta(days=1),
        )
        self.login_student()
        response = self.client.get(reverse('enrollments:course_detail', kwargs={'course_id': self.course.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '수강 기간이 종료되었습니다.', status_code=403)
