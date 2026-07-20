from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.services.access import can_access_course, get_latest_enrollment
from core.services.completion import evaluate_enrollment_completion
from core.models import Notice
from enrollments.models import Enrollment
from enrollments.notifications import notify_enrollment_request
from progress.models import WatchProgress
from progress.services import get_course_progress_percent
from quizzes.services import get_course_quiz_items

from .models import Course, CourseInvitation


def _absolute_site_url(request, path):
    if settings.PUBLIC_SITE_URL:
        return f'{settings.PUBLIC_SITE_URL}{path}'
    return request.build_absolute_uri(path)


def _visible_course_queryset(user):
    queryset = Course.objects.all()
    public_filter = Q(is_public=True, visibility=Course.Visibility.PUBLIC)

    if getattr(user, 'is_authenticated', False) and user.is_staff:
        return queryset

    if not getattr(user, 'is_authenticated', False):
        return queryset.filter(public_filter)

    return queryset.filter(
        public_filter
        | Q(is_public=True, visibility=Course.Visibility.INVITE_ONLY, invitations__user=user, invitations__active=True)
        | Q(enrollments__user=user)
    ).distinct()


def _is_invited_user(user, course):
    if not getattr(user, 'is_authenticated', False):
        return False
    return CourseInvitation.objects.filter(course=course, user=user, active=True).exists()


def _can_apply_course(user, course):
    if course.is_private:
        return False, '현재 신청할 수 없는 강의입니다.'
    if course.is_invite_only and not _is_invited_user(user, course):
        return False, '초대된 회원만 신청할 수 있는 강의입니다.'
    return True, ''


def _status_for(enrollment, access_result=None):
    if enrollment is None:
        return '신청 가능', 'text-bg-light border'
    if access_result and access_result.code == 'allowed':
        return '수강 중', 'text-bg-primary'
    if access_result and access_result.code == 'not_started':
        return '수강 전', 'text-bg-info'
    if access_result and access_result.code == 'ended':
        return '기간 만료', 'text-bg-secondary'
    if access_result and access_result.code == 'period_missing':
        return '승인됨', 'text-bg-success'
    if enrollment.status == Enrollment.Status.REQUESTED:
        return '신청 대기', 'text-bg-warning'
    if enrollment.status == Enrollment.Status.REJECTED:
        return '반려됨', 'text-bg-danger'
    if enrollment.status == Enrollment.Status.CANCELLED:
        return '취소됨', 'text-bg-secondary'
    return enrollment.get_status_display(), 'text-bg-success'


def _period_text(enrollment):
    if not enrollment:
        return '관리자 승인 후 배정'
    if enrollment.start_date and enrollment.end_date:
        return f'{enrollment.start_date} ~ {enrollment.end_date}'
    return '기간 미설정'


def _remaining_text(enrollment, access_result=None):
    if not enrollment:
        return '-'
    if access_result and access_result.code == 'not_started':
        return f'{enrollment.start_date} 시작 예정'
    if access_result and access_result.code == 'ended':
        return '기간 만료'
    if enrollment.days_remaining is None:
        return '-'
    if enrollment.days_remaining == 0:
        return '오늘 종료'
    return f'{enrollment.days_remaining}일 남음'


def _course_card(course, enrollment, request):
    access_result = None
    if request.user.is_authenticated:
        access_result = can_access_course(request.user, course)
    status_label, status_class = _status_for(enrollment, access_result)
    if enrollment is None and course.is_invite_only and request.user.is_authenticated:
        status_label, status_class = '초대됨', 'text-bg-info'
    progress_percent = get_course_progress_percent(enrollment) if enrollment else 0
    return {
        'course': course,
        'enrollment': enrollment,
        'access': access_result,
        'status_label': status_label,
        'status_class': status_class,
        'period_text': _period_text(enrollment),
        'remaining_text': _remaining_text(enrollment, access_result),
        'progress_percent': progress_percent,
    }


def _latest_enrollments(user, courses):
    if not user.is_authenticated:
        return {}
    course_ids = [course.pk for course in courses]
    enrollments = (
        Enrollment.objects
        .filter(user=user, course_id__in=course_ids)
        .select_related('course')
        .order_by('course_id', '-created_at')
    )
    latest = {}
    for enrollment in enrollments:
        latest.setdefault(enrollment.course_id, enrollment)
    return latest


def course_list(request):
    courses = list(_visible_course_queryset(request.user).prefetch_related('lessons'))
    latest = _latest_enrollments(request.user, courses)
    course_cards = [
        _course_card(course, latest.get(course.pk), request)
        for course in courses
    ]
    return render(request, 'courses/course_list.html', {'course_cards': course_cards})


