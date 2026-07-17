from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AccessLog
from enrollments.models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from lessons.models import HLSConversionJob, LessonAttachmentDownload

from .models import ServerWarningAcknowledgement
from .server_status import build_server_status


def _tail_log_file(path, max_lines=300, max_bytes=256 * 1024):
    log_path = Path(path) if path else None
    if not log_path:
        return {
            'path': '-',
            'exists': False,
            'lines': [],
            'message': '로그 파일 경로가 설정되어 있지 않습니다.',
            'size': 0,
            'truncated': False,
        }
    if not log_path.exists():
        return {
            'path': str(log_path),
            'exists': False,
            'lines': [],
            'message': '아직 기록된 서버 로그 파일이 없습니다. 오류나 운영 이벤트가 발생하면 이곳에 표시됩니다.',
            'size': 0,
            'truncated': False,
        }

    size = log_path.stat().st_size
    offset = max(size - max_bytes, 0)
    with log_path.open('rb') as log_file:
        log_file.seek(offset)
        data = log_file.read(max_bytes)
    lines = data.decode('utf-8', errors='replace').splitlines()
    if offset and lines:
        lines = lines[1:]
    lines = lines[-max_lines:]
    return {
        'path': str(log_path),
        'exists': True,
        'lines': lines,
        'message': '',
        'size': size,
        'truncated': bool(offset),
    }


@staff_member_required
def server_operations(request):
    context = {
        'title': '서버 상태',
        'status': build_server_status(request),
        'links': {
            'dashboard': reverse('admin:index'),
            'mobile': reverse('admin_mobile_ops'),
            'logs': reverse('admin_server_logs'),
            'access_logs': reverse('admin:accounts_accesslog_changelist'),
            'hls': reverse('admin:lessons_hlsconversionjob_changelist'),
            'email_logs': reverse('admin:enrollments_emaildeliverylog_changelist'),
            'ack_warning': reverse('admin_server_warning_ack'),
        },
    }
    return render(request, 'admin/server_operations.html', context)


@staff_member_required
def server_logs(request):
    log_data = _tail_log_file(getattr(settings, 'ONEDU_LOG_FILE', ''))
    context = {
        'title': '서버 로그',
        'log_data': log_data,
        'links': {
            'dashboard': reverse('admin:index'),
            'server': reverse('admin_server_ops'),
            'refresh': reverse('admin_server_logs'),
        },
    }
    return render(request, 'admin/server_logs.html', context)


@staff_member_required
@require_POST
def acknowledge_server_warning(request):
    warning_key = request.POST.get('warning_key', '').strip()
    message_hash = request.POST.get('message_hash', '').strip()
    message = request.POST.get('message', '').strip()

    if warning_key and message_hash:
        ServerWarningAcknowledgement.objects.get_or_create(
            warning_key=warning_key,
            message_hash=message_hash,
            defaults={
                'message': message,
                'acknowledged_by': request.user,
            },
        )
        messages.success(request, '운영 경고를 확인 완료 처리했습니다.')
    else:
        messages.error(request, '확인 처리할 운영 경고 정보를 찾지 못했습니다.')

    next_url = request.POST.get('next') or reverse('admin_server_ops')
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse('admin_server_ops')
    return redirect(next_url)


@staff_member_required
def mobile_operations(request):
    pending_enrollments = (
        Enrollment.objects
        .filter(status=Enrollment.Status.REQUESTED)
        .select_related('user', 'course')
        .order_by('-created_at')[:12]
    )
    pending_reenrollments = (
        ReEnrollmentRequest.objects
        .filter(status=ReEnrollmentRequest.Status.PENDING)
        .select_related('user', 'course', 'enrollment')
        .order_by('-requested_at')[:10]
    )
    hls_jobs = (
        HLSConversionJob.objects
        .filter(status__in=[
            HLSConversionJob.Status.PENDING,
            HLSConversionJob.Status.RUNNING,
            HLSConversionJob.Status.FAILED,
        ])
        .select_related('lesson', 'lesson__course')
        .order_by('-created_at')[:10]
    )
    email_logs = (
        EmailDeliveryLog.objects
        .filter(status__in=[EmailDeliveryLog.Status.FAILED, EmailDeliveryLog.Status.SKIPPED])
        .select_related('enrollment')
        .order_by('-created_at')[:10]
    )
    suspicious_logs = (
        AccessLog.objects
        .filter(is_suspicious=True)
        .select_related('user')
        .order_by('-created_at')[:10]
    )
    recent_downloads = (
        LessonAttachmentDownload.objects
        .select_related('user', 'course', 'lesson')
        .order_by('-downloaded_at')[:10]
    )

    context = {
        'title': '모바일 운영',
        'today': timezone.localdate(),
        'pending_enrollments': pending_enrollments,
        'pending_reenrollments': pending_reenrollments,
        'hls_jobs': hls_jobs,
        'email_logs': email_logs,
        'suspicious_logs': suspicious_logs,
        'recent_downloads': recent_downloads,
        'links': {
            'dashboard': reverse('admin:index'),
            'enrollments': reverse('admin:enrollments_enrollment_changelist'),
            'reenrollments': reverse('admin:enrollments_reenrollmentrequest_changelist'),
            'hls': reverse('admin:lessons_hlsconversionjob_changelist'),
            'email_logs': reverse('admin:enrollments_emaildeliverylog_changelist'),
            'access_logs': reverse('admin:accounts_accesslog_changelist'),
            'downloads': reverse('admin:lessons_lessonattachmentdownload_changelist'),
        },
    }
    return render(request, 'admin/mobile_operations.html', context)
