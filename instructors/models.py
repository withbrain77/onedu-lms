from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class TeachingAssignment(models.Model):
    class Method(models.TextChoices):
        FIXED = 'fixed', '유료 수강 1건당 정액'
        PERCENT = 'percent', '실제 입금액의 일정 비율'

    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='담당 강사',
        on_delete=models.PROTECT, related_name='teaching_assignments',
        limit_choices_to={'is_instructor': True})
    course = models.ForeignKey('courses.Course', verbose_name='강의', on_delete=models.PROTECT)
    lesson = models.ForeignKey('lessons.Lesson', verbose_name='담당 차시', on_delete=models.PROTECT,
        null=True, blank=True, help_text='강의 전체를 담당하면 비워 두세요.')
    method = models.CharField('지급 방식', max_length=10, choices=Method.choices, default=Method.FIXED)
    fixed_amount = models.PositiveIntegerField('건당 지급액(원)', default=0,
        help_text='이 강사에게 지급할 금액입니다. 실제 입금액이 0원이면 발생하지 않습니다.')
    allocation_percent = models.DecimalField('강의 수강료 중 배분 비중(%)', max_digits=5, decimal_places=2,
        default=100, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(100)],
        help_text='비율 방식: 강의 전체 담당은 100%, 차시별 담당은 합의한 배분 비중을 입력하세요.')
    royalty_percent = models.DecimalField('배분 금액 중 강사 지급률(%)', max_digits=5, decimal_places=2,
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    applies_to_renewals = models.BooleanField('재수강에도 적용', default=True)
    starts_on = models.DateField('적용 시작일', default=timezone.localdate)
    ends_on = models.DateField('적용 종료일', null=True, blank=True)
    note = models.TextField('운영자 메모', blank=True)

    class Meta:
        verbose_name = '담당 강사·정산 기준'
        verbose_name_plural = '담당 강사·정산 기준'
        ordering = ['course__title', 'lesson__order', 'instructor_id', '-starts_on']
        constraints = [models.CheckConstraint(check=Q(ends_on__isnull=True) | Q(ends_on__gte=models.F('starts_on')),
            name='teaching_valid_dates')]

    def __str__(self):
        return f'{self.instructor.display_name} / {self.course} / {self.lesson.title if self.lesson_id else "전체"}'

    @property
    def terms_label(self):
        scope = '신규·재수강' if self.applies_to_renewals else '신규 수강'
        if self.method == self.Method.FIXED:
            return f'{scope} 1건당 {self.fixed_amount:,}원'
        return f'{scope} 입금액 × 배분 {self.allocation_percent}% × 지급률 {self.royalty_percent}%'

    def clean(self):
        if self.lesson_id and self.course_id and self.lesson.course_id != self.course_id:
            raise ValidationError({'lesson': '선택한 강의에 속한 차시를 지정해 주세요.'})
        if self.ends_on and self.starts_on and self.ends_on < self.starts_on:
            raise ValidationError({'ends_on': '시작일 이후 날짜를 입력해 주세요.'})
        if not self.instructor_id or not self.course_id or not self.starts_on:
            return
        peers = type(self).objects.filter(course_id=self.course_id).exclude(pk=self.pk)
        peers = peers.filter(Q(ends_on__isnull=True) | Q(ends_on__gte=self.starts_on))
        if self.ends_on:
            peers = peers.filter(starts_on__lte=self.ends_on)
        # Whole-course and lesson-based contracts cannot accidentally pay twice.
        mixed = peers.filter(lesson__isnull=False) if self.lesson_id is None else peers.filter(lesson__isnull=True)
        if mixed.exists():
            raise ValidationError('같은 적용 기간에는 강의 전체 정산과 차시별 정산을 함께 등록할 수 없습니다.')
        if peers.filter(instructor_id=self.instructor_id, lesson_id=self.lesson_id).exists():
            raise ValidationError('동일 강사·담당 범위의 적용 기간이 겹칩니다. 기존 기준의 종료일을 먼저 지정해 주세요.')
        if self.pk and self.earnings.exists():
            old = type(self).objects.get(pk=self.pk)
            frozen = ('instructor_id', 'course_id', 'lesson_id', 'method', 'fixed_amount',
                      'allocation_percent', 'royalty_percent', 'applies_to_renewals', 'starts_on')
            if any(getattr(old, f) != getattr(self, f) for f in frozen):
                raise ValidationError('이미 계산된 정산 기준은 변경할 수 없습니다. 종료일을 지정하고 새 기준을 등록해 주세요.')
            if self.ends_on and self.earnings.filter(revenue__received_on__gt=self.ends_on).exists():
                raise ValidationError({'ends_on': '이미 계산된 입금일보다 앞당길 수 없습니다.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        from courses.models import Course
        if self.course_id:
            Course.objects.select_for_update().get(pk=self.course_id)
        self.full_clean()
        return super().save(*args, **kwargs)


class RevenueRecord(models.Model):
    enrollment = models.OneToOneField('enrollments.Enrollment', verbose_name='신규 수강 신청',
        on_delete=models.PROTECT, null=True, blank=True, related_name='revenue_record')
    renewal = models.OneToOneField('enrollments.ReEnrollmentRequest', verbose_name='재수강 신청',
        on_delete=models.PROTECT, null=True, blank=True, related_name='revenue_record')
    course = models.ForeignKey('courses.Course', verbose_name='강의', on_delete=models.PROTECT)
    amount = models.PositiveIntegerField('실제 입금액(원)', null=True, blank=True,
        help_text='할인 등을 반영한 실제 입금액입니다. 기존 강의 가격으로 추정하지 마세요. 면제는 0원입니다.')
    received_on = models.DateField('입금 확인일', null=True, blank=True)
    posted_at = models.DateTimeField('금액 확인·계산일시', null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='금액 확인자', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+', limit_choices_to={'is_staff': True})
    created_at = models.DateTimeField('등록일시', auto_now_add=True)
    note = models.TextField('입금 확인 근거·메모', blank=True)

    class Meta:
        verbose_name = '수강료 거래'
        verbose_name_plural = '수강료 거래'
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(
            check=(Q(enrollment__isnull=False, renewal__isnull=True) |
                       Q(enrollment__isnull=True, renewal__isnull=False)), name='revenue_one_source')]

    def __str__(self):
        return f'거래 {self.pk or "신규"} / {self.course} / {self.kind_label}'

    @property
    def kind_label(self):
        return '재수강' if self.renewal_id else '신규 수강'

    def clean(self):
        if bool(self.enrollment_id) == bool(self.renewal_id):
            raise ValidationError('신규 수강 신청과 재수강 신청 중 하나만 선택해 주세요.')
        source = self.renewal if self.renewal_id else self.enrollment
        if self.course_id != source.course_id:
            raise ValidationError({'course': '신청한 강의와 일치해야 합니다.'})
        if self.received_on and self.received_on > timezone.localdate():
            raise ValidationError({'received_on': '미래의 입금 확인일은 사용할 수 없습니다.'})
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.posted_at:
                raise ValidationError('계산된 거래는 변경할 수 없습니다. 환불은 별도 환불 기록으로 남겨 주세요.')

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            type(self).objects.select_for_update().get(pk=self.pk)
        self.full_clean()
        return super().save(*args, **kwargs)


class RefundRecord(models.Model):
    revenue = models.ForeignKey(RevenueRecord, verbose_name='원거래', on_delete=models.PROTECT, related_name='refunds')
    amount = models.PositiveIntegerField('환불액(원)', validators=[MinValueValidator(1)])
    refunded_on = models.DateField('환불 확인일', default=timezone.localdate)
    reason = models.CharField('환불 사유', max_length=255)
    posted_at = models.DateTimeField('반영일시', null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='환불 확인자', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+', limit_choices_to={'is_staff': True})

    class Meta:
        verbose_name = '수강료 환불'
        verbose_name_plural = '수강료 환불'
        ordering = ['-refunded_on', '-pk']

    def __str__(self):
        return f'환불 {self.pk or "신규"} / 거래 {self.revenue_id} / {self.amount:,}원'

    def clean(self):
        if self.refunded_on and self.refunded_on > timezone.localdate():
            raise ValidationError({'refunded_on': '미래의 환불 확인일은 사용할 수 없습니다.'})
        if self.revenue_id:
            if not self.revenue.posted_at:
                raise ValidationError('원거래의 실제 입금액을 먼저 확인·계산해 주세요.')
            if self.refunded_on and self.refunded_on < self.revenue.received_on:
                raise ValidationError({'refunded_on': '원거래 입금 확인일 이후여야 합니다.'})
        if self.pk and type(self).objects.filter(pk=self.pk, posted_at__isnull=False).exists():
            raise ValidationError('반영된 환불은 변경할 수 없습니다.')

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            type(self).objects.select_for_update().get(pk=self.pk)
        self.full_clean()
        return super().save(*args, **kwargs)


class InstructorEarning(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '정산 대기'
        CONFIRMED = 'confirmed', '정산 확정'
        PAID = 'paid', '지급 완료'

    assignment = models.ForeignKey(TeachingAssignment, verbose_name='적용 기준', on_delete=models.PROTECT, related_name='earnings')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='강사', on_delete=models.PROTECT)
    revenue = models.ForeignKey(RevenueRecord, verbose_name='수강료 거래', on_delete=models.PROTECT, related_name='earnings')
    refund = models.ForeignKey(RefundRecord, verbose_name='환불', on_delete=models.PROTECT, null=True, blank=True, related_name='earnings')
    occurred_on = models.DateField('발생일')
    course_title = models.CharField('강의명', max_length=200)
    lesson_title = models.CharField('담당 범위', max_length=200)
    terms = models.CharField('적용한 정산 기준', max_length=255)
    amount = models.IntegerField('강사료(원)')
    status = models.CharField('정산 상태', max_length=12, choices=Status.choices, default=Status.PENDING)
    confirmed_at = models.DateTimeField('정산 확정일시', null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name='정산 확정자', related_name='+')
    paid_at = models.DateTimeField('지급 완료 처리일시', null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name='지급 완료 처리자', related_name='+')

    class Meta:
        verbose_name = '강사료 정산 내역'
        verbose_name_plural = '강사료 정산 내역'
        ordering = ['-occurred_on', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'revenue'], condition=Q(refund__isnull=True), name='unique_revenue_earning'),
            models.UniqueConstraint(fields=['assignment', 'refund'], condition=Q(refund__isnull=False), name='unique_refund_earning'),
        ]

    def __str__(self):
        return f'{self.instructor.display_name} / {self.course_title} / {self.amount:,}원'
