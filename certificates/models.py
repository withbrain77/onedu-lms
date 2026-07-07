import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def certificate_number():
    return f'ONEDU-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}'


def verification_code():
    return uuid.uuid4().hex


class Certificate(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='수강생',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    enrollment = models.OneToOneField(
        'enrollments.Enrollment',
        verbose_name='수강',
        on_delete=models.CASCADE,
        related_name='certificate',
    )
    certificate_no = models.CharField('수료증 번호', max_length=40, unique=True, default=certificate_number)
    verification_code = models.CharField('검증 코드', max_length=64, unique=True, default=verification_code)
    issued_at = models.DateTimeField('발급일시', auto_now_add=True)
    is_active = models.BooleanField('발급 상태', default=True)
    revoked_at = models.DateTimeField('취소일시', null=True, blank=True)
    pdf_file = models.FileField('PDF 파일', upload_to='certificates/', blank=True)

    class Meta:
        verbose_name = '수료증'
        verbose_name_plural = '수료증'
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['user', 'course']),
            models.Index(fields=['certificate_no']),
            models.Index(fields=['verification_code']),
        ]

    def __str__(self):
        return f'{self.certificate_no} - {self.user} - {self.course}'

    @property
    def is_revoked(self):
        return self.revoked_at is not None or not self.is_active
