from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse

from .storage import private_video_storage


class Lesson(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField('차시명', max_length=200)
    description = models.TextField('차시 설명', blank=True)
    video_file = models.FileField(
        '영상 파일',
        upload_to='lesson_videos/',
        storage=private_video_storage,
        blank=True,
    )
    order = models.PositiveIntegerField('순서', default=1)
    duration_seconds = models.PositiveIntegerField('영상 길이(초)', default=0)
    hls_playlist_path = models.CharField('HLS 재생 목록 경로', max_length=500, blank=True)
    hls_ready = models.BooleanField('HLS 준비 완료', default=False)
    hls_converted_at = models.DateTimeField('HLS 변환일시', null=True, blank=True)
    is_public = models.BooleanField('공개 여부', default=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '차시'
        verbose_name_plural = '차시'
        ordering = ['course', 'order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['course', 'order'], name='unique_lesson_order_per_course'),
        ]

    def __str__(self):
        return f'{self.course.title} - {self.order}. {self.title}'

    def get_absolute_url(self):
        return reverse('lessons:detail', kwargs={'pk': self.pk})

    def get_video_url(self):
        return reverse('lessons:video', kwargs={'pk': self.pk})

    def get_hls_playlist_url(self):
        return reverse('lessons:hls_playlist', kwargs={'pk': self.pk})

    @property
    def has_hls(self):
        return self.hls_ready and bool(self.hls_playlist_path)


class LessonAttachment(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        verbose_name='차시',
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    title = models.CharField('자료명', max_length=200)
    file = models.FileField(
        '자료 파일',
        upload_to='lesson_attachments/',
        storage=private_video_storage,
    )
    description = models.TextField('자료 설명', blank=True)
    order = models.PositiveIntegerField('순서', default=1)
    is_public = models.BooleanField('공개 여부', default=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '학습 자료'
        verbose_name_plural = '학습 자료'
        ordering = ['lesson', 'order', 'id']

    def __str__(self):
        return f'{self.lesson} - {self.title}'

    def get_download_url(self):
        return reverse('lessons:attachment_download', kwargs={'pk': self.lesson_id, 'attachment_id': self.pk})

    @property
    def filename(self):
        if not self.file:
            return ''
        return Path(self.file.name).name


class LessonAttachmentDownload(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='수강생',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lesson_attachment_downloads',
    )
    attachment = models.ForeignKey(
        LessonAttachment,
        verbose_name='학습 자료',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='download_logs',
    )
    lesson = models.ForeignKey(
        Lesson,
        verbose_name='차시',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachment_download_logs',
    )
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachment_download_logs',
    )
    attachment_title = models.CharField('자료명', max_length=200, blank=True)
    filename = models.CharField('파일명', max_length=255, blank=True)
    ip_address = models.GenericIPAddressField('IP 주소', blank=True, null=True)
    user_agent = models.TextField('브라우저 원문', blank=True)
    device_summary = models.CharField('기기 정보', max_length=160, blank=True)
    downloaded_at = models.DateTimeField('다운로드 일시', auto_now_add=True)

    class Meta:
        verbose_name = '학습 자료 다운로드 이력'
        verbose_name_plural = '학습 자료 다운로드 이력'
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['user', '-downloaded_at']),
            models.Index(fields=['attachment', '-downloaded_at']),
            models.Index(fields=['course', '-downloaded_at']),
            models.Index(fields=['ip_address', '-downloaded_at']),
        ]

    def __str__(self):
        user_label = self.user.display_name if self.user_id else '알 수 없는 사용자'
        return f'{user_label} - {self.attachment_title or self.filename}'


class HLSConversionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '대기 중'
        RUNNING = 'running', '변환 중'
        SUCCEEDED = 'succeeded', '완료'
        FAILED = 'failed', '실패'

    lesson = models.ForeignKey(
        Lesson,
        verbose_name='차시',
        on_delete=models.CASCADE,
        related_name='hls_jobs',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='요청 관리자',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hls_conversion_jobs',
    )
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    force = models.BooleanField('기존 HLS 덮어쓰기', default=False)
    transcode = models.BooleanField('H.264/AAC 재인코딩', default=False)
    hls_time = models.PositiveIntegerField('세그먼트 길이(초)', default=6)
    progress_percent = models.PositiveSmallIntegerField('진행률(%)', default=0)
    progress_current_seconds = models.PositiveIntegerField('현재 변환 위치(초)', default=0)
    progress_total_seconds = models.PositiveIntegerField('전체 영상 길이(초)', default=0)
    celery_task_id = models.CharField('작업 큐 ID', max_length=255, blank=True)
    error_message = models.TextField('오류 메시지', blank=True)
    created_at = models.DateTimeField('요청일시', auto_now_add=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)
    started_at = models.DateTimeField('시작일시', null=True, blank=True)
    finished_at = models.DateTimeField('종료일시', null=True, blank=True)

    class Meta:
        verbose_name = 'HLS 변환 작업'
        verbose_name_plural = 'HLS 변환 작업'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.lesson} - {self.get_status_display()}'
