from django.test import TestCase
from django.urls import reverse

from .models import User


class UsernameAvailabilityTests(TestCase):
    def setUp(self):
        User.objects.create_user(username='Taken123')
        self.url = reverse('accounts:username_availability')

    def test_checks_are_case_insensitive_and_do_not_reserve_names(self):
        for name, available in [('taken123', False), ('TAKEN123', False), ('newuser123', True)]:
            response = self.client.get(self.url, {'username': name})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['available'], available)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_names_and_post_are_rejected(self):
        for name in ('', 'username', '1234', 'user_name1', '가나다1', 'a'*20+'1', ' user123'):
            self.assertFalse(self.client.get(self.url, {'username': name}).json()['available'])
        self.assertEqual(self.client.post(self.url, {'username': 'newuser123'}).status_code, 405)

    def test_signup_still_checks_names_after_availability_response(self):
        self.assertTrue(self.client.get(self.url, {'username': 'newuser123'}).json()['available'])
        User.objects.create_user(username='newuser123')
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'newuser123', 'name': '새 회원', 'email': 'new@example.com',
            'password1': 'Learning-Unique-482!', 'password2': 'Learning-Unique-482!', 'privacy_agreement': 'on',
        })
        self.assertContains(response, '이미 사용 중인 아이디입니다.')
        self.assertEqual(User.objects.filter(username='newuser123').count(), 1)
