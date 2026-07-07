from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class WatchProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='수강생',
        on_delete=models.CASCADE,
        related_name='watch_progresses',
    )
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        verbose_name='수강',
        on_delete=models.CASCADE,
        related_name='watch_progresses',
    )
    lesson = models.ForeignKey(
        'lessons.Lesson',
        verbose_name='차시',
        on_delete=models.CASCADE,
        related_name='watch_progresses',
    )
    last_position_seconds = models.PositiveIntegerField('마지막 시청 위치(초)', default=0)
    total_watched_seconds = models.PositiveIntegerField('총 시청 시간(초)', default=0)
    duration_seconds = models.PositiveIntegerField('전체 길이(초)', default=0)
    progress_percent = models.PositiveSmallIntegerField('진도율', default=0)
    is_completed = models.BooleanField('시청 완료', default=False)
    completed_at = models.DateTimeField('완료일시', null=True, blank=True)
    last_watched_at = models.DateTimeField('마지막 시청일시', auto_now=True)
    created_at = models.DateTimeField('생성일시', auto_now_add=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '시청 진도'
        verbose_name_plural = '시청 진도'
        ordering = ['-last_watched_at']
        constraints = [
            models.UniqueConstraint(fields=['enrollment', 'lesson'], name='unique_progress_per_lesson'),
        ]

    def __str__(self):
        return f'{self.user} - {self.lesson} ({self.progress_percent}%)'

    def clean(self):
        if self.enrollment_id and self.lesson_id:
            if self.enrollment.course_id != self.lesson.course_id:
                raise ValidationError('수강 강의와 차시의 강의가 일치해야 합니다.')
            if self.user_id != self.enrollment.user_id:
                raise ValidationError('진도 사용자와 수강생이 일치해야 합니다.')

    def mark_position(
        self,
        position_seconds,
        duration_seconds=None,
        watched_increment_seconds=0,
        completed=False,
    ):
        self.last_position_seconds = max(int(position_seconds), 0)
        if duration_seconds is not None:
            self.duration_seconds = max(int(duration_seconds), 0)
        self.total_watched_seconds += max(int(watched_increment_seconds), 0)
        if self.duration_seconds:
            self.progress_percent = min(
                int((self.last_position_seconds / self.duration_seconds) * 100),
                100,
            )
        if completed:
            self.progress_percent = 100
            if self.duration_seconds:
                self.last_position_seconds = max(self.last_position_seconds, self.duration_seconds)
        if (self.progress_percent >= 90 or completed) and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
