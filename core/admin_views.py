from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from accounts.models import AccessLog
from enrollments.models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from lessons.models import HLSConversionJob, LessonAttachmentDownload


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
