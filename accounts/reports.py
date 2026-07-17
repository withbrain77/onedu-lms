from django.urls import reverse
from django.utils import timezone

from certificates.models import Certificate
from core.services.completion import get_completion_status
from enrollments.models import Enrollment
from lessons.models import LessonAttachmentDownload
from lessons.templatetags.lesson_time import duration_hms
from progress.models import WatchProgress
from progress.services import get_course_progress_percent
from quizzes.models import QuizAttempt

from .models import AccessLog


def _duration_label(seconds):
    return duration_hms(seconds or 0)


def _watch_multiplier(total_watched_seconds, duration_seconds):
    if not duration_seconds:
        return None
    return round((total_watched_seconds or 0) / duration_seconds, 1)


def _distinct_nonempty(queryset, field_name):
    return len({value for value in queryset.values_list(field_name, flat=True) if value})


def _watch_risk_label(multiplier, suspicious_access_count, ip_count, device_count):
    if suspicious_access_count or ip_count >= 3 or device_count >= 3 or (multiplier is not None and multiplier >= 3):
        return '주의'
    if ip_count >= 2 or device_count >= 2 or (multiplier is not None and multiplier >= 2):
        return '관찰'
    return '정상'


def build_student_learning_report(student):
    enrollments = (
        Enrollment.objects
        .filter(user=student)
        .select_related('course', 'approved_by')
        .order_by('-created_at')
    )
    enrollment_items = []
    for enrollment in enrollments:
        progresses = list(
            WatchProgress.objects
            .filter(enrollment=enrollment)
            .select_related('lesson')
            .order_by('lesson__order', 'lesson__id')
        )
        total_watched_seconds = sum(progress.total_watched_seconds or 0 for progress in progresses)
        total_duration_seconds = sum(
            progress.duration_seconds or getattr(progress.lesson, 'duration_seconds', 0) or 0
            for progress in progresses
        )
        attempts = list(
            QuizAttempt.objects
            .filter(enrollment=enrollment)
            .select_related('quiz')
            .order_by('-submitted_at', '-started_at')
        )
        certificate = Certificate.objects.filter(enrollment=enrollment).first()
        access_logs = AccessLog.objects.filter(
            user=student,
            course_id_value=enrollment.course_id,
        )
        downloads = LessonAttachmentDownload.objects.filter(
            user=student,
            course=enrollment.course,
        )
        completion = get_completion_status(enrollment)
        ip_count = _distinct_nonempty(access_logs, 'ip_address')
        device_count = _distinct_nonempty(access_logs, 'device_summary')
        watch_multiplier = _watch_multiplier(total_watched_seconds, total_duration_seconds)
        suspicious_access_count = access_logs.filter(is_suspicious=True).count()
        enrollment_items.append(
            {
                'enrollment': enrollment,
                'course': enrollment.course,
                'progress_percent': get_course_progress_percent(enrollment),
                'completion': completion,
                'progresses': progresses,
                'quiz_attempts': attempts,
                'certificate': certificate,
                'total_watched_seconds': total_watched_seconds,
                'total_watched_label': _duration_label(total_watched_seconds),
                'total_duration_seconds': total_duration_seconds,
                'total_duration_label': _duration_label(total_duration_seconds),
                'watch_multiplier': watch_multiplier,
                'download_count': downloads.count(),
                'recent_downloads': downloads.order_by('-downloaded_at')[:5],
                'access_count': access_logs.count(),
                'suspicious_access_count': suspicious_access_count,
                'distinct_ip_count': ip_count,
                'distinct_device_count': device_count,
                'watch_risk_label': _watch_risk_label(watch_multiplier, suspicious_access_count, ip_count, device_count),
                'last_access': access_logs.order_by('-created_at').first(),
                'admin_change_url': reverse('admin:enrollments_enrollment_change', args=[enrollment.pk]),
            }
        )

    all_progresses = WatchProgress.objects.filter(user=student)
    total_watched_seconds = sum(item.total_watched_seconds or 0 for item in all_progresses)
    total_duration_seconds = sum(
        item.duration_seconds or getattr(item.lesson, 'duration_seconds', 0) or 0
        for item in all_progresses.select_related('lesson')
    )
    recent_access_logs = AccessLog.objects.filter(user=student).order_by('-created_at')[:20]
    recent_downloads = LessonAttachmentDownload.objects.filter(user=student).order_by('-downloaded_at')[:20]
    all_access_logs = AccessLog.objects.filter(user=student)
    today = timezone.localdate()
    summary_watch_multiplier = _watch_multiplier(total_watched_seconds, total_duration_seconds)
    summary_suspicious_count = all_access_logs.filter(is_suspicious=True).count()
    summary_ip_count = _distinct_nonempty(all_access_logs, 'ip_address')
    summary_device_count = _distinct_nonempty(all_access_logs, 'device_summary')

    return {
        'student': student,
        'generated_at': timezone.now(),
        'today': today,
        'enrollments': enrollment_items,
        'summary': {
            'enrollment_count': len(enrollment_items),
            'active_count': sum(1 for item in enrollment_items if item['enrollment'].is_within_period(today)),
            'completed_count': sum(1 for item in enrollment_items if item['enrollment'].is_completed),
            'total_watched_label': _duration_label(total_watched_seconds),
            'watch_multiplier': summary_watch_multiplier,
            'download_count': LessonAttachmentDownload.objects.filter(user=student).count(),
            'suspicious_access_count': summary_suspicious_count,
            'distinct_ip_count': summary_ip_count,
            'distinct_device_count': summary_device_count,
            'watch_risk_label': _watch_risk_label(
                summary_watch_multiplier,
                summary_suspicious_count,
                summary_ip_count,
                summary_device_count,
            ),
        },
        'recent_access_logs': recent_access_logs,
        'recent_downloads': recent_downloads,
    }
