from django.utils import timezone

from certificates.services import get_or_create_certificate
from progress.services import get_course_progress_percent
from quizzes.models import Quiz
from quizzes.services import get_best_attempt


def get_required_quizzes(course):
    if not course.require_quiz_pass:
        return Quiz.objects.none()
    return course.quizzes.filter(is_public=True)


def get_completion_status(enrollment):
    course = enrollment.course
    progress_percent = get_course_progress_percent(enrollment)
    required_progress = course.required_progress_percent
    progress_met = progress_percent >= required_progress

    quiz_items = []
    required_quizzes = list(get_required_quizzes(course))
    if required_quizzes:
        quiz_met = True
        for quiz in required_quizzes:
            best_attempt = get_best_attempt(enrollment.user, quiz)
            passed = bool(best_attempt and best_attempt.passed)
            quiz_items.append({
                'quiz': quiz,
                'best_attempt': best_attempt,
                'passed': passed,
                'attempted': best_attempt is not None,
            })
            quiz_met = quiz_met and passed
    else:
        quiz_met = True

    missing = []
    if not progress_met:
        missing.append(f'영상 진도 {progress_percent}% / 필요 {required_progress}%')
    for item in quiz_items:
        if not item['attempted']:
            missing.append(f'{item["quiz"].title}: 시험 미응시')
        elif not item['passed']:
            missing.append(f'{item["quiz"].title}: 시험 미합격')

    can_complete = progress_met and quiz_met
    return {
        'enrollment': enrollment,
        'course': course,
        'progress_percent': progress_percent,
        'required_progress_percent': required_progress,
        'progress_met': progress_met,
        'requires_quiz': bool(required_quizzes),
        'quiz_met': quiz_met,
        'quiz_items': quiz_items,
        'can_complete': can_complete,
        'missing': missing,
        'certificate_enabled': course.certificate_enabled,
    }


def evaluate_enrollment_completion(enrollment, save=True):
    status = get_completion_status(enrollment)
    if status['can_complete']:
        changed = False
        if not enrollment.is_completed:
            enrollment.is_completed = True
            enrollment.completed_at = timezone.now()
            changed = True
        enrollment.completion_progress_percent = status['progress_percent']
        if not enrollment.completion_note:
            enrollment.completion_note = '자동 수료 판정'
        if save:
            fields = ['is_completed', 'completed_at', 'completion_progress_percent', 'completion_note', 'updated_at']
            enrollment.save(update_fields=fields)
        if enrollment.course.certificate_enabled:
            get_or_create_certificate(enrollment)
        status['completed_now'] = changed
    else:
        enrollment.completion_progress_percent = status['progress_percent']
        if save:
            enrollment.save(update_fields=['completion_progress_percent', 'updated_at'])
        status['completed_now'] = False
    return status
