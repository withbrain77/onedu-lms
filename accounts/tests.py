from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from .models import User


class LoginPageTests(TestCase):
    def test_base_navigation_shows_home_link(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/">홈</a>')

    def test_login_page_shows_operator_support_information(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'login-support-company')
        self.assertContains(response, '위드브레인연구소(WITHBRAIN INSTITUTE)')
        self.assertContains(response, '02-569-7308')
        self.assertContains(response, 'withbrain77@daum.net')
        self.assertContains(response, '평일 09:00-18:00')
        self.assertContains(response, reverse('accounts:find_username'))
        self.assertContains(response, reverse('accounts:password_reset'))


class SignupPageTests(TestCase):
    def test_signup_page_shows_live_password_feedback(self):
        response = self.client.get(reverse('accounts:signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-password-feedback-form')
        self.assertContains(response, 'data-password-rule="length"')
        self.assertContains(response, 'data-password-rule="common"')
        self.assertContains(response, 'data-password-rule="numeric"')
        self.assertContains(response, 'data-password-rule="similar"')
        self.assertContains(response, 'data-password-rule="match"')
        self.assertContains(response, 'signup_password_feedback.js')


class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student01',
            password='Oldpass12345',
            name='홍길동',
            email='student@example.com',
        )

    def test_find_username_with_matching_name_and_email(self):
        response = self.client.post(
            reverse('accounts:find_username'),
            {
                'name': '홍길동',
                'email': 'student@example.com',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '일치하는 계정을 찾았습니다.')
        self.assertContains(response, 'student01')

    def test_find_username_shows_clear_message_when_no_match(self):
        response = self.client.post(
            reverse('accounts:find_username'),
            {
                'name': '홍길동',
                'email': 'wrong@example.com',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '계정을 찾을 수 없습니다')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_email_without_revealing_account_match(self):
        response = self.client.post(
            reverse('accounts:password_reset'),
            {'email': 'student@example.com'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('student01', mail.outbox[0].body)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        PUBLIC_SITE_URL='https://lms.example.com',
        ALLOWED_HOSTS=['192.168.0.97'],
    )
    def test_password_reset_uses_public_site_url_when_configured(self):
        response = self.client.post(
            reverse('accounts:password_reset'),
            {'email': 'student@example.com'},
            HTTP_HOST='192.168.0.97:8080',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://lms.example.com/accounts/reset/', mail.outbox[0].body)
        self.assertNotIn('192.168.0.97:8080/accounts/reset/', mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        PUBLIC_SITE_URL='',
        USE_X_FORWARDED_HOST=True,
        ALLOWED_HOSTS=['onedu.withbrain.kr'],
    )
    def test_password_reset_uses_forwarded_https_host(self):
        response = self.client.post(
            reverse('accounts:password_reset'),
            {'email': 'student@example.com'},
            HTTP_HOST='127.0.0.1:8080',
            HTTP_X_FORWARDED_HOST='onedu.withbrain.kr',
            HTTP_X_FORWARDED_PROTO='https',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://onedu.withbrain.kr/accounts/reset/', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_unknown_email_still_shows_done_page(self):
        response = self.client.post(
            reverse('accounts:password_reset'),
            {'email': 'unknown@example.com'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
