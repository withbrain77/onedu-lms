from .models import WatchProgress


def get_course_progress_percent(enrollment):
    if enrollment is None:
        return 0

    lessons = enrollment.course.lessons.filter(is_public=True)
    total_count = lessons.count()
    if total_count == 0:
        return 0

    completed_count = WatchProgress.objects.filter(
        enrollment=enrollment,
        lesson__in=lessons,
        is_completed=True,
    ).count()
    return int((completed_count / total_count) * 100)
