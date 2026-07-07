import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.services.access import can_access_lesson
from progress.models import WatchProgress

from .models import Lesson


def _lesson_queryset():
    return Lesson.objects.select_related('course').filter(is_public=True, course__is_public=True)


def _watermark_text(user):
    username = user.get_username()
    if user.is_staff:
        return f'관리자 미리보기 / {username}'
    return f'{user.display_name} / {username}'


@login_required
@ensure_csrf_cookie
def lesson_detail(request, pk):
    lesson = get_object_or_404(
        _lesson_queryset(),
        pk=pk,
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
        progress, _created = WatchProgress.objects.get_or_create(
            user=request.user,
            enrollment=access_result.enrollment,
            lesson=lesson,
            defaults={'duration_seconds': lesson.duration_seconds},
        )

    course_lessons = list(lesson.course.lessons.filter(is_public=True).order_by('order', 'id'))
    progress_by_lesson = {}
    if access_result.enrollment:
        progress_by_lesson = {
            item.lesson_id: item
            for item in WatchProgress.objects.filter(
                enrollment=access_result.enrollment,
                lesson__in=course_lessons,
            )
        }
    course_lesson_items = [
        {
            'lesson': course_lesson,
            'progress': progress_by_lesson.get(course_lesson.pk),
            'is_current': course_lesson.pk == lesson.pk,
        }
        for course_lesson in course_lessons
    ]
    next_lesson = None
    for index, course_lesson in enumerate(course_lessons):
        if course_lesson.pk == lesson.pk and index + 1 < len(course_lessons):
            next_lesson = course_lessons[index + 1]
            break

    return render(
        request,
        'lessons/detail.html',
        {
            'lesson': lesson,
            'course': lesson.course,
            'access': access_result,
            'progress': progress,
            'course_lesson_items': course_lesson_items,
            'next_lesson': next_lesson,
            'watermark_text': _watermark_text(request.user),
        },
    )


@login_required
def lesson_video(request, pk):
    lesson = get_object_or_404(_lesson_queryset(), pk=pk)
    access_result = can_access_lesson(request.user, lesson)
    if not access_result.allowed:
        raise Http404('Video not found')

    if not lesson.video_file:
        raise Http404('Video file not found')

    file_path = Path(lesson.video_file.path)
    if not file_path.exists():
        raise Http404('Video file not found')
    try:
        file_path.resolve().relative_to(Path(settings.PRIVATE_MEDIA_ROOT).resolve())
    except ValueError:
        raise Http404('Video file not found')

    content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    if settings.USE_X_ACCEL_REDIRECT:
        relative_path = file_path.resolve().relative_to(Path(settings.PRIVATE_MEDIA_ROOT).resolve())
        internal_prefix = settings.X_ACCEL_REDIRECT_PREFIX.rstrip('/')
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = f'{internal_prefix}/{quote(relative_path.as_posix())}'
    else:
        response = FileResponse(file_path.open('rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="lesson-{lesson.pk}{file_path.suffix}"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
