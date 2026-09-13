from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Enrollment, ReEnrollmentRequest


@transaction.atomic
def renew_free_enrollment(enrollment):
    enrollment = Enrollment.objects.select_for_update().get(pk=enrollment.pk)
    if not enrollment.course.is_free or not enrollment.is_approved or not enrollment.has_ended:
        return False

    renewal = enrollment.reenrollment_requests.filter(status=ReEnrollmentRequest.Status.PENDING).first()
    if renewal is None:
        renewal = ReEnrollmentRequest(
            user_id=enrollment.user_id,
            course_id=enrollment.course_id,
            enrollment=enrollment,
            reason='무료 재수강 신청',
        )
    renewal.status = ReEnrollmentRequest.Status.APPROVED
    renewal.extension_start_date = timezone.localdate()
    renewal.extension_end_date = renewal.extension_start_date + timedelta(days=enrollment.course.default_enrollment_days)
    renewal.save()
    enrollment.expiry_notice_7d_sent_at = None
    enrollment.save(update_fields=['expiry_notice_7d_sent_at', 'updated_at'])
    return True
