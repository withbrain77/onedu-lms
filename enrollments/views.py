from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services.access import can_access_course
from core.services.completion import evaluate_enrollment_completion
from courses.models import Course
from progress.models import WatchProgress
from progress.services import get_course_progress_percent
from quizzes.services import get_course_quiz_items

from .forms import ReEnrollmentRequestForm
from .models import Enrollment, ReEnrollmentRequest


def _latest_reenrollment_request(enrollment):
    return enrollment.reenrollment_requests.order_by('-requested_at').first()


def _enrollment_card(enrollment, request):
    access_result = can_access_course(request.user, enrollment.course)
    reenrollment_request = _latest_reenrollment_request(enrollment)
    if access_result.code == 'allowed':
        status_label = '수강 중'
        status_class = 'text-bg-primary'
    elif access_result.code == 'not_started':
        status_label = '수강 전'
        status_class = 'text-bg-info'
    elif access_result.code == 'ended':
        status_label = '기간 만료'
        status_class = 'text-bg-secondary'
    elif access_result.code == 'period_missing':
        status_label = '승인됨'
        status_class = 'text-bg-success'
    elif enrollment.status == Enrollment.Status.REQUESTED:
        status_label = '신청 대기'
        status_class = 'text-bg-warning'
    elif enrollment.status == Enrollment.Status.REJECTED:
        status_label = '반려됨'
        status_class = 'text-bg-danger'
    else:
        status_label = enrollment.get_status_display()
        status_class = 'text-bg-secondary'

    if enrollment.start_date and enrollment.end_date:
        period_text = f'{enrollment.start_date} ~ {enrollment.end_date}'
    else:
        period_text = '기간 미설정'

    if access_result.code == 'not_started':
        remaining_text = f'{enrollment.start_date} 시작 예정'
    elif access_result.code == 'ended':
        remaining_text = '기간 만료'
    elif enrollment.days_remaining is not None:
        remaining_text = '오늘 종료' if enrollment.days_remaining == 0 else f'{enrollment.days_remaining}일 남음'
    else:
        remaining_text = '-'

    return {
        'enrollment': enrollment,
        'course': enrollment.course,
        'access': access_result,
        'status_label': status_label,
        'status_class': status_class,
        'period_text': period_text,
        'remaining_text': remaining_text,
        'progress_percent': get_course_progress_percent(enrollment),
        'reenrollment_request': reenrollment_request,
        'has_pending_reenrollment': bool(
            reenrollment_request and reenrollment_request.status == ReEnrollmentRequest.Status.PENDING
        ),
    }


@login_required
def classroom(request):
    enrollments = (
        Enrollment.objects
        .filter(user=request.user)
        .select_related('course')
        .order_by('-created_at')
    )
    active_cards = []
    waiting_cards = []
    ended_cards = []
    other_cards = []

    for enrollment in enrollments:
        if enrollment.status == Enrollment.Status.APPROVED:
            evaluate_enrollment_completion(enrollment)
        card = _enrollment_card(enrollment, request)
        if enrollment.status == Enrollment.Status.REQUESTED:
            waiting_cards.append(card)
        elif enrollment.status == Enrollment.Status.APPROVED and enrollment.has_ended:
            ended_cards.append(card)
        elif enrollment.status == Enrollment.Status.APPROVED:
            active_cards.append(card)
        else:
            other_cards.append(card)

    return render(
        request,
        'classroom/index.html',
        {
            'active_cards': active_cards,
            'waiting_cards': waiting_cards,
            'ended_cards': ended_cards,
            'other_cards': other_cards,
        },
    )


@login_required
@require_POST
def cancel_enrollment_request(request, enrollment_id):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('course', 'user'),
        pk=enrollment_id,
        user=request.user,
    )
    if enrollment.status != Enrollment.Status.REQUESTED:
        messages.warning(request, '승인 대기 중인 수강 신청만 취소할 수 있습니다.')
        return redirect('enrollments:classroom')

    enrollment.status = Enrollment.Status.CANCELLED
    enrollment.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{enrollment.course.title} 수강 신청을 취소했습니다.')
    return redirect('enrollments:classroom')


@login_required
def classroom_course_detail(request, course_id):
    course = get_object_or_404(Course.objects.prefetch_related('lessons'), pk=course_id, is_public=True)
    access_result = can_access_course(request.user, course)
    if not access_result.allowed:
        reenrollment_request = access_result.enrollment and _latest_reenrollment_request(access_result.enrollment)
        return render(
            request,
            'classroom/access_denied.html',
            {
                'course': course,
                'access': access_result,
                'enrollment': access_result.enrollment,
                'reenrollment_request': reenrollment_request,
            },
            status=403,
        )

    enrollment = access_result.enrollment
    lessons = list(course.lessons.filter(is_public=True).order_by('order'))
    progress_by_lesson = {}
    if enrollment:
        completion_status = evaluate_enrollment_completion(enrollment)
        progress_by_lesson = {
            progress.lesson_id: progress
            for progress in WatchProgress.objects.filter(enrollment=enrollment, lesson__in=lessons)
        }
        progress_percent = completion_status['progress_percent'] if completion_status else 0
        quiz_items = get_course_quiz_items(request.user, course)
    else:
        completion_status = None
        progress_percent = 0
        quiz_items = []

    lesson_items = [
        {
            'lesson': lesson,
            'progress': progress_by_lesson.get(lesson.pk),
        }
        for lesson in lessons
    ]

    return render(
        request,
        'classroom/course_detail.html',
        {
            'course': course,
            'enrollment': enrollment,
            'access': access_result,
            'lesson_items': lesson_items,
            'progress_percent': progress_percent,
            'quiz_items': quiz_items,
            'completion_status': completion_status,
        },
    )


@login_required
def request_reenrollment(request, enrollment_id):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('course', 'user'),
        pk=enrollment_id,
        user=request.user,
        status=Enrollment.Status.APPROVED,
    )
    if not enrollment.has_ended:
        messages.warning(request, '수강 기간이 종료된 강의만 재수강을 신청할 수 있습니다.')
        return redirect('enrollments:classroom')

    pending_request = enrollment.reenrollment_requests.filter(status=ReEnrollmentRequest.Status.PENDING).first()
    if pending_request:
        messages.info(request, '이미 재수강 신청이 접수되어 관리자 승인을 기다리고 있습니다.')
        return redirect('enrollments:classroom')

    if request.method == 'POST':
        form = ReEnrollmentRequestForm(request.POST)
        if form.is_valid():
            reenrollment_request = form.save(commit=False)
            reenrollment_request.user = request.user
            reenrollment_request.course = enrollment.course
            reenrollment_request.enrollment = enrollment
            reenrollment_request.save()
            messages.success(request, '재수강 신청이 접수되었습니다. 관리자가 승인하면 수강 기간이 연장됩니다.')
            return redirect('enrollments:classroom')
    else:
        form = ReEnrollmentRequestForm()

    return render(
        request,
        'classroom/reenrollment_form.html',
        {
            'form': form,
            'enrollment': enrollment,
            'course': enrollment.course,
            'latest_request': _latest_reenrollment_request(enrollment),
        },
    )
