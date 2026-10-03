import csv
from functools import wraps

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from enrollments.models import Enrollment
from progress.models import WatchProgress
from .models import InstructorEarning, RefundRecord, RevenueRecord, TeachingAssignment


def instructor_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_instructor:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


class PeriodForm(forms.Form):
    start = forms.DateField(label='시작일', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end = forms.DateField(label='종료일', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            self.add_error('end', '종료일은 시작일 이후로 선택해 주세요.')
        return data


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


@never_cache
@require_GET
@instructor_required
def dashboard(request):
    today = timezone.localdate()
    form = PeriodForm(request.GET if 'start' in request.GET or 'end' in request.GET else {
        'start': today.replace(day=1).isoformat(), 'end': today.isoformat()})
    assignments = TeachingAssignment.objects.filter(instructor=request.user).select_related('course', 'lesson')
    earnings = InstructorEarning.objects.filter(instructor=request.user).select_related('revenue', 'refund')
    if not form.is_valid():
        return render(request, 'instructors/dashboard.html', {'form': form, 'assignments': assignments}, status=400)
    start, end = form.cleaned_data['start'], form.cleaned_data['end']
    earnings = earnings.filter(occurred_on__range=(start, end))
    if request.GET.get('download') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="instructor-{start}-{end}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['발생일', '거래 번호', '강의', '담당 범위', '구분', '적용 기준', '강사료(원)', '상태', '확정일', '지급 완료 처리일'])
        for row in earnings.iterator():
            writer.writerow([row.occurred_on, row.revenue_id, safe_cell(row.course_title), safe_cell(row.lesson_title),
                '환불 차감' if row.refund_id else row.revenue.kind_label, safe_cell(row.terms), row.amount,
                row.get_status_display(), timezone.localdate(row.confirmed_at) if row.confirmed_at else '',
                timezone.localdate(row.paid_at) if row.paid_at else ''])
        return response
    original = earnings.filter(refund__isnull=True)
    revenues = RevenueRecord.objects.filter(pk__in=original.values('revenue_id'))
    refunds = RefundRecord.objects.filter(pk__in=earnings.filter(refund__isnull=False).values('refund_id'))
    # Unknown dates cannot honestly be assigned to a selected period.
    scope = Q(pk__in=[])
    for assignment in assignments:
        dates = Q(received_on__gte=assignment.starts_on)
        if assignment.ends_on:
            dates &= Q(received_on__lte=assignment.ends_on)
        scope |= Q(course_id=assignment.course_id) & (dates | Q(received_on__isnull=True))
    pending = RevenueRecord.objects.filter(scope, posted_at__isnull=True)
    pending_count = pending.filter(received_on__range=(start, end)).count()
    undated_count = pending.filter(received_on__isnull=True).count()
    cards = []
    grouped = {}
    for assignment in assignments:
        grouped.setdefault(assignment.course_id, {'course': assignment.course, 'assignments': []})['assignments'].append(assignment)
    for card in grouped.values():
        enrollments = Enrollment.objects.filter(course=card['course'], status=Enrollment.Status.APPROVED)
        progress = WatchProgress.objects.filter(enrollment__in=enrollments, total_watched_seconds__gt=0)
        if all(a.lesson_id for a in card['assignments']):
            progress = progress.filter(lesson_id__in=[a.lesson_id for a in card['assignments']])
        card['students'] = enrollments.values('user_id').distinct().count()
        card['viewers'] = progress.values('user_id').distinct().count()
        card['completed'] = enrollments.filter(is_completed=True).values('user_id').distinct().count()
        cards.append(card)
    totals = {status: earnings.filter(status=status).aggregate(total=Sum('amount'))['total'] or 0
              for status in InstructorEarning.Status.values}
    return render(request, 'instructors/dashboard.html', {
        'form': form, 'assignments': assignments, 'cards': cards,
        'rows': Paginator(earnings, 30).get_page(request.GET.get('page')),
        'start': start.isoformat(), 'end': end.isoformat(), 'totals': totals,
        'new_count': revenues.filter(enrollment__isnull=False, amount__gt=0).count(),
        'renewal_count': revenues.filter(renewal__isnull=False, amount__gt=0).count(),
        'gross': revenues.aggregate(total=Sum('amount'))['total'] or 0,
        'refund_total': refunds.aggregate(total=Sum('amount'))['total'] or 0,
        'pending_count': pending_count, 'undated_count': undated_count,
    })