def course_detail(request, slug):
    course = get_object_or_404(
        _visible_course_queryset(request.user).prefetch_related('lessons'),
        slug=slug,
    )
    enrollment = get_latest_enrollment(request.user, course) if request.user.is_authenticated else None
    access_result = can_access_course(request.user, course) if request.user.is_authenticated else None
    progress_percent = get_course_progress_percent(enrollment) if enrollment else 0
    lessons = list(course.lessons.filter(is_public=True).order_by('order'))
    progress_by_lesson = {}

    if access_result and access_result.allowed and enrollment:
        completion_status = evaluate_enrollment_completion(enrollment)
        progress_percent = completion_status['progress_percent']
        progress_by_lesson = {
            progress.lesson_id: progress
            for progress in WatchProgress.objects.filter(enrollment=enrollment, lesson__in=lessons)
        }
    else:
        completion_status = None

    lesson_items = [
        {
            'lesson': lesson,
            'progress': progress_by_lesson.get(lesson.pk),
        }
        for lesson in lessons
    ]

    status_label, status_class = _status_for(enrollment, access_result)
    short_course_path = reverse('course_short_link', kwargs={'course_id': course.pk})
    notices = (
        Notice.objects
        .filter(is_published=True, published_at__lte=timezone.now())
        .filter(Q(course__isnull=True) | Q(course=course))
        .select_related('course')
        .order_by('-is_pinned', '-published_at', '-created_at')[:5]
    )
    return render(
        request,
        'courses/course_detail.html',
        {
            'course': course,
            'enrollment': enrollment,
            'access': access_result,
            'lesson_items': lesson_items,
            'progress_percent': progress_percent,
            'status_label': status_label,
            'status_class': status_class,
            'period_text': _period_text(enrollment),
            'remaining_text': _remaining_text(enrollment, access_result),
            'quiz_items': get_course_quiz_items(request.user, course) if access_result and access_result.allowed else [],
            'completion_status': completion_status,
            'short_course_path': short_course_path,
            'short_course_url': _absolute_site_url(request, short_course_path),
            'notices': notices,
        },
    )


def short_course_redirect(request, course_id):
    course = get_object_or_404(_visible_course_queryset(request.user), pk=course_id)
    return redirect(course)


@login_required
@require_POST
def apply_course(request, slug):
    course = get_object_or_404(_visible_course_queryset(request.user), slug=slug)
    if request.user.is_staff:
        messages.warning(request, '관리자 계정은 수강 신청 대상이 아닙니다.')
        return redirect(course)

    can_apply, deny_message = _can_apply_course(request.user, course)
    if not can_apply:
        messages.warning(request, deny_message)
        return redirect('courses:list')

    latest = get_latest_enrollment(request.user, course)
    if latest and latest.status == Enrollment.Status.REQUESTED:
        messages.info(request, '이미 수강 신청이 접수되어 승인 대기 중입니다.')
        return redirect(course)

    if latest and latest.status == Enrollment.Status.APPROVED and not latest.has_ended:
        messages.info(request, '이미 승인된 강의입니다. 내 강의실에서 학습을 이어가세요.')
        return redirect('enrollments:course_detail', course_id=course.pk)

    if latest and latest.status == Enrollment.Status.APPROVED and latest.has_ended:
        messages.warning(request, '수강 기간이 종료되었습니다. 재수강 신청은 다음 단계에서 제공됩니다.')
        return redirect(course)

    if course.is_free:
        today = timezone.localdate()
        enrollment = Enrollment.objects.create(
            user=request.user,
            course=course,
            status=Enrollment.Status.APPROVED,
            payment_status=Enrollment.PaymentStatus.NOT_REQUIRED,
            start_date=today,
            end_date=today + timedelta(days=course.default_enrollment_days),
        )
        messages.success(request, '무료 강의 신청이 완료되었습니다. 바로 학습을 시작할 수 있습니다.')
        return redirect('enrollments:course_detail', course_id=enrollment.course_id)

    enrollment = Enrollment.objects.create(
        user=request.user,
        course=course,
        payment_status=Enrollment.PaymentStatus.PENDING,
    )
    notify_enrollment_request(enrollment)
    deposit = settings.ONEDU_DEPOSIT_NOTICE
    messages.success(
        request,
        (
            '수강 신청이 접수되었습니다. '
            f"{deposit['bank']} {deposit['account']} / 예금주 {deposit['holder']}로 입금해 주세요. "
            f"입금자명은 {deposit['payer_note']} "
            '입금 확인 후 관리자가 승인하면 학습을 시작할 수 있습니다.'
        ),
    )
    return redirect('enrollments:classroom')
