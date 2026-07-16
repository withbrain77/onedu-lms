from datetime import timedelta
from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course

from .admin import EnrollmentAdmin
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


class EnrollmentCancellationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='cancel_student',
            password='pass12345',
            name='Cancel Student',
        )
        self.other_student = User.objects.create_user(
            username='cancel_other',
            password='pass12345',
            name='Cancel Other',
        )
        self.course = Course.objects.create(
            title='Cancellation Course',
            is_public=True,
            pricing_type=Course.PricingType.PAID,
            price_krw=30000,
        )

    def test_requested_enrollment_can_be_cancelled_by_owner(self):
        enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.REQUESTED,
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:cancel_enrollment', kwargs={'enrollment_id': enrollment.pk}),
        )

        self.assertRedirects(response, reverse('enrollments:classroom'))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.CANCELLED)

    def test_approved_enrollment_cannot_be_cancelled_by_student_action(self):
        enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('enrollments:cancel_enrollment', kwargs={'enrollment_id': enrollment.pk}),
        )

        self.assertRedirects(response, reverse('enrollments:classroom'))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.APPROVED)

    def test_other_user_cannot_cancel_enrollment(self):
        enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.REQUESTED,
        )
        self.client.force_login(self.other_student)

        response = self.client.post(
            reverse('enrollments:cancel_enrollment', kwargs={'enrollment_id': enrollment.pk}),
        )

        self.assertEqual(response.status_code, 404)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.REQUESTED)


class AdminEnrollmentNotificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='notify_admin',
            password='pass12345',
            email='admin@example.com',
        )
        self.student = User.objects.create_user(
            username='notify_student',
            password='pass12345',
            name='Notify Student',
        )
        self.paid_course = Course.objects.create(
            title='Paid Notification Course',
            is_public=True,
            pricing_type=Course.PricingType.PAID,
            price_krw=30000,
        )
        self.free_course = Course.objects.create(
            title='Free Auto Course',
            is_public=True,
            pricing_type=Course.PricingType.FREE,
            price_krw=0,
        )
        self.pending_paid = Enrollment.objects.create(
            user=self.student,
            course=self.paid_course,
            status=Enrollment.Status.REQUESTED,
        )
        Enrollment.objects.create(
            user=self.student,
            course=self.free_course,
            status=Enrollment.Status.REQUESTED,
        )

    def test_admin_index_shows_pending_paid_enrollment_notifications(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '승인 대기 수강 신청')
        self.assertContains(response, '운영 대시보드')
        self.assertContains(response, '빠른 작업')
        self.assertContains(response, '1</strong>')
        self.assertContains(response, self.paid_course.title)
        self.assertContains(response, self.student.username)
        self.assertContains(
            response,
            reverse('admin:enrollments_enrollment_change', args=[self.pending_paid.pk]),
        )


class AdminEnrollmentPeriodShortcutTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='period_admin',
            password='pass12345',
            email='period-admin@example.com',
        )
        self.student = User.objects.create_user(
            username='period_student',
            password='pass12345',
            name='Period Student',
        )
        self.course = Course.objects.create(title='Period Course', is_public=True)
        self.enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.REQUESTED,
        )

    def test_enrollment_change_form_loads_period_shortcut_script(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin:enrollments_enrollment_change', args=[self.enrollment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin_enrollment_period_shortcuts.js')
        self.assertContains(response, 'id_start_date')
        self.assertContains(response, 'id_end_date')


class EnrollmentApprovalEmailTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin_user = User.objects.create_superuser(
            username='approval_admin',
            password='pass12345',
            email='admin@example.com',
        )
        self.student = User.objects.create_user(
            username='approval_student',
            password='pass12345',
            name='승인 수강생',
            email='student@example.com',
        )
        self.course = Course.objects.create(
            title='Approval Notification Course',
            is_public=True,
            pricing_type=Course.PricingType.PAID,
            price_krw=30000,
        )
        self.enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.REQUESTED,
        )
        self.model_admin = EnrollmentAdmin(Enrollment, AdminSite())
        self.request = RequestFactory().post('/admin/enrollments/enrollment/')
        self.request.user = self.admin_user

    def approve_enrollment(self, enrollment=None):
        enrollment = enrollment or Enrollment.objects.get(pk=self.enrollment.pk)
        enrollment.status = Enrollment.Status.APPROVED
        enrollment.start_date = self.today
        enrollment.end_date = self.today + timedelta(days=30)
        self.model_admin.save_model(self.request, enrollment, form=None, change=True)
        return enrollment

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_APPROVAL=True,
        PUBLIC_SITE_URL='https://onedu.withbrain.kr',
    )
    def test_admin_approval_sends_student_email(self):
        self.approve_enrollment()

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, Enrollment.Status.APPROVED)
        self.assertEqual(self.enrollment.approved_by, self.admin_user)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(message.to, ['student@example.com'])
        self.assertIn('수강 신청이 승인되었습니다', message.subject)
        self.assertIn('승인 수강생', message.body)
        self.assertIn(self.course.title, message.body)
        self.assertIn(str(self.today), message.body)
        self.assertIn('https://onedu.withbrain.kr/classroom/', message.body)
        self.assertIn(f'https://onedu.withbrain.kr/classroom/{self.course.pk}/', message.body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_APPROVAL=True,
    )
    def test_approved_enrollment_update_does_not_send_duplicate_email(self):
        enrollment = self.approve_enrollment()
        self.assertEqual(len(mail.outbox), 1)

        enrollment = Enrollment.objects.get(pk=enrollment.pk)
        enrollment.end_date = self.today + timedelta(days=60)
        self.model_admin.save_model(self.request, enrollment, form=None, change=True)

        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_APPROVAL=False,
    )
    def test_approval_email_can_be_disabled(self):
        self.approve_enrollment()

        self.assertEqual(len(mail.outbox), 0)


class EnrollmentExpiryNoticeCommandTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='expiry_student',
            password='pass12345',
            name='만료 안내 수강생',
            email='expiry@example.com',
        )
        self.course = Course.objects.create(
            title='Expiry Notice Course',
            is_public=True,
            pricing_type=Course.PricingType.PAID,
            price_krw=30000,
        )

    def enrollment(self, **kwargs):
        defaults = {
            'user': self.student,
            'course': self.course,
            'status': Enrollment.Status.APPROVED,
            'start_date': self.today - timedelta(days=10),
            'end_date': self.today + timedelta(days=7),
        }
        defaults.update(kwargs)
        return Enrollment.objects.create(**defaults)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D=True,
        PUBLIC_SITE_URL='https://onedu.withbrain.kr',
    )
    def test_command_sends_expiry_notice_once_and_records_sent_at(self):
        enrollment = self.enrollment()
        output = StringIO()

        call_command('send_expiry_notices', date=str(self.today), stdout=output)

        enrollment.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(enrollment.expiry_notice_7d_sent_at)
        self.assertIn('matched=1 sent=1 skipped=0 dry_run=False', output.getvalue())

        message = mail.outbox[0]
        self.assertEqual(message.to, ['expiry@example.com'])
        self.assertIn('수강 기간 종료 7일 전 안내', message.subject)
        self.assertIn('만료 안내 수강생', message.body)
        self.assertIn(self.course.title, message.body)
        self.assertIn(str(enrollment.end_date), message.body)
        self.assertIn('https://onedu.withbrain.kr/classroom/', message.body)
        self.assertIn(f'https://onedu.withbrain.kr/classroom/{self.course.pk}/', message.body)

        second_output = StringIO()
        call_command('send_expiry_notices', date=str(self.today), stdout=second_output)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('matched=0 sent=0 skipped=0 dry_run=False', second_output.getvalue())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D=True,
    )
    def test_command_dry_run_does_not_send_or_mark(self):
        enrollment = self.enrollment()
        output = StringIO()

        call_command('send_expiry_notices', date=str(self.today), dry_run=True, stdout=output)

        enrollment.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(enrollment.expiry_notice_7d_sent_at)
        self.assertIn('[dry-run]', output.getvalue())
        self.assertIn('matched=1 sent=0 skipped=0 dry_run=True', output.getvalue())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D=True,
    )
    def test_command_skips_completed_unapproved_and_non_matching_dates(self):
        self.enrollment(is_completed=True)
        self.enrollment(status=Enrollment.Status.REQUESTED)
        self.enrollment(end_date=self.today + timedelta(days=8))
        output = StringIO()

        call_command('send_expiry_notices', date=str(self.today), stdout=output)

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('matched=0 sent=0 skipped=0 dry_run=False', output.getvalue())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D=False,
    )
    def test_command_respects_disabled_expiry_notice_setting(self):
        enrollment = self.enrollment()
        output = StringIO()

        call_command('send_expiry_notices', date=str(self.today), stdout=output)

        enrollment.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(enrollment.expiry_notice_7d_sent_at)
        self.assertIn('matched=1 sent=0 skipped=1 dry_run=False', output.getvalue())
