from datetime import timedelta
import hashlib
import tarfile
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import AccessLog, User
from accounts.reports import build_student_learning_report
from core.models import Notice, ServerWarningAcknowledgement
from core.services.access import can_access_course
from core.tasks import create_nonvideo_backup_task
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson
from progress.models import WatchProgress


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

    @patch('core.views.random.sample')
    def test_home_page_shows_two_random_public_courses(self, mocked_sample):
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
        mocked_sample.return_value = [old_course.pk, newest_course.pk]

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        mocked_sample.assert_called_once()
        self.assertContains(response, 'Newest Public Program')
        self.assertContains(response, 'Old Public Program')
        self.assertNotContains(response, 'Middle Public Program')
        self.assertContains(response, '전체 프로그램 더보기')
        self.assertContains(response, reverse('courses:list'))

    def test_home_page_hides_invite_only_courses_from_public_programs(self):
        Course.objects.create(
            title='Public Home Program',
            description='Visible on home.',
            is_public=True,
            visibility=Course.Visibility.PUBLIC,
        )
        Course.objects.create(
            title='Invite Only Home Program',
            description='Should not be visible on public home.',
            is_public=True,
            visibility=Course.Visibility.INVITE_ONLY,
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Public Home Program')
        self.assertNotContains(response, 'Invite Only Home Program')

    def test_home_page_shows_latest_global_notice(self):
        Notice.objects.create(
            title='운영 점검 안내',
            content='주말 점검이 예정되어 있습니다.',
            is_published=True,
            is_pinned=True,
        )
        Course.objects.create(title='Notice Course', is_public=True)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '공지사항')
        self.assertContains(response, '운영 점검 안내')
        self.assertContains(response, reverse('notice_list'))

    def test_notice_list_and_detail_are_public(self):
        notice = Notice.objects.create(
            title='수강 안내',
            content='승인 후 수강할 수 있습니다.',
            is_published=True,
        )

        list_response = self.client.get(reverse('notice_list'))
        detail_response = self.client.get(reverse('notice_detail', kwargs={'notice_id': notice.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, '수강 안내')
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, '승인 후 수강할 수 있습니다.')

    def test_unpublished_notice_is_hidden(self):
        notice = Notice.objects.create(
            title='비공개 공지',
            content='숨김',
            is_published=False,
        )

        response = self.client.get(reverse('notice_detail', kwargs={'notice_id': notice.pk}))

        self.assertEqual(response.status_code, 404)

    def test_private_course_notice_is_hidden_from_public_notice_pages(self):
        private_course = Course.objects.create(title='Private Notice Course', is_public=False)
        notice = Notice.objects.create(
            title='비공개 강의 공지',
            content='숨김',
            course=private_course,
            is_published=True,
        )

        list_response = self.client.get(reverse('notice_list'))
        detail_response = self.client.get(reverse('notice_detail', kwargs={'notice_id': notice.pk}))

        self.assertNotContains(list_response, '비공개 강의 공지')
        self.assertEqual(detail_response.status_code, 404)

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
        self.assertContains(response, '20260718-server-logs')
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
        self.assertContains(response, '서버 로그')
        self.assertContains(response, 'onedu-admin-menu-direct')
        self.assertNotContains(response, '운영 현황')

    def test_admin_index_shows_recent_active_watchers(self):
        admin_user = User.objects.create_superuser(
            username='active_watch_admin',
            password='pass12345',
            email='active-watch-admin@example.com',
            name='Active Watch Admin',
        )
        student = User.objects.create_user(
            username='active_dash_student',
            password='pass12345',
            email='active-dash-student@example.com',
            name='Active Dashboard Student',
        )
        course = Course.objects.create(title='Active Dashboard Program', is_public=True)
        lesson = Lesson.objects.create(
            course=course,
            title='Active Dashboard Lesson',
            order=1,
            is_public=True,
        )
        enrollment = Enrollment.objects.create(
            user=student,
            course=course,
            status=Enrollment.Status.APPROVED,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=7),
        )
        WatchProgress.objects.create(
            user=student,
            enrollment=enrollment,
            lesson=lesson,
            progress_percent=35,
            last_position_seconds=120,
            total_watched_seconds=240,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LIVE LEARNING')
        self.assertContains(response, '현재 시청 중')
        self.assertContains(response, 'Active Dashboard Program')
        self.assertContains(response, 'Active Dashboard Lesson')
        self.assertContains(response, 'active_dash_student')

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
        self.assertContains(response, reverse('admin_server_logs'))

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
        self.assertContains(response, 'onedu-server-warning__button')
        self.assertContains(response, 'is-primary')
        self.assertContains(response, 'is-secondary')
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

    def test_staff_can_open_server_logs_page(self):
        admin_user = User.objects.create_superuser(
            username='server_logs_admin',
            password='pass12345',
            email='server-logs-admin@example.com',
            name='서버 로그 관리자',
        )
        self.client.force_login(admin_user)

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / 'onedu.log'
            log_file.write_text(
                '[2026-07-18 00:00:00] ERROR enrollments.notifications: smtp timeout\n'
                '[2026-07-18 00:00:01] INFO core.server_status: status checked\n',
                encoding='utf-8',
            )
            with override_settings(ONEDU_LOG_FILE=str(log_file)):
                response = self.client.get(reverse('admin_server_logs'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서버 로그')
        self.assertContains(response, 'smtp timeout')
        self.assertContains(response, 'onedu-server-log-view')
        self.assertContains(response, reverse('admin_server_ops'))

    def test_server_logs_requires_staff_login(self):
        response = self.client.get(reverse('admin_server_logs'))

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
        AccessLog.objects.create(
            user=student,
            event_type=AccessLog.EventType.LOGIN_SUCCESS,
            ip_address='203.0.113.10',
            device_summary='Chrome / Windows',
        )
        AccessLog.objects.create(
            user=student,
            event_type=AccessLog.EventType.LESSON_VIEW,
            ip_address='203.0.113.11',
            device_summary='Safari / iPhone',
            course_id_value=course.pk,
            course_title=course.title,
            is_suspicious=True,
            suspicious_reason='다른 접속 환경',
        )
        report = build_student_learning_report(student)
        self.assertEqual(report['summary']['distinct_ip_count'], 2)
        self.assertEqual(report['summary']['distinct_device_count'], 2)
        self.assertEqual(report['summary']['watch_risk_label'], '주의')
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:accounts_user_learning_report', args=[student.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '리포트 수강생 학습 리포트')
        self.assertContains(response, '리포트 강의')
        self.assertContains(response, '총 시청 시간')
        self.assertContains(response, '이용 패턴')

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

    def test_compose_enables_nonvideo_backup_volume_and_schedule_env(self):
        compose = (Path(settings.BASE_DIR) / 'docker-compose.yml').read_text(encoding='utf-8')

        self.assertIn('ONEDU_AUTOMATED_BACKUP_ENABLED', compose)
        self.assertIn('ONEDU_BACKUP_RETENTION_DAYS', compose)
        self.assertIn('${ONEDU_BACKUP_DIR:-./backups}:/vol/web/backups', compose)

    def test_nonvideo_backup_command_archives_media_and_private_attachments_without_videos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            media_root = temp_path / 'media'
            private_media_root = temp_path / 'private_media'
            backup_root = temp_path / 'backups'
            media_root.mkdir()
            private_media_root.mkdir()
            (media_root / 'guide.pdf').write_text('public guide', encoding='utf-8')
            (private_media_root / 'lesson_attachments').mkdir()
            (private_media_root / 'lesson_attachments' / 'slide.pdf').write_text('private slide', encoding='utf-8')
            (private_media_root / 'lesson_videos').mkdir()
            (private_media_root / 'lesson_videos' / 'lecture.mp4').write_text('video', encoding='utf-8')

            output = StringIO()
            with override_settings(
                MEDIA_ROOT=media_root,
                PRIVATE_MEDIA_ROOT=private_media_root,
                ONEDU_BACKUP_ROOT=backup_root,
                ONEDU_BACKUP_INCLUDE_PUBLIC_MEDIA=True,
                ONEDU_BACKUP_INCLUDE_PRIVATE_NONVIDEO=True,
                ONEDU_BACKUP_RETENTION_DAYS=30,
            ):
                call_command('create_nonvideo_backup', skip_db=True, stdout=output)

            media_archives = list((backup_root / 'media').glob('onedu_media_*.tar.gz'))
            self.assertEqual(len(media_archives), 1)
            with tarfile.open(media_archives[0], 'r:gz') as archive:
                names = archive.getnames()
            self.assertIn('media/guide.pdf', names)

            private_archives = list((backup_root / 'private_nonvideo').glob('onedu_private_nonvideo_*.tar.gz'))
            self.assertEqual(len(private_archives), 1)
            with tarfile.open(private_archives[0], 'r:gz') as archive:
                private_names = archive.getnames()
            self.assertIn('private_media/lesson_attachments/slide.pdf', private_names)
            self.assertNotIn('private_media/lesson_videos/lecture.mp4', private_names)

    def test_nonvideo_backup_task_respects_disabled_setting(self):
        with override_settings(ONEDU_AUTOMATED_BACKUP_ENABLED=False):
            self.assertEqual(create_nonvideo_backup_task.run(), 'disabled')

    def test_ops_readiness_command_reports_operational_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = StringIO()
            with override_settings(
                STATIC_ROOT=temp_path / 'static',
                MEDIA_ROOT=temp_path / 'media',
                PRIVATE_MEDIA_ROOT=temp_path / 'private_media',
                ONEDU_LOG_DIR=temp_path / 'logs',
            ):
                for path in (
                    settings.STATIC_ROOT,
                    settings.MEDIA_ROOT,
                    settings.PRIVATE_MEDIA_ROOT,
                    settings.ONEDU_LOG_DIR,
                ):
                    Path(path).mkdir(parents=True, exist_ok=True)
                call_command('ops_readiness', stdout=output)

        rendered = output.getvalue()
        self.assertIn('ONEDU 운영 점검', rendered)
        self.assertIn('입금 확인 대기', rendered)


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
