from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from courses.models import Course, CourseInvitation
from enrollments.models import Enrollment, ReEnrollmentRequest


class AdministratorActorChoiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(username='admin123')
        cls.staff = User.objects.create_user(username='staff123', is_staff=True)
        cls.student = User.objects.create_user(username='student123')
        cls.role_only = User.objects.create_user(username='role123', role=User.Role.ADMIN)

    def setUp(self):
        self.request = RequestFactory().get('/admin/')
        self.request.user = self.admin_user
        self.client.force_login(self.admin_user)

    def test_editable_administrator_fields_filter_choices_and_reject_nonstaff_ids(self):
        for model, field_name in (
            (Enrollment, 'approved_by'),
            (Enrollment, 'payment_confirmed_by'),
            (ReEnrollmentRequest, 'processed_by'),
            (Course, 'created_by'),
            (CourseInvitation, 'invited_by'),
        ):
            with self.subTest(model=model.__name__, field=field_name):
                form = admin.site._registry[model].get_form(self.request)()
                field = form.fields[field_name]
                self.assertSetEqual(set(field.queryset.values_list('pk', flat=True)),
                                    {self.admin_user.pk, self.staff.pk})
                for user in (self.admin_user, self.staff):
                    self.assertEqual(field.clean(str(user.pk)), user)
                for user in (self.student, self.role_only):
                    with self.assertRaises(ValidationError):
                        field.clean(str(user.pk))
                self.assertIsNone(field.clean(''))

    def test_approval_and_renewal_autocomplete_only_returns_staff(self):
        for model, field_name in ((Enrollment, 'approved_by'), (ReEnrollmentRequest, 'processed_by')):
            for term, expected in (('', {self.admin_user.pk, self.staff.pk}), ('student123', set())):
                with self.subTest(model=model.__name__, term=term):
                    response = self.client.get(reverse('admin:autocomplete'), {
                        'app_label': model._meta.app_label, 'model_name': model._meta.model_name,
                        'field_name': field_name, 'term': term,
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual({int(item['id']) for item in response.json()['results']}, expected)

    def test_student_and_invitee_selection_still_accepts_members(self):
        for model in (Enrollment, ReEnrollmentRequest, CourseInvitation):
            with self.subTest(model=model.__name__):
                form = admin.site._registry[model].get_form(self.request)()
                self.assertEqual(form.fields['user'].clean(str(self.student.pk)), self.student)
