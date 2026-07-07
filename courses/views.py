from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services.access import can_access_course, get_latest_enrollment
from core.services.completion import evaluate_enrollment_completion
from enrollments.models import Enrollment
from progress.models import WatchProgress
from progress.services import get_course_progress_percent
from quizzes.services import get_course_quiz_items

from .models import Course


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
    courses = list(Course.objects.filter(is_public=True).prefetch_related('lessons'))
    latest = _latest_enrollments(request.user, courses)
    course_cards = [
        _course_card(course, latest.get(course.pk), request)
        for course in courses
    ]
    return render(request, 'courses/course_list.html', {'course_cards': course_cards})


@login_required
def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.prefetch_related('lessons'),
        slug=slug,
        is_public=True,
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
        },
    )


@login_required
@require_POST
def apply_course(request, slug):
    course = get_object_or_404(Course, slug=slug, is_public=True)
    if request.user.is_staff:
        messages.warning(request, '관리자 계정은 수강 신청 대상이 아닙니다.')
        return redirect(course)

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

    Enrollment.objects.create(user=request.user, course=course)
    messages.success(request, '수강 신청이 접수되었습니다. 관리자가 승인하면 학습을 시작할 수 있습니다.')
    return redirect('enrollments:classroom')
