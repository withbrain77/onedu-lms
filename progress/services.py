from .models import WatchProgress


def get_course_progress_percent(enrollment):
    if enrollment is None:
        return 0

    lessons = enrollment.course.lessons.filter(is_public=True)
    total_count = lessons.count()
    if total_count == 0:
        return 0

    progresses = WatchProgress.objects.filter(
        enrollment=enrollment,
        lesson__in=lessons,
    ).values_list('lesson_id', 'progress_percent')
    progress_map = {lesson_id: progress_percent for lesson_id, progress_percent in progresses}
    total_percent = sum(progress_map.get(lesson.pk, 0) for lesson in lessons)
    return int(total_percent / total_count)
