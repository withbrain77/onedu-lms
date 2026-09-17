import json
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.services.access import can_access_lesson
from core.services.completion import evaluate_enrollment_completion
from lessons.models import Lesson
from enrollments.models import Enrollment

from .models import ProgressSaveReceipt, WatchProgress


def _seconds(value, default=0):
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError, OverflowError):
        return default


def _json_body(request):
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST


@login_required
@require_POST
def save_lesson_progress(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related('course'),
        pk=lesson_id,
        is_public=True,
        course__is_public=True,
    )
    access_result = can_access_lesson(request.user, lesson)
    if not access_result.allowed:
        return JsonResponse(
            {'ok': False, 'message': access_result.message, 'code': access_result.code},
            status=403,
        )
    if access_result.enrollment is None:
        return JsonResponse(
            {'ok': False, 'message': '수강생 진도 저장 대상이 아닙니다.', 'code': 'no_enrollment'},
            status=403,
        )

    payload = _json_body(request)
    if payload.get('enrollment_id') and str(payload['enrollment_id']) != str(access_result.enrollment.pk):
        return JsonResponse({'ok': False, 'code': 'enrollment_changed'}, status=409)
    event_id = None
    recorded_at = timezone.now()
    if payload.get('event_id'):
        try:
            event_id = UUID(str(payload['event_id']))
            recorded_at = parse_datetime(str(payload.get('recorded_at', '')))
            if recorded_at is None or timezone.is_naive(recorded_at):
                raise ValueError('Timezone-aware timestamp required')
            recorded_at = min(recorded_at, timezone.now())
        except (ValueError, TypeError, OverflowError):
            return JsonResponse({'ok': False, 'code': 'invalid_event'}, status=400)
    position_seconds = _seconds(payload.get('position_seconds'))
    duration_seconds = _seconds(payload.get('duration_seconds'), lesson.duration_seconds)
    watched_increment_seconds = min(_seconds(payload.get('watched_increment_seconds')), 60)
    completed = payload.get('completed') in (True, 'true', 'True', '1', 1)

    with transaction.atomic():
        # Serialize creation and increments, including simultaneous requests from tabs.
        Enrollment.objects.select_for_update().get(pk=access_result.enrollment.pk)
        progress, _created = WatchProgress.objects.get_or_create(
            user=request.user,
            enrollment=access_result.enrollment,
            lesson=lesson,
            defaults={'duration_seconds': duration_seconds},
        )
        duplicate = event_id and ProgressSaveReceipt.objects.filter(progress=progress, event_id=event_id).exists()
        if not duplicate:
            previous_position = progress.last_position_seconds
            is_latest = not progress.last_position_recorded_at or recorded_at >= progress.last_position_recorded_at
            progress.mark_position(
                position_seconds=position_seconds,
                duration_seconds=duration_seconds or lesson.duration_seconds,
                watched_increment_seconds=watched_increment_seconds,
                completed=completed,
            )
            if is_latest:
                progress.last_position_recorded_at = recorded_at
            else:
                progress.last_position_seconds = previous_position
            progress.full_clean()
            progress.save()
            if event_id:
                ProgressSaveReceipt.objects.create(progress=progress, event_id=event_id)

    if duration_seconds and lesson.duration_seconds != duration_seconds:
        Lesson.objects.filter(pk=lesson.pk).update(duration_seconds=duration_seconds)

    completion_status = evaluate_enrollment_completion(access_result.enrollment)

    return JsonResponse(
        {
            'ok': True,
            'last_position_seconds': progress.last_position_seconds,
            'total_watched_seconds': progress.total_watched_seconds,
            'duration_seconds': progress.duration_seconds,
            'progress_percent': progress.progress_percent,
            'is_completed': progress.is_completed,
            'last_watched_at': progress.last_watched_at.isoformat(),
            'course_completed': completion_status['enrollment'].is_completed,
        }
    )
