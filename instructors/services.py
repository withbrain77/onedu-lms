from decimal import Decimal, ROUND_DOWN

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from courses.models import Course
from .models import InstructorEarning, RefundRecord, RevenueRecord, TeachingAssignment


def require_operator(user):
    if not user.is_active or not user.is_staff:
        raise PermissionDenied


def whole_won(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_DOWN))


@transaction.atomic
def post_revenue(record_id, operator):
    require_operator(operator)
    record = RevenueRecord.objects.select_for_update().get(pk=record_id)
    if record.posted_at:
        return False
    record.full_clean()
    if record.amount is None or record.received_on is None:
        raise ValidationError('실제 입금액과 입금 확인일을 입력해 주세요.')
    source = record.renewal if record.renewal_id else record.enrollment
    if record.renewal_id:
        if source.status != source.Status.APPROVED:
            raise ValidationError('승인된 재수강 신청만 계산할 수 있습니다.')
    elif source.payment_status not in (source.PaymentStatus.CONFIRMED, source.PaymentStatus.WAIVED):
        raise ValidationError('입금 확인 또는 면제 처리된 수강 신청만 계산할 수 있습니다.')
    if not record.renewal_id and source.payment_status == source.PaymentStatus.WAIVED and record.amount:
        raise ValidationError('입금 면제된 수강은 금액을 0원으로 입력해 주세요.')
    # Serialize all postings/contract changes for a course on PostgreSQL.
    Course.objects.select_for_update().get(pk=record.course_id)
    assignments = TeachingAssignment.objects.filter(course_id=record.course_id, starts_on__lte=record.received_on).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gte=record.received_on))
    if record.renewal_id:
        assignments = assignments.filter(applies_to_renewals=True)
    assignments = list(assignments.select_related('instructor', 'course', 'lesson'))
    if record.amount and not assignments:
        raise ValidationError('입금 확인일에 적용할 담당 강사·정산 기준이 없습니다. 기준을 먼저 등록해 주세요.')
    earnings = []
    for assignment in assignments:
        if not record.amount:
            amount = 0
        elif assignment.method == TeachingAssignment.Method.FIXED:
            amount = assignment.fixed_amount
        else:
            amount = whole_won(Decimal(record.amount) * assignment.allocation_percent * assignment.royalty_percent / 10000)
        earnings.append(InstructorEarning(
            assignment=assignment, instructor=assignment.instructor, revenue=record,
            occurred_on=record.received_on, course_title=assignment.course.title,
            lesson_title=assignment.lesson.title if assignment.lesson_id else '강의 전체',
            terms=assignment.terms_label, amount=amount,
        ))
    if sum(e.amount for e in earnings) > record.amount:
        raise ValidationError('전체 강사 지급액이 실제 입금액을 초과합니다. 할인 금액과 정산 기준을 확인해 주세요.')
    InstructorEarning.objects.bulk_create(earnings)
    RevenueRecord.objects.filter(pk=record.pk).update(posted_at=timezone.now(), posted_by=operator)
    return True


@transaction.atomic
def post_refund(refund_id, operator):
    require_operator(operator)
    refund = RefundRecord.objects.select_for_update().get(pk=refund_id)
    if refund.posted_at:
        return False
    revenue = RevenueRecord.objects.select_for_update().get(pk=refund.revenue_id)
    refund.full_clean()
    previous = revenue.refunds.filter(posted_at__isnull=False).aggregate(total=Sum('amount'))['total'] or 0
    if previous + refund.amount > revenue.amount:
        raise ValidationError('누적 환불액이 실제 입금액을 초과합니다.')
    for original in revenue.earnings.filter(refund__isnull=True):
        # Cumulative rounding makes a full refund cancel the exact original royalty.
        already = -(revenue.earnings.filter(assignment=original.assignment, refund__posted_at__isnull=False,
            refund__isnull=False).aggregate(total=Sum('amount'))['total'] or 0)
        target = whole_won(Decimal(original.amount) * (previous + refund.amount) / revenue.amount)
        InstructorEarning.objects.create(
            assignment=original.assignment, instructor=original.instructor, revenue=revenue,
            refund=refund, occurred_on=refund.refunded_on, course_title=original.course_title,
            lesson_title=original.lesson_title, terms='원거래 강사료를 누적 환불 비율에 따라 차감', amount=-(target - already),
        )
    RefundRecord.objects.filter(pk=refund.pk).update(posted_at=timezone.now(), posted_by=operator)
    return True


@transaction.atomic
def advance_earnings(queryset, operator, *, paid=False):
    require_operator(operator)
    now = timezone.now()
    ids = list(queryset.select_for_update().values_list('pk', flat=True))
    target = InstructorEarning.objects.filter(pk__in=ids)
    if paid:
        return target.filter(status=InstructorEarning.Status.CONFIRMED).update(
            status=InstructorEarning.Status.PAID, paid_at=now, paid_by=operator)
    return target.filter(status=InstructorEarning.Status.PENDING).update(
        status=InstructorEarning.Status.CONFIRMED, confirmed_at=now, confirmed_by=operator)
