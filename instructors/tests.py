from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import StudentProfileForm, StudentSignUpForm
from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment, ReEnrollmentRequest
from lessons.models import Lesson
from .models import InstructorEarning, RefundRecord, RevenueRecord, TeachingAssignment
from .services import advance_earnings, post_refund, post_revenue


class InstructorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.operator = User.objects.create_superuser(username='operator1', password='Test-only-482!')
        cls.teacher = User.objects.create_user(username='teacher1', is_instructor=True)
        cls.other = User.objects.create_user(username='teacher2', is_instructor=True)
        cls.student = User.objects.create_user(username='student1', email='private.student@example.invalid')
        cls.course = Course.objects.create(title='본인 담당 강의', pricing_type='paid', price_krw=30000,
            reenrollment_price_krw=12000, reenrollment_days=14)
        cls.lesson = Lesson.objects.create(course=cls.course, title='담당 차시', order=1)
        cls.assignment = TeachingAssignment.objects.create(instructor=cls.teacher, course=cls.course,
            fixed_amount=10000, starts_on=cls.today-timedelta(days=365))

    def payment(self, amount=30000, user=None):
        enrollment = Enrollment.objects.create(user=user or self.student, course=self.course,
            status='approved', payment_status='confirmed', start_date=self.today, end_date=self.today+timedelta(days=30))
        record = enrollment.revenue_record
        record.amount = amount
        record.save()
        return record

    def post(self, amount=30000):
        record = self.payment(amount)
        post_revenue(record.pk, self.operator)
        record.refresh_from_db()
        return record

    def test_roles_coexist_and_do_not_grant_admin_or_self_promotion(self):
        self.assertTrue(self.teacher.is_student)
        self.assertFalse(self.teacher.is_staff)
        self.assertNotIn('is_instructor', StudentSignUpForm().fields)
        self.assertNotIn('is_instructor', StudentProfileForm().fields)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get('/instructor/').status_code, 200)
        self.assertEqual(self.client.get('/classroom/').status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertContains(self.client.get('/accounts/profile/'), '강사실 보기')

    def test_anonymous_student_and_revoked_accounts_cannot_access_or_export(self):
        for suffix in ('', '?download=csv'):
            self.assertEqual(self.client.get('/instructor/'+suffix).status_code, 302)
        for user in (self.student, self.operator):
            self.client.force_login(user)
            for suffix in ('', '?download=csv'):
                self.assertEqual(self.client.get('/instructor/'+suffix).status_code, 403)
        self.client.force_login(self.teacher)
        User.objects.filter(pk=self.teacher.pk).update(is_instructor=False)
        self.assertEqual(self.client.get('/instructor/').status_code, 403)

    def test_assignment_requires_instructor_and_matching_lesson(self):
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(instructor=self.student, course=self.course)
        other_course = Course.objects.create(title='다른 강의')
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(instructor=self.other, course=other_course, lesson=self.lesson)

    def test_assignment_overlap_and_whole_course_lesson_double_payment_rejected(self):
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(instructor=self.teacher, course=self.course)
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(instructor=self.other, course=self.course, lesson=self.lesson)
        self.assignment.ends_on = self.today
        self.assignment.save()
        TeachingAssignment.objects.create(instructor=self.teacher, course=self.course, starts_on=self.today+timedelta(days=1))

    def test_payment_creates_unknown_amount_once_without_using_course_price(self):
        enrollment = Enrollment.objects.create(user=self.student, course=self.course, payment_status='confirmed')
        self.assertIsNone(enrollment.revenue_record.amount)
        enrollment.save()
        self.assertEqual(RevenueRecord.objects.count(), 1)
        with self.assertRaises(ValidationError):
            post_revenue(enrollment.revenue_record.pk, self.operator)
        self.assertEqual(InstructorEarning.objects.count(), 0)

    def test_fixed_snapshot_idempotence_and_frozen_financial_history(self):
        record = self.post()
        self.assertFalse(post_revenue(record.pk, self.operator))
        earning = record.earnings.get()
        self.assertEqual(earning.amount, 10000)
        self.course.price_krw = 90000
        self.course.save()
        self.assertEqual(record.earnings.get().amount, 10000)
        self.assignment.fixed_amount = 20000
        with self.assertRaises(ValidationError):
            self.assignment.save()
        record.amount = 50000
        with self.assertRaises(ValidationError):
            record.save()

    def test_percentage_is_based_on_actual_payment_and_rounds_down(self):
        self.assignment.method = 'percent'
        self.assignment.allocation_percent = 50
        self.assignment.royalty_percent = 40
        self.assignment.save()
        record = self.post(24999)
        self.assertEqual(record.earnings.get().amount, 4999)

    def test_multi_instructor_lesson_shares_and_sum_guard(self):
        self.assignment.delete()
        TeachingAssignment.objects.create(instructor=self.teacher, course=self.course, lesson=self.lesson,
            method='percent', allocation_percent=50, royalty_percent=40)
        lesson2 = Lesson.objects.create(course=self.course, title='다른 차시', order=2)
        TeachingAssignment.objects.create(instructor=self.other, course=self.course, lesson=lesson2,
            method='percent', allocation_percent=50, royalty_percent=40)
        record = self.post()
        self.assertEqual(list(record.earnings.values_list('amount', flat=True)), [6000, 6000])
        self.assertEqual(record.earnings.count(), 2)

    def test_payment_cannot_be_posted_without_terms_or_with_excessive_payout(self):
        record = self.payment(9999)
        with self.assertRaises(ValidationError):
            post_revenue(record.pk, self.operator)
        self.assertFalse(InstructorEarning.objects.exists())
        self.assignment.delete()
        with self.assertRaises(ValidationError):
            post_revenue(record.pk, self.operator)

    def test_zero_payment_generates_no_royalty(self):
        record = self.post(0)
        self.assertEqual(record.earnings.get().amount, 0)

    def test_refund_rounding_cancels_exact_original_and_prevents_over_refund(self):
        self.assignment.fixed_amount = 10001
        self.assignment.save()
        record = self.post()
        for amount in (10000, 10000, 10000):
            refund = RefundRecord.objects.create(revenue=record, amount=amount, reason='부분 환불')
            self.assertTrue(post_refund(refund.pk, self.operator))
            self.assertFalse(post_refund(refund.pk, self.operator))
        self.assertEqual(sum(record.earnings.values_list('amount', flat=True)), 0)
        extra = RefundRecord.objects.create(revenue=record, amount=1, reason='초과')
        with self.assertRaises(ValidationError):
            post_refund(extra.pk, self.operator)
        refund.reason = '변경'
        with self.assertRaises(ValidationError):
            refund.save()

    def test_renewals_have_separate_unknown_transaction_and_terms(self):
        original = self.post()
        renewal = ReEnrollmentRequest.objects.create(user=self.student, course=self.course,
            enrollment=original.enrollment, status='approved', reason='재수강')
        record = renewal.revenue_record
        self.assertIsNone(record.amount)
        self.assertIsNone(record.received_on)
        record.amount, record.received_on = 12000, self.today
        record.save()
        post_revenue(record.pk, self.operator)
        self.assertEqual(record.earnings.get().amount, 10000)
        self.assertEqual(RevenueRecord.objects.count(), 2)

    def test_pending_renewal_does_not_create_income(self):
        enrollment = self.payment().enrollment
        ReEnrollmentRequest.objects.create(user=self.student, course=self.course, enrollment=enrollment, reason='대기')
        self.assertFalse(RevenueRecord.objects.filter(renewal__isnull=False).exists())

    def test_period_filters_and_instructor_isolation_include_csv(self):
        record = self.post()
        other_course = Course.objects.create(title='타 강사 비공개 매출', pricing_type='paid', price_krw=90000)
        TeachingAssignment.objects.create(instructor=self.other, course=other_course, fixed_amount=8765)
        enrollment = Enrollment.objects.create(user=self.student, course=other_course, payment_status='confirmed')
        other_record = enrollment.revenue_record
        other_record.amount = 90000
        other_record.save()
        post_revenue(other_record.pk, self.operator)
        self.client.force_login(self.teacher)
        for query in ({}, {'download': 'csv', 'instructor': self.other.pk}):
            response = self.client.get('/instructor/', query)
            self.assertContains(response, self.course.title)
            self.assertNotContains(response, other_course.title)
            self.assertNotContains(response, self.student.email)
            self.assertNotContains(response, self.student.username)
            self.assertIn('no-store', response['Cache-Control'])
        response = self.client.get('/instructor/', {'start': '2000-01-01', 'end': '2000-01-31', 'download': 'csv'})
        self.assertNotContains(response, '10000')
        self.assertEqual(self.client.get('/instructor/', {'start': 'bad', 'end': '2026-01-01'}).status_code, 400)
        self.assertEqual(self.client.get('/instructor/', {'start': '2026-02-01', 'end': '2026-01-01'}).status_code, 400)

    def test_csv_formula_text_is_escaped(self):
        self.course.title = '=FORMULA()'
        self.course.save()
        self.post()
        self.client.force_login(self.teacher)
        response = self.client.get('/instructor/', {'download': 'csv'})
        self.assertContains(response, "'=FORMULA()")

    def test_staff_only_posting_and_explicit_settlement_state_transitions(self):
        record = self.payment()
        with self.assertRaises(PermissionDenied):
            post_revenue(record.pk, self.teacher)
        post_revenue(record.pk, self.operator)
        rows = record.earnings.all()
        self.assertEqual(advance_earnings(rows, self.operator, paid=True), 0)
        self.assertEqual(advance_earnings(rows, self.operator), 1)
        self.assertEqual(advance_earnings(rows, self.operator), 0)
        self.assertEqual(advance_earnings(rows, self.operator, paid=True), 1)
        self.assertEqual(advance_earnings(rows, self.operator, paid=True), 0)
        earning = rows.get()
        self.assertEqual(earning.paid_by, self.operator)
        self.assertEqual(earning.confirmed_by, self.operator)

    def test_instructor_selector_does_not_list_students(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'instructors', 'model_name': 'teachingassignment', 'field_name': 'instructor'})
        ids = {int(row['id']) for row in response.json()['results']}
        self.assertEqual(ids, {self.teacher.pk, self.other.pk})

    def test_admin_posting_and_readonly_pages(self):
        record = self.payment()
        self.client.force_login(self.operator)
        response = self.client.post(reverse('admin:instructors_revenuerecord_changelist'), {
            'action': 'verify_and_calculate', '_selected_action': [record.pk]})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertIsNotNone(record.posted_at)
        response = self.client.get(reverse('admin:instructors_revenuerecord_change', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.post(reverse('admin:instructors_revenuerecord_change', args=[record.pk]), {'amount': 1}).status_code, 403)

    def test_teacher_still_needs_normal_enrollment_to_watch(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.lesson.get_absolute_url()).status_code, 403)
        Enrollment.objects.create(user=self.teacher, course=self.course, status='approved',
            start_date=self.today, end_date=self.today+timedelta(days=30))
        self.assertEqual(self.client.get(self.lesson.get_absolute_url()).status_code, 200)

    def test_legacy_import_preserves_unknown_amount_and_is_repeatable(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        source = Enrollment.objects.create(user=self.student, course=self.course)
        Enrollment.objects.filter(pk=source.pk).update(payment_status='confirmed', payment_confirmed_at=timezone.now())
        prepare = import_module('instructors.migrations.0002_prepare_existing_transactions').prepare_existing
        prepare(apps, SimpleNamespace(connection=connection))
        prepare(apps, SimpleNamespace(connection=connection))
        self.assertEqual(RevenueRecord.objects.filter(enrollment=source).count(), 1)
        record = RevenueRecord.objects.get(enrollment=source)
        self.assertIsNone(record.amount)
        self.assertIsNone(record.posted_at)
        self.assertEqual(record.received_on, self.today)


from concurrent.futures import ThreadPoolExecutor
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature


class ConcurrentSettlementTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_posting_and_refund_limits(self):
        operator = User.objects.create_user(username='staff1', is_staff=True)
        teacher = User.objects.create_user(username='teacher1', is_instructor=True)
        student = User.objects.create_user(username='student1')
        course = Course.objects.create(title='동시 처리', pricing_type='paid', price_krw=30000)
        TeachingAssignment.objects.create(instructor=teacher, course=course, fixed_amount=10000)
        enrollment = Enrollment.objects.create(user=student, course=course, payment_status='confirmed')
        record = enrollment.revenue_record
        record.amount = 30000
        record.save()

        def run(service, pk):
            try:
                return service(pk, operator)
            except ValidationError:
                return 'blocked'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pk: run(post_revenue, pk), [record.pk, record.pk]))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(record.earnings.count(), 1)
        record.refresh_from_db()
        refunds = [RefundRecord.objects.create(revenue=record, amount=20000, reason='동시 부분 환불') for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pk: run(post_refund, pk), [r.pk for r in refunds]))
        self.assertCountEqual(results, [True, 'blocked'])
        self.assertEqual(record.refunds.filter(posted_at__isnull=False).count(), 1)
