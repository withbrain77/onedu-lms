import csv
import io
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from .models import InstructorEarning, RefundRecord, RevenueRecord, TeachingAssignment
from .services import advance_earnings, post_refund, post_revenue


class InstructorEdgeCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.admin = User.objects.create_superuser(username='edgeadmin1', password='Only-test-579!')
        cls.teacher = User.objects.create_user(username='edgeteacher1', is_instructor=True)
        cls.student = User.objects.create_user(username='edgestudent1')
        cls.course = Course.objects.create(title='상세 점검 강의', pricing_type='paid', price_krw=30000)
        cls.lesson = Lesson.objects.create(course=cls.course, title='상세 점검 차시', order=1)
        cls.assignment = TeachingAssignment.objects.create(instructor=cls.teacher, course=cls.course,
            fixed_amount=10000, starts_on=cls.today-timedelta(days=365))

    def payment(self, day=None, amount=30000, post=True):
        source = Enrollment.objects.create(user=self.student, course=self.course, payment_status='confirmed')
        record = source.revenue_record
        record.amount = amount
        record.received_on = day or self.today
        record.save()
        if post:
            post_revenue(record.pk, self.admin)
            record.refresh_from_db()
        return record

    def assignment_data(self, **changes):
        data = dict(instructor=self.teacher.pk, course=self.course.pk, lesson='', method='fixed',
            fixed_amount=10000, allocation_percent='100', royalty_percent='0', applies_to_renewals='on',
            starts_on=self.assignment.starts_on.isoformat(), ends_on=self.today.isoformat(), note='종료 처리', _save='Save')
        data.update(changes)
        return data

    def test_revoked_instructor_contract_can_be_closed_without_changing_earned_amount(self):
        record = self.payment()
        User.objects.filter(pk=self.teacher.pk).update(is_instructor=False)
        self.assignment.ends_on = self.today
        self.assignment.save()
        self.assertEqual(record.earnings.get().amount, 10000)

    def test_admin_can_close_revoked_instructor_contract(self):
        self.payment()
        User.objects.filter(pk=self.teacher.pk).update(is_instructor=False)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:instructors_teachingassignment_change', args=[self.assignment.pk]),
                                    self.assignment_data())
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.ends_on, self.today)

    def test_admin_can_close_unposted_revoked_contract_but_not_replace_with_non_teacher(self):
        User.objects.filter(pk=self.teacher.pk).update(is_instructor=False)
        self.client.force_login(self.admin)
        url = reverse('admin:instructors_teachingassignment_change', args=[self.assignment.pk])
        response = self.client.post(url, self.assignment_data())
        self.assertEqual(response.status_code, 302)
        response = self.client.post(url, self.assignment_data(instructor=self.student.pk))
        self.assertEqual(response.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.instructor_id, self.teacher.pk)

    def test_revoked_instructor_cannot_be_assigned_to_a_new_course(self):
        User.objects.filter(pk=self.teacher.pk).update(is_instructor=False)
        another = Course.objects.create(title='새 강의')
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(instructor=self.teacher, course=another)

    def test_assigned_lesson_cannot_be_moved_to_another_course(self):
        self.assignment.lesson = self.lesson
        self.assignment.save()
        self.lesson.course = Course.objects.create(title='다른 강의')
        with self.assertRaises(ValidationError):
            self.lesson.full_clean()

    def test_stale_lesson_assignment_cannot_produce_royalties(self):
        self.assignment.lesson = self.lesson
        self.assignment.save()
        another = Course.objects.create(title='다른 강의')
        Lesson.objects.filter(pk=self.lesson.pk).update(course=another)
        record = self.payment(post=False)
        with self.assertRaises(ValidationError):
            post_revenue(record.pk, self.admin)
        self.assertFalse(record.earnings.exists())

    def test_rate_change_uses_payment_date_and_does_not_change_previous_earnings(self):
        yesterday = self.today-timedelta(days=1)
        self.assignment.ends_on = yesterday
        self.assignment.save()
        TeachingAssignment.objects.create(instructor=self.teacher, course=self.course,
            starts_on=self.today, fixed_amount=6000)
        old, new = self.payment(yesterday), self.payment(self.today)
        self.assertEqual(old.earnings.get().amount, 10000)
        self.assertEqual(new.earnings.get().amount, 6000)

    def test_refund_in_next_month_keeps_original_payment_and_paid_history(self):
        last_month = self.today.replace(day=1)-timedelta(days=1)
        record = self.payment(last_month)
        advance_earnings(record.earnings.all(), self.admin)
        advance_earnings(record.earnings.all(), self.admin, paid=True)
        refund = RefundRecord.objects.create(revenue=record, amount=30000, reason='다음 달 환불', refunded_on=self.today)
        post_refund(refund.pk, self.admin)
        self.client.force_login(self.teacher)
        old = self.client.get('/instructor/', {'start': last_month.isoformat(), 'end': last_month.isoformat()})
        self.assertEqual(old.context['gross'], 30000)
        self.assertEqual(old.context['totals']['paid'], 10000)
        new = self.client.get('/instructor/', {'start': self.today.isoformat(), 'end': self.today.isoformat()})
        self.assertEqual(new.context['gross'], 0)
        self.assertEqual(new.context['new_count'], 0)
        self.assertEqual(new.context['refund_total'], 30000)
        self.assertEqual(new.context['totals']['pending'], -10000)

    def test_same_teacher_multiple_lessons_does_not_double_count_course_revenue(self):
        self.assignment.lesson, self.assignment.fixed_amount = self.lesson, 5000
        self.assignment.save()
        second = Lesson.objects.create(course=self.course, title='두 번째 차시', order=2)
        TeachingAssignment.objects.create(instructor=self.teacher, course=self.course, lesson=second, fixed_amount=5000)
        self.payment()
        self.client.force_login(self.teacher)
        response = self.client.get('/instructor/')
        self.assertEqual(response.context['new_count'], 1)
        self.assertEqual(response.context['gross'], 30000)
        self.assertEqual(response.context['totals']['pending'], 10000)

    def test_pagination_and_export_include_all_own_rows_and_same_total(self):
        for _ in range(32):
            self.payment()
        self.client.force_login(self.teacher)
        response = self.client.get('/instructor/', {'page': 2})
        self.assertEqual(len(response.context['rows']), 2)
        self.assertEqual(response.context['totals']['pending'], 320000)
        self.assertEqual(response.context['new_count'], 32)
        exported = self.client.get('/instructor/', {'download': 'csv'})
        rows = list(csv.reader(io.StringIO(exported.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 33)
        self.assertEqual(sum(int(row[6]) for row in rows[1:]), 320000)

    def test_view_only_staff_cannot_forge_financial_actions(self):
        record = self.payment()
        viewer = User.objects.create_user(username='edgeviewer1', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_instructorearning'))
        self.client.force_login(viewer)
        url = reverse('admin:instructors_instructorearning_changelist')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'action': 'confirm_earnings', '_selected_action': [record.earnings.get().pk]})
        self.assertEqual(record.earnings.get().status, 'pending')

    def test_profile_post_cannot_self_promote(self):
        self.client.force_login(self.student)
        self.client.post('/accounts/profile/', {'name': '수강생', 'email': 'edge@example.invalid', 'phone': '',
            'is_instructor': 'on', 'is_staff': 'on', 'is_superuser': 'on', 'role': 'admin'})
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_instructor)
        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertEqual(self.student.role, 'student')

    def test_inactive_teacher_loses_existing_session_access(self):
        self.client.force_login(self.teacher)
        User.objects.filter(pk=self.teacher.pk).update(is_active=False)
        self.assertEqual(self.client.get('/instructor/').status_code, 302)
        self.assertEqual(self.client.get('/instructor/?download=csv').status_code, 302)

    def test_invalid_admin_source_and_dates_show_form_errors_instead_of_server_error(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:instructors_revenuerecord_add'), {
            'course': self.course.pk, 'amount': '-1', 'received_on': (self.today+timedelta(days=1)).isoformat(), '_save': 'Save'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RevenueRecord.objects.exists())
        response = self.client.post(reverse('admin:instructors_teachingassignment_add'), self.assignment_data(
            starts_on=self.today.isoformat(), ends_on=(self.today-timedelta(days=1)).isoformat()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TeachingAssignment.objects.count(), 1)

    def test_rejected_or_unconfirmed_payments_cannot_be_calculated(self):
        record = self.payment(post=False)
        Enrollment.objects.filter(pk=record.enrollment_id).update(payment_status='pending')
        with self.assertRaises(ValidationError):
            post_revenue(record.pk, self.admin)
        self.assertFalse(InstructorEarning.objects.exists())
