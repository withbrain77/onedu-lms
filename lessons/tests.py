from datetime import timedelta
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment

from .forms import LessonAdminForm, list_server_video_files, validate_server_video_file
from .models import HLSConversionJob, Lesson


class VideoProtectionAndWatermarkTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='student123',
            password='pass12345',
            name='홍길동',
        )
        self.other_student = User.objects.create_user(
            username='student456',
            password='pass12345',
            name='김수강',
        )
        self.admin = User.objects.create_user(
            username='admin_preview',
            password='pass12345',
            name='관리자',
            is_staff=True,
        )
        self.course = Course.objects.create(title='Video Protected Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Protected Video Lesson',
            order=1,
            duration_seconds=60,
            is_public=True,
        )
        self.lesson.video_file.save(
            'mvp25-test-video.mp4',
            ContentFile(b'test video bytes'),
            save=True,
        )
        self.watch_url = self.lesson.get_absolute_url()
        self.video_url = self.lesson.get_video_url()

    def tearDown(self):
        if self.lesson.video_file:
            try:
                self.lesson.video_file.delete(save=False)
            except PermissionError:
                pass
        hls_dir = Path(settings.PRIVATE_MEDIA_ROOT) / 'lesson_hls' / f'lesson-{self.lesson.pk}'
        shutil.rmtree(hls_dir, ignore_errors=True)

    def approve(self, user=None, start_offset=-1, end_offset=7):
        return Enrollment.objects.create(
            user=user or self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=start_offset),
            end_date=self.today + timedelta(days=end_offset),
        )

    def test_anonymous_user_cannot_open_video_page(self):
        response = self.client.get(self.watch_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_requested_student_cannot_open_video_page_or_file(self):
        Enrollment.objects.create(user=self.student, course=self.course)
        self.client.force_login(self.student)

        page_response = self.client.get(self.watch_url)
        file_response = self.client.get(self.video_url)

        self.assertEqual(page_response.status_code, 403)
        self.assertEqual(file_response.status_code, 404)

    def test_expired_student_cannot_open_video_page_or_file(self):
        self.approve(start_offset=-10, end_offset=-1)
        self.client.force_login(self.student)

        page_response = self.client.get(self.watch_url)
        file_response = self.client.get(self.video_url)

        self.assertEqual(page_response.status_code, 403)
        self.assertEqual(file_response.status_code, 404)

    def test_approved_student_can_open_video_page_and_file(self):
        self.approve()
        self.client.force_login(self.student)

        page_response = self.client.get(self.watch_url)
        file_response = self.client.get(self.video_url)

        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(file_response.status_code, 200)
        self.assertContains(page_response, self.video_url)
        file_response.close()

    @override_settings(USE_X_ACCEL_REDIRECT=True, X_ACCEL_REDIRECT_PREFIX='/protected-media/')
    def test_x_accel_redirect_header_can_be_used_for_private_video(self):
        self.approve()
        self.client.force_login(self.student)

        response = self.client.get(self.video_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['X-Accel-Redirect'].startswith('/protected-media/lesson_videos/'))
        self.assertTrue(response['X-Accel-Redirect'].endswith('.mp4'))
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response.content, b'')

    def test_watermark_uses_logged_in_student_identity(self):
        self.approve(user=self.student)
        self.approve(user=self.other_student)

        self.client.force_login(self.student)
        first_response = self.client.get(self.watch_url)
        self.client.force_login(self.other_student)
        second_response = self.client.get(self.watch_url)

        self.assertContains(first_response, '홍길동 / student123')
        self.assertContains(second_response, '김수강 / student456')
        self.assertNotContains(first_response, '김수강 / student456')

    def test_staff_preview_watermark_is_natural(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.watch_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '관리자 미리보기 / admin_preview')

    def test_template_does_not_expose_public_media_video_url(self):
        self.approve()
        self.client.force_login(self.student)

        response = self.client.get(self.watch_url)

        self.assertContains(response, self.video_url)
        self.assertNotContains(response, f'{settings.MEDIA_URL}lesson_videos/')

    def test_private_video_storage_has_no_public_url(self):
        with self.assertRaises(ValueError):
            _ = self.lesson.video_file.url

    def prepare_hls_files(self):
        private_root = Path(settings.PRIVATE_MEDIA_ROOT)
        hls_dir = private_root / 'lesson_hls' / f'lesson-{self.lesson.pk}'
        hls_dir.mkdir(parents=True, exist_ok=True)
        (hls_dir / 'index.m3u8').write_text(
            '#EXTM3U\n'
            '#EXT-X-VERSION:3\n'
            '#EXTINF:6.0,\n'
            'segment_00000.ts\n'
            '#EXT-X-ENDLIST\n',
            encoding='utf-8',
        )
        (hls_dir / 'segment_00000.ts').write_bytes(b'hls segment')
        self.lesson.hls_playlist_path = f'lesson_hls/lesson-{self.lesson.pk}/index.m3u8'
        self.lesson.hls_ready = True
        self.lesson.save(update_fields=['hls_playlist_path', 'hls_ready'])
        return hls_dir

    def test_hls_playlist_rewrites_segments_to_protected_urls(self):
        self.prepare_hls_files()
        self.approve()
        self.client.force_login(self.student)

        response = self.client.get(self.lesson.get_hls_playlist_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'/lessons/{self.lesson.pk}/hls/segment_00000.ts')
        self.assertNotContains(response, 'lesson_hls/')

    @override_settings(USE_X_ACCEL_REDIRECT=True, X_ACCEL_REDIRECT_PREFIX='/protected-media/')
    def test_hls_segment_uses_x_accel_redirect_when_enabled(self):
        self.prepare_hls_files()
        self.approve()
        self.client.force_login(self.student)

        response = self.client.get(reverse('lessons:hls_file', kwargs={'pk': self.lesson.pk, 'filename': 'segment_00000.ts'}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], f'/protected-media/lesson_hls/lesson-{self.lesson.pk}/segment_00000.ts')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response.content, b'')

    def test_requested_student_cannot_open_hls_playlist_or_segment(self):
        self.prepare_hls_files()
        Enrollment.objects.create(user=self.student, course=self.course)
        self.client.force_login(self.student)

        playlist_response = self.client.get(self.lesson.get_hls_playlist_url())
        segment_response = self.client.get(reverse('lessons:hls_file', kwargs={'pk': self.lesson.pk, 'filename': 'segment_00000.ts'}))

        self.assertEqual(playlist_response.status_code, 404)
        self.assertEqual(segment_response.status_code, 404)


class LessonAdminServerVideoFormTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.private_root = Path(self.temp_dir.name)
        self.course = Course.objects.create(title='Server File Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Server File Lesson',
            order=1,
            duration_seconds=0,
            is_public=True,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_private_file(self, relative_path, content=b'video'):
        path = self.private_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_server_video_choices_include_only_supported_lesson_videos(self):
        self.write_private_file('lesson_videos/large-video.mp4')
        self.write_private_file('lesson_videos/readme.txt')
        self.write_private_file('other/private-video.mp4')

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            choices = dict(list_server_video_files())

        self.assertIn('lesson_videos/large-video.mp4', choices)
        self.assertNotIn('lesson_videos/readme.txt', choices)
        self.assertNotIn('other/private-video.mp4', choices)

    def test_server_video_selection_sets_lesson_video_file_name(self):
        self.write_private_file('lesson_videos/large-video.mp4')
        data = {
            'course': self.course.pk,
            'title': self.lesson.title,
            'description': self.lesson.description,
            'server_video_file': 'lesson_videos/large-video.mp4',
            'order': self.lesson.order,
            'duration_seconds': 300,
            'is_public': 'on',
        }

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            form = LessonAdminForm(data=data, instance=self.lesson)
            self.assertTrue(form.is_valid(), form.errors.as_json())
            saved_lesson = form.save()

        self.assertEqual(saved_lesson.video_file.name, 'lesson_videos/large-video.mp4')

    def test_admin_form_renders_existing_private_video_without_public_url(self):
        self.lesson.video_file = 'lesson_videos/large-video.mp4'
        self.lesson.save(update_fields=['video_file'])
        self.write_private_file('lesson_videos/large-video.mp4')

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            form = LessonAdminForm(instance=self.lesson)
            rendered_form = form.as_p()

        self.assertIn('lesson_videos/large-video.mp4', rendered_form)
        self.assertNotIn('href=', rendered_form)

    def test_admin_change_page_shows_hls_queue_buttons(self):
        admin = User.objects.create_user(
            username='lesson_admin',
            password='pass12345',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(admin)

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            response = self.client.get(f'/admin/lessons/lesson/{self.lesson.pk}/change/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HLS 변환 요청')
        self.assertContains(response, 'HLS 재변환')

    @patch('lessons.admin.convert_lesson_hls_task.apply_async')
    def test_admin_hls_queue_uses_video_queue_and_stores_task_id(self, mocked_apply_async):
        admin = User.objects.create_user(
            username='lesson_admin_queue',
            password='pass12345',
            is_staff=True,
            is_superuser=True,
        )
        self.lesson.video_file = 'lesson_videos/large-video.mp4'
        self.lesson.save(update_fields=['video_file'])
        mocked_apply_async.return_value = Mock(id='task-123')
        self.client.force_login(admin)

        with override_settings(CELERY_VIDEO_QUEUE='video'):
            response = self.client.post(f'/admin/lessons/lesson/{self.lesson.pk}/queue-hls/')

        self.assertRedirects(response, f'/admin/lessons/lesson/{self.lesson.pk}/change/')
        mocked_apply_async.assert_called_once_with(args=(self.lesson.hls_jobs.get().pk,), queue='video')
        job = self.lesson.hls_jobs.get()
        self.assertEqual(job.status, HLSConversionJob.Status.PENDING)
        self.assertEqual(job.celery_task_id, 'task-123')

    @patch('lessons.admin.convert_lesson_hls_task.apply_async')
    def test_admin_hls_queue_marks_empty_task_id_as_failed(self, mocked_apply_async):
        admin = User.objects.create_user(
            username='lesson_admin_empty_task',
            password='pass12345',
            is_staff=True,
            is_superuser=True,
        )
        self.lesson.video_file = 'lesson_videos/large-video.mp4'
        self.lesson.save(update_fields=['video_file'])
        mocked_apply_async.return_value = Mock(id='')
        self.client.force_login(admin)

        response = self.client.post(f'/admin/lessons/lesson/{self.lesson.pk}/queue-hls/')

        self.assertRedirects(response, f'/admin/lessons/lesson/{self.lesson.pk}/change/')
        job = self.lesson.hls_jobs.get()
        self.assertEqual(job.status, HLSConversionJob.Status.FAILED)
        self.assertIn('empty task id', job.error_message)

    def test_server_video_selection_rejects_path_outside_lesson_video_folder(self):
        outside_path = self.private_root.parent / 'outside.mp4'
        outside_path.write_bytes(b'outside')
        self.addCleanup(lambda: outside_path.unlink(missing_ok=True))

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            with self.assertRaises(ValidationError):
                validate_server_video_file('../outside.mp4')

    def test_server_video_selection_rejects_unsupported_extension(self):
        self.write_private_file('lesson_videos/not-video.txt')

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            with self.assertRaises(ValidationError):
                validate_server_video_file('lesson_videos/not-video.txt')


class ConvertLessonHlsCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.private_root = Path(self.temp_dir.name)
        self.course = Course.objects.create(title='HLS Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='HLS Lesson',
            order=1,
            duration_seconds=60,
            is_public=True,
            video_file='lesson_videos/source.mp4',
        )
        source_path = self.private_root / 'lesson_videos' / 'source.mp4'
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b'source video')

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('lessons.services.hls.subprocess.run')
    def test_convert_lesson_hls_updates_lesson_hls_fields(self, mocked_run):
        def fake_run(command, check):
            playlist_path = Path(command[-1])
            playlist_path.parent.mkdir(parents=True, exist_ok=True)
            playlist_path.write_text('#EXTM3U\n#EXT-X-ENDLIST\n', encoding='utf-8')

        mocked_run.side_effect = fake_run

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            call_command('convert_lesson_hls', self.lesson.pk)

        self.lesson.refresh_from_db()

        self.assertTrue(self.lesson.hls_ready)
        self.assertEqual(self.lesson.hls_playlist_path, f'lesson_hls/lesson-{self.lesson.pk}/index.m3u8')
        self.assertIsNotNone(self.lesson.hls_converted_at)
        self.assertTrue(mocked_run.called)

    @patch('lessons.services.hls.probe_video_duration_seconds')
    @patch('lessons.services.hls.subprocess.run')
    def test_convert_lesson_hls_updates_missing_duration(self, mocked_run, mocked_probe):
        self.lesson.duration_seconds = 0
        self.lesson.save(update_fields=['duration_seconds'])
        mocked_probe.return_value = 5288

        def fake_run(command, check):
            playlist_path = Path(command[-1])
            playlist_path.parent.mkdir(parents=True, exist_ok=True)
            playlist_path.write_text('#EXTM3U\n#EXT-X-ENDLIST\n', encoding='utf-8')

        mocked_run.side_effect = fake_run

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            call_command('convert_lesson_hls', self.lesson.pk)

        self.lesson.refresh_from_db()

        self.assertEqual(self.lesson.duration_seconds, 5288)
        self.assertTrue(self.lesson.hls_ready)

    @patch('lessons.services.hls.subprocess.run')
    def test_convert_lesson_hls_clears_hls_fields_when_ffmpeg_fails(self, mocked_run):
        self.lesson.hls_ready = True
        self.lesson.hls_playlist_path = f'lesson_hls/lesson-{self.lesson.pk}/index.m3u8'
        self.lesson.save(update_fields=['hls_ready', 'hls_playlist_path'])
        mocked_run.side_effect = subprocess.CalledProcessError(1, ['ffmpeg'])

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            with self.assertRaisesMessage(Exception, 'ffmpeg failed'):
                call_command('convert_lesson_hls', self.lesson.pk)

        self.lesson.refresh_from_db()

        self.assertFalse(self.lesson.hls_ready)
        self.assertEqual(self.lesson.hls_playlist_path, '')
        self.assertIsNone(self.lesson.hls_converted_at)


class HLSConversionJobTaskTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.private_root = Path(self.temp_dir.name)
        self.admin = User.objects.create_user(username='admin', password='pass12345', is_staff=True)
        self.course = Course.objects.create(title='Queued HLS Course', is_public=True)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Queued HLS Lesson',
            order=1,
            duration_seconds=60,
            is_public=True,
            video_file='lesson_videos/source.mp4',
        )
        source_path = self.private_root / 'lesson_videos' / 'source.mp4'
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b'source video')

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('lessons.services.hls.subprocess.Popen')
    def test_hls_conversion_job_task_marks_success(self, mocked_popen):
        class FakeProcess:
            stdout = iter(['out_time_ms=30000000\n', 'out_time_ms=60000000\n', 'progress=end\n'])

            def wait(self):
                return 0

        def fake_popen(command, **kwargs):
            playlist_path = Path(command[-1])
            playlist_path.parent.mkdir(parents=True, exist_ok=True)
            playlist_path.write_text('#EXTM3U\n#EXT-X-ENDLIST\n', encoding='utf-8')
            return FakeProcess()

        mocked_popen.side_effect = fake_popen
        job = HLSConversionJob.objects.create(lesson=self.lesson, requested_by=self.admin, force=True)

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            from .tasks import convert_lesson_hls_task

            result = convert_lesson_hls_task.apply(args=(job.pk,), throw=True)

        self.assertTrue(result.successful())
        job.refresh_from_db()
        self.lesson.refresh_from_db()
        self.assertEqual(job.status, HLSConversionJob.Status.SUCCEEDED)
        self.assertEqual(job.progress_percent, 100)
        self.assertEqual(job.progress_current_seconds, 60)
        self.assertEqual(job.progress_total_seconds, 60)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
        self.assertTrue(self.lesson.hls_ready)

    @patch('lessons.services.hls.subprocess.Popen')
    def test_hls_conversion_job_task_marks_failure(self, mocked_popen):
        class FakeProcess:
            stdout = iter(['out_time_ms=12000000\n'])

            def wait(self):
                return 1

        mocked_popen.return_value = FakeProcess()
        job = HLSConversionJob.objects.create(lesson=self.lesson, requested_by=self.admin, force=True)

        with override_settings(PRIVATE_MEDIA_ROOT=str(self.private_root)):
            from .tasks import convert_lesson_hls_task

            with self.assertRaisesMessage(Exception, 'ffmpeg failed'):
                convert_lesson_hls_task.apply(args=(job.pk,), throw=True)

        job.refresh_from_db()
        self.assertEqual(job.status, HLSConversionJob.Status.FAILED)
        self.assertIn('ffmpeg failed', job.error_message)
        self.assertIsNotNone(job.finished_at)
