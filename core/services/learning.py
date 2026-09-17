from core.services.access import can_access_course
from django.db.models.functions import Coalesce
from progress.models import WatchProgress


def lesson_reached_end(progress):
    if not progress or not progress.is_completed:
        return False
    duration = progress.duration_seconds or progress.lesson.duration_seconds
    return bool(duration and progress.last_position_seconds >= duration - 1)


def next_public_lesson(lesson):
    return lesson.course.lessons.filter(is_public=True, order__gt=lesson.order).order_by('order', 'pk').first()


def continue_lesson(enrollment):
    """Use the latest watched public lesson, then the first published lesson."""
    progress = enrollment.watch_progresses.filter(lesson__is_public=True).select_related('lesson').order_by(
        Coalesce('last_position_recorded_at', 'last_watched_at').desc(), '-pk',
    ).first()
    if progress:
        if lesson_reached_end(progress):
            return next_public_lesson(progress.lesson) or progress.lesson
        return progress.lesson
    return enrollment.course.lessons.filter(is_public=True).order_by('order', 'id').first()


def recent_learning(user):
    if not user.is_authenticated or user.is_staff:
        return None
    progresses = WatchProgress.objects.filter(
        user=user, lesson__is_public=True, lesson__course__is_public=True,
    ).select_related('lesson__course', 'enrollment').order_by(
        Coalesce('last_position_recorded_at', 'last_watched_at').desc(), '-pk',
    )
    access_by_course = {}
    for progress in progresses.iterator():
        course = progress.lesson.course
        if course.pk not in access_by_course:
            access_by_course[course.pk] = can_access_course(user, course)
        access = access_by_course[course.pk]
        if access.allowed and access.enrollment.pk == progress.enrollment_id:
            progress.reached_end = lesson_reached_end(progress)
            progress.next_lesson = next_public_lesson(progress.lesson) if progress.reached_end else None
            return progress
    return None
