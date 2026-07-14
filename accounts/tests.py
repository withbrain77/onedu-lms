from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from .models import AccessLog, User
from .views import REMEMBER_USERNAME_COOKIE


class LoginPageTests(TestCase):
    def test_base_navigation_shows_home_link(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/">홈</a>')
        self.assertContains(response, 'WITHBRAIN ONEDU TRAINING SYSTEM')

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

    def test_login_page_shows_remember_username_checkbox(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '아이디 기억하기')
        self.assertContains(response, 'name="remember_username"')

    def test_login_page_prefills_remembered_username(self):
        self.client.cookies[REMEMBER_USERNAME_COOKIE] = 'remembered_student'

        response = self.client.get(reverse('accounts:login'))

        self.assertContains(response, 'value="remembered_student"')
        self.assertContains(response, 'name="remember_username"')
        self.assertContains(response, 'checked')

    def test_successful_login_can_remember_username(self):
        User.objects.create_user(
            username='student01',
            password='StrongPass12345!',
            name='테스트 수강생',
        )

        response = self.client.post(
            reverse('accounts:login'),
            {
                'username': 'student01',
                'password': 'StrongPass12345!',
                'remember_username': 'on',
            },
            HTTP_X_FORWARDED_FOR='203.0.113.10',
            HTTP_USER_AGENT='Mozilla/5.0 Windows Chrome/120.0',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[REMEMBER_USERNAME_COOKIE].value, 'student01')
        log = AccessLog.objects.get(user__username='student01', event_type=AccessLog.EventType.LOGIN_SUCCESS)
        self.assertEqual(log.ip_address, '203.0.113.10')
        self.assertEqual(log.device_summary, 'Windows PC / Chrome')

    def test_successful_login_without_remembering_deletes_existing_username_cookie(self):
        User.objects.create_user(
            username='student02',
            password='StrongPass12345!',
            name='테스트 수강생',
        )
        self.client.cookies[REMEMBER_USERNAME_COOKIE] = 'old_student'

        response = self.client.post(
            reverse('accounts:login'),
            {
                'username': 'student02',
                'password': 'StrongPass12345!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[REMEMBER_USERNAME_COOKIE].value, '')
        self.assertEqual(response.cookies[REMEMBER_USERNAME_COOKIE]['max-age'], 0)


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
        self.assertContains(response, 'name="privacy_agreement"')
        self.assertContains(response, 'data-privacy-consent-box')
        self.assertContains(response, 'data-privacy-consent-error')
        self.assertContains(response, reverse('privacy_policy'))

    def test_signup_requires_privacy_agreement(self):
        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'privacy_student',
                'name': 'Privacy Student',
                'email': 'privacy@example.com',
                'phone': '010-2222-3333',
                'password1': 'StrongPass12345!',
                'password2': 'StrongPass12345!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '개인정보 처리방침에 동의해 주세요.')
        self.assertContains(response, 'privacy-consent-box-invalid')
        self.assertFalse(User.objects.filter(username='privacy_student').exists())

    def test_signup_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(
            username='existing_user',
            password='Oldpass12345',
            name='Existing User',
            email='student@example.com',
        )

        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'new_student',
                'name': 'New Student',
                'email': 'STUDENT@example.com',
                'phone': '010-1234-5678',
                'password1': 'StrongPass12345!',
                'password2': 'StrongPass12345!',
                'privacy_agreement': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '이미 가입된 이메일 주소입니다')
        self.assertFalse(User.objects.filter(username='new_student').exists())


class ProfileManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student_profile',
            password='Oldpass12345!',
            name='기존 이름',
            email='old@example.com',
            phone='010-1111-2222',
        )
        self.other = User.objects.create_user(
            username='other_profile',
            password='Oldpass12345!',
            name='다른 사용자',
            email='other@example.com',
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_logged_in_user_can_view_profile_and_nav_link(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('accounts:profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '내 정보 수정')
        self.assertContains(response, 'student_profile')
        self.assertContains(response, 'old@example.com')
        self.assertContains(response, reverse('accounts:password_change'))
        self.assertContains(response, reverse('accounts:profile'))

    def test_user_can_update_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('accounts:profile'),
            {
                'name': '변경 이름',
                'email': 'NEW@example.com',
                'phone': '010-9999-0000',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, '변경 이름')
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertEqual(self.user.phone, '010-9999-0000')

    def test_profile_rejects_duplicate_email_case_insensitively(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('accounts:profile'),
            {
                'name': '변경 이름',
                'email': 'OTHER@example.com',
                'phone': '010-9999-0000',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '이미 다른 계정에서 사용 중인 이메일 주소입니다')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.com')

    def test_password_change_requires_login(self):
        response = self.client.get(reverse('accounts:password_change'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_user_can_change_password_and_keep_session(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('accounts:password_change'),
            {
                'old_password': 'Oldpass12345!',
                'new_password1': 'Newpass12345!',
                'new_password2': 'Newpass12345!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Newpass12345!'))
        self.assertFalse(self.user.check_password('Oldpass12345!'))

        profile_response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(profile_response.status_code, 200)


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
