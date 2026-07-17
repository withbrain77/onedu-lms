from datetime import timedelta
import hashlib
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import ServerWarningAcknowledgement
from core.services.access import can_access_course
from courses.models import Course
from enrollments.models import Enrollment


class HomePageTests(TestCase):
    def test_anonymous_user_sees_polished_home_page(self):
        Course.objects.create(
            title='IM 마스터스 세미나 2026',
            description='대표 강의 설명',
            is_public=True,
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '위드브레인연구소 교육·세미나 영상 아카이브')
        self.assertContains(response, '승인된 수강생에게 교육 영상과 세미나 영상을 제공')
        self.assertContains(response, '제한 공개')
        self.assertContains(response, 'archive-console')
        self.assertContains(response, 'portal-category-card')
        self.assertContains(response, '학습 이용 안내')
        self.assertContains(response, 'WITHBRAIN')
        self.assertContains(response, 'IM 마스터스 세미나 2026')
        self.assertContains(response, '&copy; 2026 WITHBRAIN INSTITUTE. All rights reserved.')
        self.assertContains(response, '교육 영상 및 강의자료의 무단 복제, 배포, 공유, 녹화, 캡처를 금합니다.')
        self.assertNotContains(response, 'withbrain-footer-logo.png')
        self.assertContains(response, reverse('accounts:login'))
        self.assertContains(response, reverse('accounts:signup'))
        self.assertContains(response, reverse('certificates:verify'))
        self.assertContains(response, reverse('privacy_policy'))

    def test_privacy_policy_is_public(self):
        response = self.client.get(reverse('privacy_policy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '개인정보 처리방침')
        self.assertContains(response, '접속 기록')
        self.assertContains(response, '부정 이용 방지')
        self.assertContains(response, 'withbrain77@daum.net')

    def test_home_page_shows_two_recent_public_courses(self):
        old_course = Course.objects.create(
            title='Old Public Program',
            description='Old public program.',
            is_public=True,
        )
        middle_course = Course.objects.create(
            title='Middle Public Program',
            description='Middle public program.',
            is_public=True,
        )
        newest_course = Course.objects.create(
            title='Newest Public Program',
            description='Newest public program.',
            is_public=True,
        )
        Course.objects.filter(pk=old_course.pk).update(created_at=timezone.now() - timedelta(days=2))
        Course.objects.filter(pk=middle_course.pk).update(created_at=timezone.now() - timedelta(days=1))
        Course.objects.filter(pk=newest_course.pk).update(created_at=timezone.now())

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Newest Public Program')
        self.assertContains(response, 'Middle Public Program')
        self.assertNotContains(response, 'Old Public Program')
        self.assertContains(response, '전체 프로그램 더보기')
        self.assertContains(response, reverse('courses:list'))

    def test_student_home_shows_home_page(self):
        course = Course.objects.create(
            title='Student Home Course',
            description='Visible to logged in students.',
            is_public=True,
        )
        user = User.objects.create_user(
            username='student_home',
            password='pass12345',
            name='수강생',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'WITHBRAIN VIDEO ARCHIVE')
        self.assertContains(response, reverse('enrollments:classroom'))
        self.assertContains(response, course.get_absolute_url())
        self.assertContains(response, '전체 프로그램')

    def test_staff_home_shows_home_page(self):
        admin_user = User.objects.create_superuser(
            username='home_admin',
            password='pass12345',
            email='home-admin@example.com',
            name='관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'WITHBRAIN VIDEO ARCHIVE')
        self.assertContains(response, reverse('admin:index'))


class CourseAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student1',
            password='pass12345',
            name='수강생',
        )
        self.course = Course.objects.create(title='업무 기본 교육', is_public=True)
        self.today = timezone.localdate()

    def test_course_requires_enrollment(self):
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'not_applied')

    def test_requested_enrollment_is_blocked(self):
        Enrollment.objects.create(user=self.user, course=self.course)
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'waiting_approval')

    def test_future_start_date_is_blocked(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=10),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'not_started')

    def test_expired_enrollment_is_blocked(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=10),
            end_date=self.today - timedelta(days=1),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'ended')

    def test_active_approved_enrollment_is_allowed(self):
        Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        result = can_access_course(self.user, self.course, today=self.today)
        self.assertTrue(result.allowed)
        self.assertEqual(result.code, 'allowed')


