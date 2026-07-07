from datetime import timedelta

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
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
    is_completed = models.BooleanField('수료 여부', default=False)
    completed_at = models.DateTimeField('수료일시', null=True, blank=True)
    completion_progress_percent = models.PositiveSmallIntegerField('수료 판정 진도율', default=0)
    completion_note = models.TextField('수료 메모', blank=True)
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


class ReEnrollmentRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '대기'
        APPROVED = 'approved', '승인'
        REJECTED = 'rejected', '반려'

    DEFAULT_EXTENSION_DAYS = 30

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='신청자',
        on_delete=models.CASCADE,
        related_name='reenrollment_requests',
    )
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='reenrollment_requests',
    )
    enrollment = models.ForeignKey(
        Enrollment,
        verbose_name='기존 수강',
        on_delete=models.CASCADE,
        related_name='reenrollment_requests',
    )
    reason = models.TextField('신청 사유')
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField('요청일시', auto_now_add=True)
    processed_at = models.DateTimeField('처리일시', null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='처리 관리자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_reenrollment_requests',
    )
    admin_note = models.TextField('관리자 메모', blank=True)
    extension_start_date = models.DateField('연장 시작일', null=True, blank=True)
    extension_end_date = models.DateField('연장 종료일', null=True, blank=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '재수강 신청'
        verbose_name_plural = '재수강 신청'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'course', 'status']),
            models.Index(fields=['status', 'requested_at']),
            models.Index(fields=['processed_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['enrollment'],
                condition=Q(status='pending'),
                name='unique_pending_reenrollment_per_enrollment',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.course} ({self.get_status_display()})'

    def clean(self):
        if self.enrollment_id:
            if self.user_id and self.enrollment.user_id != self.user_id:
                raise ValidationError('기존 수강의 수강생과 재수강 신청자가 일치해야 합니다.')
            if self.course_id and self.enrollment.course_id != self.course_id:
                raise ValidationError('기존 수강의 강의와 재수강 신청 강의가 일치해야 합니다.')
            if self.enrollment.status != Enrollment.Status.APPROVED:
                raise ValidationError('승인된 수강에 대해서만 재수강을 신청할 수 있습니다.')
        if self.extension_start_date and self.extension_end_date:
            if self.extension_end_date < self.extension_start_date:
                raise ValidationError('연장 종료일은 연장 시작일보다 빠를 수 없습니다.')

    def set_default_extension_dates(self):
        if not self.extension_start_date:
            self.extension_start_date = timezone.localdate()
        if not self.extension_end_date:
            self.extension_end_date = self.extension_start_date + timedelta(days=self.DEFAULT_EXTENSION_DAYS)

    def apply_extension_to_enrollment(self):
        enrollment = self.enrollment
        enrollment.status = Enrollment.Status.APPROVED
        enrollment.start_date = self.extension_start_date
        enrollment.end_date = self.extension_end_date
        if self.processed_by_id:
            enrollment.approved_by = self.processed_by
        enrollment.approved_at = self.processed_at or timezone.now()
        enrollment.save(update_fields=['status', 'start_date', 'end_date', 'approved_by', 'approved_at', 'updated_at'])

    def save(self, *args, **kwargs):
        if self.status == self.Status.APPROVED:
            self.set_default_extension_dates()
        if self.status in (self.Status.APPROVED, self.Status.REJECTED) and self.processed_at is None:
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)
        if self.status == self.Status.APPROVED:
            self.apply_extension_to_enrollment()
