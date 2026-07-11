from django.test import TestCase
from django.urls import reverse


class LoginPageTests(TestCase):
    def test_login_page_shows_operator_support_information(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'login-support-company')
        self.assertContains(response, '위드브레인연구소(WITHBRAIN INSTITUTE)')
        self.assertContains(response, '02-569-7308')
        self.assertContains(response, 'withbrain77@daum.net')
        self.assertContains(response, '평일 09:00-18:00')
