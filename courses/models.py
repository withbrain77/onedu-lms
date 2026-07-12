from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.text import slugify


class Course(models.Model):
    class PricingType(models.TextChoices):
        FREE = 'free', '무료'
        PAID = 'paid', '유료'

    title = models.CharField('강의명', max_length=200)
    slug = models.SlugField('URL 슬러그', max_length=220, unique=True, blank=True, allow_unicode=True)
    description = models.TextField('강의 설명', blank=True)
    thumbnail = models.FileField('썸네일', upload_to='course_thumbnails/', blank=True)
    is_public = models.BooleanField('공개 여부', default=True)
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
    def price_label(self):
        if self.is_free:
            return '무료'
        return f'{self.price_krw:,}원'

    @property
    def approval_policy_label(self):
        if self.is_free:
            return '신청 즉시 수강 가능'
        return '운영자 확인 후 승인'

    @property
    def access_period_label(self):
        if self.is_free:
            return f'신청 즉시 {self.default_enrollment_days}일'
        return '승인 후 배정'
