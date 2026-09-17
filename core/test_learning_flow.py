from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.services.learning import continue_lesson, recent_learning
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from progress.models import WatchProgress


class LearningFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='learner-flow', password='TestPass12345!')
        self.course = Course.objects.create(title='학습 흐름', is_public=True)
        self.first = Lesson.objects.create(course=self.course, title='첫 차시', order=1, duration_seconds=100)
        self.second = Lesson.objects.create(course=self.course, title='다음 차시', order=2, duration_seconds=100)
        today = timezone.localdate()
        self.enrollment = Enrollment.objects.create(
            user=self.user, course=self.course, status=Enrollment.Status.APPROVED,
            start_date=today - timedelta(days=1), end_date=today + timedelta(days=7),
        )

    def login(self):
        self.client.force_login(self.user)

    def test_login_returns_to_lesson_and_preserves_replay_choice(self):
        target = self.first.get_absolute_url() + '?replay=1'
        page = self.client.get(reverse('accounts:login'), {'next': target})
        self.assertContains(page, 'name="next"')
        response = self.client.post(reverse('accounts:login'), {
            'username': self.user.username, 'password': 'TestPass12345!', 'next': target,
        })
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_login_rejects_external_redirects(self):
        for target in ['https://outside.example/path', '//outside.example/path', 'javascript:alert(1)']:
            self.client.logout()
            response = self.client.post(reverse('accounts:login'), {
                'username': self.user.username, 'password': 'TestPass12345!', 'next': target,
            })
            self.assertRedirects(response, reverse('enrollments:classroom'), fetch_redirect_response=False)

    def test_access_check_distinguishes_login_and_enrollment_expiry(self):
        url = reverse('lessons:access_status', args=[self.first.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'login_required')
        self.assertIn('no-store', response['Cache-Control'])
        self.login()
        self.assertTrue(self.client.get(url).json()['ok'])
        self.assertFalse(WatchProgress.objects.exists())
        self.enrollment.end_date = timezone.localdate() - timedelta(days=1)
        self.enrollment.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'ended')
        self.first.is_public = False
        self.first.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_progress_api_returns_json_for_expired_login(self):
        response = self.client.post(reverse('progress:save_lesson', args=[self.first.pk]), {}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'login_required')
        self.assertFalse(WatchProgress.objects.exists())

    def test_completion_threshold_does_not_skip_unwatched_ending(self):
        progress = WatchProgress.objects.create(
            user=self.user, enrollment=self.enrollment, lesson=self.first,
            duration_seconds=100, last_position_seconds=90, progress_percent=90, is_completed=True,
        )
        self.assertEqual(continue_lesson(self.enrollment), self.first)
        self.assertFalse(recent_learning(self.user).reached_end)
        progress.last_position_seconds = 100
        progress.save()
        self.assertEqual(continue_lesson(self.enrollment), self.second)
        self.assertEqual(recent_learning(self.user).next_lesson, self.second)
        self.login()
        self.assertContains(self.client.get(reverse('home')), '처음부터 복습')
        self.assertTrue(self.client.get(self.first.get_absolute_url()).context['lesson_reached_end'])
        self.assertFalse(self.client.get(self.first.get_absolute_url(), {'replay': '1'}).context['lesson_reached_end'])

    def test_next_lesson_excludes_hidden_lessons(self):
        WatchProgress.objects.create(user=self.user, enrollment=self.enrollment, lesson=self.first,
                                     duration_seconds=100, last_position_seconds=100, is_completed=True)
        self.second.is_public = False
        self.second.save()
        self.assertEqual(continue_lesson(self.enrollment), self.first)
        self.assertIsNone(recent_learning(self.user).next_lesson)

    def test_catalog_search_keeps_visibility_rules(self):
        private = Course.objects.create(title='비공개 학습 흐름', is_public=True, visibility=Course.Visibility.INVITE_ONLY)
        response = self.client.get(reverse('courses:list'), {'q': '학습'})
        self.assertEqual([card['course'] for card in response.context['course_cards']], [self.course])
        self.assertNotContains(response, private.title)
        response = self.client.get(reverse('courses:list'), {'q': '없는 제목'})
        self.assertEqual(response.context['course_cards'], [])
        self.assertContains(response, '검색 결과가 없습니다.')

    def test_classroom_tabs_and_search_do_not_mix_status_or_users(self):
        pending = Course.objects.create(title='대기 중 과정')
        Enrollment.objects.create(user=self.user, course=pending)
        stranger = User.objects.create_user(username='other-flow')
        private = Course.objects.create(title='다른 사용자 과정')
        Enrollment.objects.create(user=stranger, course=private)
        self.login()
        response = self.client.get(reverse('enrollments:classroom'))
        self.assertEqual(response.context['selected_status'], 'active')
        self.assertEqual([card['course'] for card in response.context['visible_cards']], [self.course])
        self.assertNotContains(response, pending.title)
        self.assertNotContains(response, private.title)
        response = self.client.get(reverse('enrollments:classroom'), {'status': 'waiting', 'q': '대기'})
        self.assertEqual([card['course'] for card in response.context['visible_cards']], [pending])
        response = self.client.get(reverse('enrollments:classroom'), {'status': 'waiting', 'q': '없음'})
        self.assertEqual(response.context['visible_cards'], [])
        self.assertContains(response, '검색 결과가 없습니다.')
