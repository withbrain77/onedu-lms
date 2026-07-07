from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course

from .models import Enrollment, ReEnrollmentRequest


class ReEnrollmentRequestTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='reenroll_student',
            password='pass12345',
            name='Re Student',
        )
        self.other_student = User.objects.create_user(
            username='other_reenroll',
            password='pass12345',
            name='Other Student',
        )
        self.admin = User.objects.create_superuser(
            username='reenroll_admin',
            password='pass12345',
            email='admin@example.com',
        )
        self.course = Course.objects.create(title='ReEnrollment Course', is_public=True)

    def enrollment(self, user=None, start_days=-40, end_days=-1, status=Enrollment.Status.APPROVED):
        return Enrollment.objects.create(
            user=user or self.student,
            course=self.course,
            status=status,
            start_date=self.today + timedelta(days=start_days),
            end_date=self.today + timedelta(days=end_days),
        )

    def test_expired_enrollment_can_request_reenrollment(self):
        enrollment = self.enrollment()
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            {'reason': '업무 일정으로 다시 수강이 필요합니다.'},
        )

        self.assertRedirects(response, reverse('enrollments:classroom'))
        request = ReEnrollmentRequest.objects.get(enrollment=enrollment)
        self.assertEqual(request.user, self.student)
        self.assertEqual(request.course, self.course)
        self.assertEqual(request.status, ReEnrollmentRequest.Status.PENDING)

    def test_active_enrollment_cannot_request_reenrollment(self):
        enrollment = self.enrollment(start_days=-1, end_days=10)
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            {'reason': '아직 기간이 남았지만 신청합니다.'},
        )

        self.assertRedirects(response, reverse('enrollments:classroom'))
        self.assertFalse(ReEnrollmentRequest.objects.exists())

    def test_unapproved_enrollment_cannot_request_reenrollment(self):
        enrollment = self.enrollment(status=Enrollment.Status.REQUESTED)
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            {'reason': '승인 전 재수강 신청입니다.'},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ReEnrollmentRequest.objects.exists())

    def test_pending_reenrollment_request_blocks_duplicate(self):
        enrollment = self.enrollment()
        ReEnrollmentRequest.objects.create(
            user=self.student,
            course=self.course,
            enrollment=enrollment,
            reason='먼저 접수한 신청입니다.',
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            {'reason': '중복 신청입니다.'},
        )

        self.assertRedirects(response, reverse('enrollments:classroom'))
        self.assertEqual(ReEnrollmentRequest.objects.filter(enrollment=enrollment).count(), 1)

    def test_admin_approval_extends_enrollment_period_without_resetting_completion(self):
        enrollment = self.enrollment()
        enrollment.is_completed = True
        enrollment.completion_progress_percent = 100
        enrollment.save(update_fields=['is_completed', 'completion_progress_percent', 'updated_at'])
        request = ReEnrollmentRequest.objects.create(
            user=self.student,
            course=self.course,
            enrollment=enrollment,
            reason='기간 연장이 필요합니다.',
        )

        request.status = ReEnrollmentRequest.Status.APPROVED
        request.processed_by = self.admin
        request.save()
        enrollment.refresh_from_db()
        request.refresh_from_db()

        self.assertEqual(enrollment.start_date, self.today)
        self.assertEqual(enrollment.end_date, self.today + timedelta(days=30))
        self.assertEqual(enrollment.approved_by, self.admin)
        self.assertTrue(enrollment.is_completed)
        self.assertEqual(enrollment.completion_progress_percent, 100)
        self.assertEqual(request.extension_start_date, self.today)
        self.assertEqual(request.extension_end_date, self.today + timedelta(days=30))
        self.assertIsNotNone(request.processed_at)

    def test_rejected_request_status_is_visible_in_classroom(self):
        enrollment = self.enrollment()
        ReEnrollmentRequest.objects.create(
            user=self.student,
            course=self.course,
            enrollment=enrollment,
            reason='재수강 요청입니다.',
            status=ReEnrollmentRequest.Status.REJECTED,
            processed_by=self.admin,
            admin_note='교육 담당자에게 별도 문의하세요.',
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse('enrollments:classroom'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '재수강 반려')
        self.assertContains(response, '교육 담당자에게 별도 문의하세요.')

    def test_expired_course_access_denied_page_shows_reenrollment_button(self):
        enrollment = self.enrollment()
        self.client.force_login(self.student)

        response = self.client.get(reverse('enrollments:course_detail', kwargs={'course_id': self.course.pk}))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '재수강 신청', status_code=403)
        self.assertContains(
            response,
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            status_code=403,
        )

    def test_other_user_cannot_request_reenrollment_for_someone_else(self):
        enrollment = self.enrollment()
        self.client.force_login(self.other_student)

        response = self.client.post(
            reverse('enrollments:request_reenrollment', kwargs={'enrollment_id': enrollment.pk}),
            {'reason': '다른 사람 수강에 대한 신청입니다.'},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ReEnrollmentRequest.objects.exists())

    def test_admin_reenrollment_request_screen_accessible(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get('/admin/enrollments/reenrollmentrequest/')

        self.assertEqual(response.status_code, 200)