class AdminThemeTests(TestCase):
    def test_admin_login_uses_mobile_friendly_layout(self):
        response = self.client.get(reverse('admin:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onedu-admin-login')
        self.assertContains(response, 'onedu-admin-login-card')
        self.assertContains(response, 'ONEDU LMS 관리자')
        self.assertContains(response, 'WITHBRAIN 운영 콘솔')
        self.assertContains(response, 'css/admin.css')
        self.assertNotContains(response, 'onedu-admin-workspace')

    def test_admin_index_loads_custom_theme(self):
        admin_user = User.objects.create_superuser(
            username='admin',
            password='pass12345',
            email='admin@example.com',
            name='관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ONEDU LMS 관리자')
        self.assertContains(response, 'css/admin.css')
        self.assertContains(response, 'onedu-admin-workspace')
        self.assertContains(response, 'onedu-admin-sidebar')
        self.assertContains(response, '운영 대시보드')
        self.assertContains(response, '빠른 작업')
        self.assertContains(response, '최근 활동')
        self.assertContains(response, '주의 접속')
        self.assertContains(response, '접속 보안 확인')
        self.assertContains(response, reverse('admin_mobile_ops'))
        self.assertContains(response, reverse('admin_server_ops'))
        self.assertContains(response, '메일 발송 실패')
        self.assertContains(response, '오늘 자료 다운로드')
        self.assertContains(response, '운영 설정')
        self.assertContains(response, '서버 상태')
        self.assertContains(response, 'onedu-admin-menu-direct')
        self.assertNotContains(response, '운영 현황')

    def test_admin_model_pages_keep_operations_sidebar(self):
        admin_user = User.objects.create_superuser(
            username='admin_pages',
            password='pass12345',
            email='admin-pages@example.com',
            name='관리자',
        )
        self.client.force_login(admin_user)

        for url in (
            reverse('admin:accounts_user_changelist'),
            reverse('admin:enrollments_enrollment_changelist'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'onedu-admin-workspace')
                self.assertContains(response, 'onedu-admin-sidebar')
                self.assertContains(response, '운영 콘솔')
                self.assertContains(response, '접속 보안 로그')

    def test_staff_can_open_mobile_operations_page(self):
        admin_user = User.objects.create_superuser(
            username='mobile_admin',
            password='pass12345',
            email='mobile-admin@example.com',
            name='모바일 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin_mobile_ops'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '모바일 운영')
        self.assertContains(response, '수강 승인 대기')
        self.assertContains(response, '메일 확인 필요')
        self.assertContains(response, '최근 자료 다운로드')

    def test_staff_can_open_server_operations_page(self):
        admin_user = User.objects.create_superuser(
            username='server_admin',
            password='pass12345',
            email='server-admin@example.com',
            name='서버 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin_server_ops'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서버 상태')
        self.assertContains(response, '운영 설정')
        self.assertContains(response, '도메인 / IP')
        self.assertContains(response, '서비스 상태')
        self.assertContains(response, '저장소 사용량')
        self.assertContains(response, '트래픽 지표')
        self.assertContains(response, 'HLS 작업')

    @override_settings(USE_X_ACCEL_REDIRECT=False)
    def test_server_warning_links_to_related_area_and_can_be_acknowledged(self):
        admin_user = User.objects.create_superuser(
            username='server_warning_admin',
            password='pass12345',
            email='server-warning-admin@example.com',
            name='서버 경고 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin_server_ops'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="app:x_accel_disabled"')
        self.assertContains(response, '#serviceTitle')
        self.assertContains(response, '확인 완료')

        message = '운영 환경에서 X-Accel-Redirect 영상 보호 설정을 확인하세요.'
        response = self.client.post(
            reverse('admin_server_warning_ack'),
            {
                'warning_key': 'app:x_accel_disabled',
                'message_hash': hashlib.sha256(message.encode('utf-8')).hexdigest(),
                'message': message,
                'next': reverse('admin_server_ops'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ServerWarningAcknowledgement.objects.filter(
                warning_key='app:x_accel_disabled',
                acknowledged_by=admin_user,
            ).exists()
        )
        self.assertNotContains(response, 'value="app:x_accel_disabled"')

    def test_server_operations_requires_staff_login(self):
        response = self.client.get(reverse('admin_server_ops'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])

    def test_staff_can_open_student_learning_report(self):
        admin_user = User.objects.create_superuser(
            username='report_admin',
            password='pass12345',
            email='report-admin@example.com',
            name='리포트 관리자',
        )
        student = User.objects.create_user(
            username='report_student',
            password='pass12345',
            email='report-student@example.com',
            name='리포트 수강생',
        )
        course = Course.objects.create(title='리포트 강의', is_public=True)
        Enrollment.objects.create(user=student, course=course, status=Enrollment.Status.REQUESTED)
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:accounts_user_learning_report', args=[student.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '리포트 수강생 학습 리포트')
        self.assertContains(response, '리포트 강의')
        self.assertContains(response, '총 시청 시간')

    def test_user_changelist_learning_report_link_uses_visible_button_style(self):
        admin_user = User.objects.create_superuser(
            username='report_link_admin',
            password='pass12345',
            email='report-link-admin@example.com',
            name='리포트 링크 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:accounts_user_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onedu-admin-inline-button')
        self.assertContains(response, '학습 리포트')


class DeploymentConfigTests(TestCase):
    def test_compose_passes_enrollment_notification_env_to_web_container(self):
        compose = (Path(settings.BASE_DIR) / 'docker-compose.yml').read_text(encoding='utf-8')

        self.assertIn('ONEDU_NOTIFY_ENROLLMENT_REQUEST', compose)
        self.assertIn('ONEDU_ADMIN_NOTIFICATION_EMAIL:', compose)
        self.assertIn('ONEDU_ADMIN_NOTIFICATION_EMAILS:', compose)


class UIPreviewTests(TestCase):
    def test_ui_preview_requires_staff_login(self):
        response = self.client.get(reverse('ui_preview'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])

    def test_staff_can_open_ui_preview(self):
        admin_user = User.objects.create_superuser(
            username='ui_admin',
            password='pass12345',
            email='ui-admin@example.com',
            name='UI 관리자',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('ui_preview'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UI 시안 선택')
        self.assertContains(response, 'Clear Blue')
        self.assertContains(response, 'Modern SaaS')
        self.assertContains(response, 'Calm Academy')
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Learning Timeline')
        self.assertContains(response, 'Kanban Course Board')
        self.assertContains(response, 'Focus Player')
        self.assertContains(response, 'Admin Console')
