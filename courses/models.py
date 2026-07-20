from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.text import slugify


class Course(models.Model):
    class PricingType(models.TextChoices):
        FREE = 'free', '무료'
        PAID = 'paid', '유료'

    class Visibility(models.TextChoices):
        PUBLIC = 'public', '공개'
        INVITE_ONLY = 'invite_only', '초대 전용'
        PRIVATE = 'private', '비공개'

    title = models.CharField('강의명', max_length=200)
    slug = models.SlugField('URL 슬러그', max_length=220, unique=True, blank=True, allow_unicode=True)
    description = models.TextField('강의 설명', blank=True)
    thumbnail = models.FileField('썸네일', upload_to='course_thumbnails/', blank=True)
    is_public = models.BooleanField('공개 여부', default=True)
    visibility = models.CharField(
        '공개 방식',
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
        help_text='공개는 모든 회원이 볼 수 있고, 초대 전용은 지정한 회원만 목록과 상세를 볼 수 있습니다.',
    )
    pricing_type = models.CharField(
        '과금 유형',
        max_length=10,
        choices=PricingType.choices,
        default=PricingType.FREE,
    )
    price_krw = models.PositiveIntegerField('이용료(원)', default=0)
    default_enrollment_days = models.PositiveSmallIntegerField('기본 수강 기간(일)', default=30)
    required_progress_percent = models.PositiveSmallIntegerField('수료 진도 기준(%)', default=90)
    require_quiz_pass = models.BooleanField('시험 합격 필요', default=True)
    certificate_enabled = models.BooleanField('수료증 발급 사용', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='생성자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
    )
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '강의'
        verbose_name_plural = '강의'
        ordering = ['title']

    def __str__(self):
        return self.title

    def clean(self):
        if self.pricing_type == self.PricingType.FREE and self.price_krw:
            raise ValidationError({'price_krw': '무료 강의는 이용료를 0원으로 설정해 주세요.'})
        if self.pricing_type == self.PricingType.PAID and self.price_krw <= 0:
            raise ValidationError({'price_krw': '유료 강의는 이용료를 1원 이상 입력해 주세요.'})
        if self.default_enrollment_days <= 0:
            raise ValidationError({'default_enrollment_days': '기본 수강 기간은 1일 이상이어야 합니다.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or 'course'
            candidate = base_slug
            index = 2
            while Course.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base_slug}-{index}'
                index += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('courses:detail', kwargs={'slug': self.slug})

    @property
    def lesson_count(self):
        return self.lessons.filter(is_public=True).count()

    @property
    def is_free(self):
        return self.pricing_type == self.PricingType.FREE

    @property
    def is_paid(self):
        return self.pricing_type == self.PricingType.PAID

    @property
    def is_listed(self):
        return self.is_public and self.visibility == self.Visibility.PUBLIC

    @property
    def is_invite_only(self):
        return self.is_public and self.visibility == self.Visibility.INVITE_ONLY

    @property
    def is_private(self):
        return (not self.is_public) or self.visibility == self.Visibility.PRIVATE

    @property
    def visibility_label(self):
        return self.get_visibility_display()

    @property
    def price_label(self):
        if self.is_free:
            return '무료'
        return f'{self.price_krw:,}원'

    @property
    def approval_policy_label(self):
        if self.is_invite_only:
            return '초대 회원만 신청 가능'
        if self.is_free:
            return '신청 즉시 수강 가능'
        return '운영자 확인 후 승인'

    @property
    def access_period_label(self):
        if self.is_free:
            return f'신청 즉시 {self.default_enrollment_days}일'
        return '승인 후 배정'


class CourseInvitation(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='초대 회원',
        on_delete=models.CASCADE,
        related_name='course_invitations',
    )
    active = models.BooleanField('활성', default=True)
    note = models.CharField('메모', max_length=255, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='초대한 관리자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_course_invitations',
    )
    created_at = models.DateTimeField('초대일시', auto_now_add=True)

    class Meta:
        verbose_name = '강의 초대 회원'
        verbose_name_plural = '강의 초대 회원'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['course', 'user'], name='unique_course_invitation_per_user'),
        ]
        indexes = [
            models.Index(fields=['course', 'active']),
            models.Index(fields=['user', 'active']),
        ]

    def __str__(self):
        return f'{self.course} - {self.user}'
