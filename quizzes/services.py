from django.utils import timezone

from .models import AnswerChoice, Question, QuizAttempt, QuizAttemptAnswer


def get_attempt_count(user, quiz):
    if not getattr(user, 'is_authenticated', False):
        return 0
    return QuizAttempt.objects.filter(user=user, quiz=quiz, submitted_at__isnull=False).count()


def get_remaining_attempts(user, quiz):
    return max(quiz.max_attempts - get_attempt_count(user, quiz), 0)


def get_best_attempt(user, quiz):
    if not getattr(user, 'is_authenticated', False):
        return None
    return (
        QuizAttempt.objects
        .filter(user=user, quiz=quiz, submitted_at__isnull=False)
        .order_by('-score', '-submitted_at')
        .first()
    )


def build_quiz_status(user, quiz):
    attempt_count = get_attempt_count(user, quiz)
    remaining_attempts = max(quiz.max_attempts - attempt_count, 0)
    best_attempt = get_best_attempt(user, quiz)
    return {
        'quiz': quiz,
        'attempt_count': attempt_count,
        'remaining_attempts': remaining_attempts,
        'best_attempt': best_attempt,
        'can_attempt': remaining_attempts > 0,
    }


def get_course_quiz_items(user, course):
    quizzes = course.quizzes.filter(is_public=True).prefetch_related('questions')
    return [build_quiz_status(user, quiz) for quiz in quizzes]


def grade_quiz_attempt(*, user, enrollment, quiz, payload, started_at=None):
    questions = list(
        quiz.questions
        .prefetch_related('choices')
        .order_by('order', 'id')
    )
    auto_gradable_points = sum(
        question.points
        for question in questions
        if question.type == Question.Type.MULTIPLE_CHOICE
    ) or 1
    earned_points = 0
    attempt_number = get_attempt_count(user, quiz) + 1
    attempt = QuizAttempt.objects.create(
        user=user,
        quiz=quiz,
        enrollment=enrollment,
        attempt_number=attempt_number,
        started_at=started_at or timezone.now(),
        submitted_at=timezone.now(),
    )

    for question in questions:
        answer = QuizAttemptAnswer(attempt=attempt, question=question)
        if question.type == Question.Type.MULTIPLE_CHOICE:
            choice_id = payload.get(f'question_{question.pk}')
            selected_choice = None
            if choice_id:
                selected_choice = AnswerChoice.objects.filter(
                    pk=choice_id,
                    question=question,
                ).first()
            answer.selected_choice = selected_choice
            answer.is_correct = bool(selected_choice and selected_choice.is_correct)
            answer.earned_points = question.points if answer.is_correct else 0
        else:
            answer.text_answer = payload.get(f'question_{question.pk}', '').strip()
            answer.is_correct = False
            answer.earned_points = 0
        answer.save()
        earned_points += answer.earned_points

    attempt.score = int(round((earned_points / auto_gradable_points) * 100))
    attempt.max_score = 100
    attempt.passed = attempt.score >= quiz.pass_score
    attempt.save(update_fields=['score', 'max_score', 'passed'])
    return attempt
