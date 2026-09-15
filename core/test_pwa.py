from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User


class HomeScreenInstallTests(TestCase):
    def test_public_manifest_opens_classroom_and_has_installable_icons(self):
        response = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        manifest = response.json()
        self.assertEqual(manifest['short_name'], '위드브레인')
        self.assertEqual(manifest['start_url'], reverse('enrollments:classroom'))
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual({icon['sizes'] for icon in manifest['icons']}, {'192x192', '512x512'})
        for size in (180, 192, 512):
            self.assertIsNotNone(finders.find(f'img/pwa/withbrain-{size}.png'))
        self.assertNotIn('sessionid', response.cookies)

    def test_home_and_install_page_expose_manifest_and_apple_icon(self):
        for route in ('home', 'install'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'rel="manifest"')
            self.assertContains(response, 'rel="apple-touch-icon"')
            self.assertContains(response, 'name="apple-mobile-web-app-title" content="위드브레인"')

    @override_settings(PUBLIC_SITE_URL='https://onedu.withbrain.kr')
    def test_install_guide_uses_public_classroom_address(self):
        response = self.client.get(reverse('install'))
        self.assertContains(response, 'https://onedu.withbrain.kr/classroom/')
        self.assertContains(response, 'Safari')
        self.assertContains(response, 'Chrome')
        self.assertContains(response, '카카오톡')

    def test_icon_start_requires_login_then_opens_students_classroom(self):
        start_url = self.client.get(reverse('pwa_manifest')).json()['start_url']
        response = self.client.get(start_url)
        self.assertRedirects(response, reverse('accounts:login') + '?next=' + start_url)
        User.objects.create_user(username='pwa_student', password='pass12345', name='학생')
        response = self.client.post(reverse('accounts:login'), {
            'username': 'pwa_student', 'password': 'pass12345', 'next': start_url,
        })
        self.assertRedirects(response, start_url)
        self.assertContains(self.client.get(start_url), 'data-install-banner')
