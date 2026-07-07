from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class Enrollment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', '승인 대기'
        APPROVED = 'approved', '승인됨'
        REJECTED = 'rejected', '반려됨'
        CANCELLED = 'cancelled', '취소됨'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='수강생',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    status = models.CharField(
        '상태',
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    start_date = models.DateField('수강 시작일', null=True, blank=True)
    end_date = models.DateField('수강 종료일', null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='승인자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_enrollments',
    )
    approved_at = models.DateTimeField('승인일시', null=True, blank=True)
    rejected_reason = models.TextField('반려 사유', blank=True)
    created_at = models.DateTimeField('신청일시', auto_now_add=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '수강 신청'
        verbose_name_plural = '수강 신청'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'course', 'status']),
            models.Index(fields=['status', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f'{self.user} - {self.course} ({self.get_status_display()})'

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('수강 종료일은 수강 시작일보다 빠를 수 없습니다.')

    def save(self, *args, **kwargs):
        if self.status == self.Status.APPROVED and self.approved_at is None:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_waiting(self):
        return self.status == self.Status.REQUESTED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED

    def is_within_period(self, today=None):
        if self.status != self.Status.APPROVED:
            return False
        if not self.start_date or not self.end_date:
            return False
        today = today or timezone.localdate()
        return self.start_date <= today <= self.end_date

    @property
    def has_ended(self):
        return bool(self.end_date and timezone.localdate() > self.end_date)

    @property
    def days_remaining(self):
        if not self.end_date:
            return None
        remaining = (self.end_date - timezone.localdate()).days
        return max(remaining, 0)
