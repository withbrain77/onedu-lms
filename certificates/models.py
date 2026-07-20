import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import private_certificate_asset_storage


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


class CertificateDesign(models.Model):
    name = models.CharField('설정명', max_length=100, default='기본 수료증 디자인')
    is_active = models.BooleanField('사용 여부', default=True)
    certificate_title = models.CharField('수료증 제목', max_length=80, default='수 료 증')
    issuer_name = models.CharField('발급 기관명', max_length=120, default='위드브레인연구소')
    issuer_subtitle = models.CharField('발급 기관 보조 문구', max_length=160, blank=True, default='WITHBRAIN INSTITUTE')
    representative_name = models.CharField('대표자명', max_length=80, blank=True)
    completion_statement = models.CharField(
        '수료 문구',
        max_length=240,
        default='위 사람은 본 교육 과정을 성실히 이수하였음을 증명합니다.',
    )
    logo_image = models.FileField(
        '로고 이미지',
        storage=private_certificate_asset_storage,
        upload_to='certificate_assets/logos/',
        blank=True,
        help_text='PNG 또는 JPG 로고를 업로드합니다. 직접 URL로 공개되지 않습니다.',
    )
    seal_image = models.FileField(
        '직인 이미지',
        storage=private_certificate_asset_storage,
        upload_to='certificate_assets/seals/',
        blank=True,
        help_text='투명 배경 PNG 직인을 권장합니다. 직접 URL로 공개되지 않습니다.',
    )
    accent_color = models.CharField('포인트 색상', max_length=7, default='#007B74')
    footer_note = models.CharField(
        '하단 안내 문구',
        max_length=180,
        default='본 수료증은 ONEDU LMS 수료증 검증 페이지에서 진위 여부를 확인할 수 있습니다.',
    )
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '수료증 디자인 설정'
        verbose_name_plural = '수료증 디자인 설정'
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            CertificateDesign.objects.exclude(pk=self.pk).update(is_active=False)
