from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.services.access import can_access_lesson
from progress.models import WatchProgress

from .models import Lesson


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(
        Lesson.objects.select_related('course'),
        pk=pk,
        is_public=True,
        course__is_public=True,
    )
    access_result = can_access_lesson(request.user, lesson)
    if not access_result.allowed:
        return render(
            request,
            'lessons/access_denied.html',
            {'lesson': lesson, 'course': lesson.course, 'access': access_result},
            status=403,
        )

    progress = None
    if access_result.enrollment:
        progress = WatchProgress.objects.filter(
            enrollment=access_result.enrollment,
            lesson=lesson,
        ).first()

    return render(
        request,
        'lessons/detail.html',
        {
            'lesson': lesson,
            'course': lesson.course,
            'access': access_result,
            'progress': progress,
        },
    )
