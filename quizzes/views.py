from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from core.services.access import can_access_course

from .models import Quiz, QuizAttempt
from .services import build_quiz_status, grade_quiz_attempt


def _quiz_queryset():
    return (
        Quiz.objects
        .select_related('course')
        .prefetch_related('questions__choices')
        .filter(is_public=True, course__is_public=True)
    )


def _session_start_key(quiz):
    return f'quiz_started_at_{quiz.pk}'


@login_required
@require_http_methods(['GET', 'POST'])
def take_quiz(request, pk):
    quiz = get_object_or_404(_quiz_queryset(), pk=pk)
    access_result = can_access_course(request.user, quiz.course)
    if not access_result.allowed or access_result.enrollment is None:
        return render(
            request,
            'quizzes/access_denied.html',
            {'quiz': quiz, 'course': quiz.course, 'access': access_result},
            status=403,
        )

    status = build_quiz_status(request.user, quiz)
    if not status['can_attempt']:
        messages.warning(request, '재응시 가능 횟수를 모두 사용했습니다.')
        return redirect('quizzes:result', pk=status['best_attempt'].pk)

    questions = list(quiz.questions.prefetch_related('choices').order_by('order', 'id'))
    if request.method == 'POST':
        started_at = parse_datetime(request.session.pop(_session_start_key(quiz), '')) or timezone.now()
        attempt = grade_quiz_attempt(
            user=request.user,
            enrollment=access_result.enrollment,
            quiz=quiz,
            payload=request.POST,
            started_at=started_at,
        )
        messages.success(request, '시험이 제출되었습니다.')
        return redirect('quizzes:result', pk=attempt.pk)

    request.session[_session_start_key(quiz)] = timezone.now().isoformat()
    question_items = [
        {
            'question': question,
            'choices': list(question.choices.all()),
        }
        for question in questions
    ]
    return render(
        request,
        'quizzes/take.html',
        {
            'quiz': quiz,
            'course': quiz.course,
            'question_items': question_items,
            'status': status,
            'access': access_result,
        },
    )


@login_required
def quiz_result(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects
        .select_related('user', 'quiz', 'quiz__course')
        .prefetch_related('answers__question', 'answers__selected_choice'),
        pk=pk,
    )
    if attempt.user_id != request.user.pk and not request.user.is_staff:
        raise Http404('Quiz attempt not found')

    status = build_quiz_status(attempt.user, attempt.quiz)
    return render(
        request,
        'quizzes/result.html',
        {
            'attempt': attempt,
            'quiz': attempt.quiz,
            'course': attempt.quiz.course,
            'answers': attempt.answers.all(),
            'status': status,
        },
    )
