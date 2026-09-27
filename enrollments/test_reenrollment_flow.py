from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from .admin import EmailDeliveryLogAdmin
from .models import Enrollment, ReEnrollmentRequest, EmailDeliveryLog


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ONEDU_EMAIL_ASYNC=False,
                   ONEDU_NOTIFY_ENROLLMENT_REQUEST=True, ONEDU_NOTIFY_ENROLLMENT_APPROVAL=True,
                   ONEDU_ADMIN_NOTIFICATION_EMAILS=['operator@example.com'], ONEDU_EMAIL_RETRY_COUNT=0)
class ReEnrollmentFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='renewal123', email='learner@example.com')
        self.course = Course.objects.create(title='재수강 과정', pricing_type='paid', price_krw=30000,
                                            reenrollment_price_krw=12000, reenrollment_days=14)
        self.enrollment = Enrollment.objects.create(user=self.student, course=self.course, status='approved',
            start_date=timezone.localdate()-timedelta(days=40), end_date=timezone.localdate()-timedelta(days=1),
            expiry_notice_7d_sent_at=timezone.now(), is_completed=True)
        self.client.force_login(self.student)

    def create_request(self, **kwargs):
        return ReEnrollmentRequest.objects.create(user=self.student, course=self.course, enrollment=self.enrollment,
                                                   reason='복습 신청', **kwargs)

    def test_policy_and_deposit_are_visible_before_and_after_application(self):
        for url in (self.course.get_absolute_url(), reverse('enrollments:classroom'),
                    reverse('enrollments:request_reenrollment', args=[self.enrollment.pk])):
            response = self.client.get(url)
            self.assertContains(response, '12,000원')
            self.assertContains(response, '승인 후 14일')
            self.assertContains(response, 'data-copy-account=')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('enrollments:request_reenrollment', args=[self.enrollment.pk]), {'reason': '복습 신청'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['operator@example.com'])
        renewal = ReEnrollmentRequest.objects.get(enrollment=self.enrollment)
        self.assertEqual((renewal.price_krw, renewal.duration_days), (12000, 14))
        self.course.reenrollment_price_krw = 22000
        self.course.reenrollment_days = 20
        self.course.save()
        for url in (self.course.get_absolute_url(), reverse('enrollments:classroom')):
            response = self.client.get(url)
            self.assertContains(response, '12,000원')
            self.assertContains(response, '승인 후 14일')
            self.assertNotContains(response, '22,000원')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('enrollments:request_reenrollment', args=[self.enrollment.pk]), {'reason': '중복 신청'})
        self.assertEqual(ReEnrollmentRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_policy_and_waived_policy_do_not_ask_for_payment(self):
        for price, days, text in ((None, None, '재수강 비용·입금 문의'), (0, 14, '입금 없이')):
            self.course.reenrollment_price_krw, self.course.reenrollment_days = price, days
            self.course.save()
            response = self.client.get(reverse('enrollments:request_reenrollment', args=[self.enrollment.pk]))
            self.assertContains(response, text)
            self.assertNotContains(response, 'data-copy-account=')

    def test_approval_resets_expiry_once_preserves_completion_and_notifies_student(self):
        renewal = self.create_request()
        with self.captureOnCommitCallbacks(execute=True):
            renewal.status = 'approved'
            renewal.save()
        self.enrollment.refresh_from_db()
        self.assertIsNone(self.enrollment.expiry_notice_7d_sent_at)
        self.assertTrue(self.enrollment.is_completed)
        self.assertEqual(self.enrollment.end_date, timezone.localdate()+timedelta(days=14))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['learner@example.com'])
        self.assertIn('재수강 신청이 승인', mail.outbox[0].body)
        sent_at = timezone.now()
        self.enrollment.expiry_notice_7d_sent_at = sent_at
        self.enrollment.end_date += timedelta(days=5)
        self.enrollment.save()
        with self.captureOnCommitCallbacks(execute=True):
            renewal.admin_note = '메모 수정'
            renewal.save()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.expiry_notice_7d_sent_at, sent_at)
        self.assertEqual(self.enrollment.end_date, timezone.localdate()+timedelta(days=19))
        self.assertEqual(len(mail.outbox), 1)

    def test_rejection_notifies_once_without_changing_period(self):
        renewal = self.create_request()
        old_end = self.enrollment.end_date
        with self.captureOnCommitCallbacks(execute=True):
            renewal.status, renewal.admin_note = 'rejected', '별도 일정으로 안내드립니다.'
            renewal.save(update_fields=['status', 'admin_note'])
            renewal.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('별도 일정', mail.outbox[0].body)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.end_date, old_end)

    def test_rollback_does_not_send_request_mail(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.create_request()
                    raise ValueError('rollback')
            except ValueError:
                pass
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReEnrollmentRequest.objects.exists())

    def test_failed_request_mail_retains_context_and_can_be_retried(self):
        with patch('enrollments.notifications.send_mail', side_effect=RuntimeError('offline')):
            with self.captureOnCommitCallbacks(execute=True):
                renewal = self.create_request()
        log = EmailDeliveryLog.objects.get(status='failed')
        self.assertEqual(log.reenrollment_request_id, renewal.pk)
        request = RequestFactory().post('/')
        request.session = {}
        request._messages = FallbackStorage(request)
        EmailDeliveryLogAdmin(EmailDeliveryLog, AdminSite()).retry_selected_email_logs(request, EmailDeliveryLog.objects.filter(pk=log.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('복습 신청', mail.outbox[0].body)

    def test_free_renewal_does_not_create_paid_notifications(self):
        self.course.pricing_type, self.course.price_krw = 'free', 0
        self.course.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('enrollments:request_reenrollment', args=[self.enrollment.pk]))
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.has_ended)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D=True)
    def test_expiry_notice_can_be_sent_for_the_extended_period(self):
        self.enrollment.is_completed = False
        self.enrollment.save()
        renewal = self.create_request()
        with self.captureOnCommitCallbacks(execute=True):
            renewal.status = 'approved'
            renewal.extension_end_date = timezone.localdate()+timedelta(days=7)
            renewal.save()
        call_command('send_expiry_notices', verbosity=0)
        self.assertEqual(EmailDeliveryLog.objects.filter(kind='enrollment_expiry_7d', status='sent').count(), 1)
        call_command('send_expiry_notices', verbosity=0)
        self.assertEqual(EmailDeliveryLog.objects.filter(kind='enrollment_expiry_7d', status='sent').count(), 1)

    def test_course_requires_complete_positive_duration_policy(self):
        for price, days in ((10000, None), (None, 20), (0, 0)):
            self.course.reenrollment_price_krw, self.course.reenrollment_days = price, days
            with self.assertRaises(ValidationError):
                self.course.full_clean()

    def test_async_mail_preserves_renewal_reference(self):
        with override_settings(ONEDU_EMAIL_ASYNC=True):
            with patch('enrollments.notifications._enqueue_email_log') as enqueue:
                with self.captureOnCommitCallbacks(execute=True):
                    renewal = self.create_request()
                self.assertEqual(enqueue.call_count, 1)
                log = EmailDeliveryLog.objects.get(status='queued')
                self.assertEqual(log.reenrollment_request, renewal)
