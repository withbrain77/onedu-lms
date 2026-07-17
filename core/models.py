from django.conf import settings
from django.db import models
from django.utils import timezone


class Notice(models.Model):
    title = models.CharField('제목', max_length=160)
    content = models.TextField('내용')
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='관련 강의',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notices',
    )
    is_published = models.BooleanField('공개 여부', default=True)
    is_pinned = models.BooleanField('상단 고정', default=False)
    published_at = models.DateTimeField('공개일시', default=timezone.now)
    created_at = models.DateTimeField('생성일시', auto_now_add=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '공지사항'
        verbose_name_plural = '공지사항'
        ordering = ['-is_pinned', '-published_at', '-created_at']
        indexes = [
            models.Index(fields=['is_published', '-published_at']),
            models.Index(fields=['course', 'is_published', '-published_at']),
        ]

    def __str__(self):
        return self.title

    @property
    def scope_label(self):
        return self.course.title if self.course_id else '전체 공지'


class ServerWarningAcknowledgement(models.Model):
    warning_key = models.CharField('경고 키', max_length=120)
    message_hash = models.CharField('메시지 해시', max_length=64)
    message = models.TextField('확인한 메시지', blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='확인 관리자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='server_warning_acknowledgements',
    )
    acknowledged_at = models.DateTimeField('확인 일시', auto_now_add=True)

    class Meta:
        verbose_name = '서버 경고 확인'
        verbose_name_plural = '서버 경고 확인'
        unique_together = ('warning_key', 'message_hash')
        ordering = ['-acknowledged_at']
        indexes = [
            models.Index(fields=['warning_key', 'message_hash']),
            models.Index(fields=['-acknowledged_at']),
        ]

    def __str__(self):
        return f'{self.warning_key} / {self.acknowledged_at:%Y-%m-%d %H:%M}'
