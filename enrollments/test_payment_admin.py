from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from courses.models import Course
from .admin import EnrollmentAdminForm


class PaymentAdministratorChoiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin123', password='Test-only-482!')
        self.staff = User.objects.create_user(username='staff123', is_staff=True)
        self.student = User.objects.create_user(username='student123')
        self.role_only = User.objects.create_user(username='role123', role=User.Role.ADMIN, is_staff=False)
        self.course = Course.objects.create(title='Paid course', pricing_type='paid', price_krw=30000)
        self.client.force_login(self.admin)

    def choices(self, field, term=''):
        response = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'enrollments', 'model_name': 'enrollment', 'field_name': field, 'term': term,
        })
        self.assertEqual(response.status_code, 200)
        return {int(item['id']) for item in response.json()['results']}

    def test_payment_search_only_returns_staff_without_filtering_students_elsewhere(self):
        self.assertEqual(self.choices('payment_confirmed_by'), {self.admin.pk, self.staff.pk})
        self.assertEqual(self.choices('payment_confirmed_by', 'student123'), set())
        self.assertEqual(self.choices('user', 'student123'), {self.student.pk})
        self.assertEqual(self.choices('user', 'role123'), {self.role_only.pk})

    def test_form_rejects_nonstaff_ids_even_when_submitted_directly(self):
        for user, valid in ((self.admin, True), (self.staff, True), (self.student, False), (self.role_only, False)):
            with self.subTest(username=user.username):
                form = EnrollmentAdminForm(data={
                    'user': self.student.pk, 'course': self.course.pk, 'status': 'requested',
                    'payment_status': 'confirmed', 'payment_confirmed_by': user.pk,
                    'completion_progress_percent': 0,
                })
                self.assertEqual(form.is_valid(), valid, form.errors)
                if not valid:
                    self.assertIn('payment_confirmed_by', form.errors)
