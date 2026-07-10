from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment

from .forms import LessonAdminForm, list_server_video_files, validate_server_video_file
from .models import Lesson


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
