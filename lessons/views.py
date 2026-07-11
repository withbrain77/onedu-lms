import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from core.services.access import can_access_lesson
from progress.models import WatchProgress

from .models import Lesson, LessonAttachment


HLS_ALLOWED_SUFFIXES = {'.ts', '.m4s', '.mp4', '.aac', '.vtt'}


def _lesson_queryset():
    return Lesson.objects.select_related('course').filter(is_public=True, course__is_public=True)


def _watermark_text(user):
    username = user.get_username()
    if user.is_staff:
        return f'관리자 미리보기 / {username}'
    return f'{user.display_name} / {username}'


def _private_media_root():
    return Path(settings.PRIVATE_MEDIA_ROOT).resolve()


def _private_file_path(relative_path):
    file_path = (_private_media_root() / relative_path).resolve()
    try:
        file_path.relative_to(_private_media_root())
    except ValueError:
        raise Http404('File not found')
    return file_path


def _content_disposition(disposition, filename):
    ascii_filename = filename.encode('ascii', 'ignore').decode().strip() or 'download'
    ascii_filename = ascii_filename.replace('\\', '\\\\').replace('"', '\\"')
    encoded_filename = quote(filename, safe='')
    return f'{disposition}; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'


def _protected_file_response(file_path, content_type, filename, disposition='inline'):
    if not file_path.exists() or not file_path.is_file():
        raise Http404('File not found')

    try:
        relative_path = file_path.resolve().relative_to(_private_media_root())
    except ValueError:
        raise Http404('File not found')

    if settings.USE_X_ACCEL_REDIRECT:
        internal_prefix = settings.X_ACCEL_REDIRECT_PREFIX.rstrip('/')
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = f'{internal_prefix}/{quote(relative_path.as_posix())}'
    else:
        response = FileResponse(file_path.open('rb'), content_type=content_type)
    response['Content-Disposition'] = _content_disposition(disposition, filename)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _get_accessible_lesson_or_404(user, pk):
    lesson = get_object_or_404(_lesson_queryset(), pk=pk)
    access_result = can_access_lesson(user, lesson)
    if not access_result.allowed:
        raise Http404('Lesson not found')
    return lesson


def _hls_playlist_path(lesson):
    if not lesson.has_hls:
        raise Http404('HLS playlist not found')
    playlist_path = _private_file_path(lesson.hls_playlist_path)
    if playlist_path.suffix.lower() != '.m3u8':
        raise Http404('HLS playlist not found')
    if not playlist_path.exists():
        raise Http404('HLS playlist not found')
    return playlist_path


def _rewrite_hls_playlist(lesson, playlist_text):
    lines = []
    for line in playlist_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            lines.append(line)
            continue
        if '://' in stripped or stripped.startswith('/'):
            lines.append(line)
            continue
        lines.append(reverse('lessons:hls_file', kwargs={'pk': lesson.pk, 'filename': stripped}))
    return '\n'.join(lines) + '\n'


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
    attachments = list(lesson.attachments.filter(is_public=True).order_by('order', 'id'))
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
            'attachments': attachments,
            'next_lesson': next_lesson,
            'watermark_text': _watermark_text(request.user),
        },
    )


@login_required
def lesson_video(request, pk):
    lesson = _get_accessible_lesson_or_404(request.user, pk)

    if not lesson.video_file:
        raise Http404('Video file not found')

    file_path = _private_file_path(lesson.video_file.name)
    content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    return _protected_file_response(file_path, content_type, f'lesson-{lesson.pk}{file_path.suffix}')


@login_required
def lesson_hls_playlist(request, pk):
    lesson = _get_accessible_lesson_or_404(request.user, pk)
    playlist_path = _hls_playlist_path(lesson)
    playlist_text = playlist_path.read_text(encoding='utf-8')
    response = HttpResponse(
        _rewrite_hls_playlist(lesson, playlist_text),
        content_type='application/vnd.apple.mpegurl; charset=utf-8',
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def lesson_hls_file(request, pk, filename):
    lesson = _get_accessible_lesson_or_404(request.user, pk)
    playlist_path = _hls_playlist_path(lesson)
    base_dir = playlist_path.parent.resolve()
    file_path = (base_dir / filename).resolve()
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise Http404('HLS file not found')

    if file_path.suffix.lower() not in HLS_ALLOWED_SUFFIXES:
        raise Http404('HLS file not found')

    content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    if file_path.suffix.lower() == '.ts':
        content_type = 'video/mp2t'
    elif file_path.suffix.lower() == '.m4s':
        content_type = 'video/iso.segment'
    return _protected_file_response(file_path, content_type, file_path.name)


@login_required
def lesson_attachment_download(request, pk, attachment_id):
    lesson = _get_accessible_lesson_or_404(request.user, pk)
    attachment = get_object_or_404(
        LessonAttachment.objects.filter(lesson=lesson, is_public=True),
        pk=attachment_id,
    )
    if not attachment.file:
        raise Http404('Attachment file not found')

    file_path = _private_file_path(attachment.file.name)
    content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    return _protected_file_response(file_path, content_type, attachment.filename, disposition='attachment')
